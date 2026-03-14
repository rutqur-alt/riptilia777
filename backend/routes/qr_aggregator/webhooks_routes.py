"""TrustGain webhook handling routes for QR aggregator.

Extracted from legacy.py to keep modules focused.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, HTTPException, Request

from core.database import db

from .router import logger, router
from .trade_logic import (
    _cancel_qr_trade,
    _complete_qr_trade,
    _try_complete_trade_with_balance_check,
)

@router.post("/qr-aggregator/webhook/{provider_id}")
async def handle_trustgain_webhook(provider_id: str, request: Request, background_tasks: BackgroundTasks):
    """Handle incoming webhook from TrustGain"""
    provider = await db.qr_providers.find_one({"id": provider_id}, {"_id": 0})
    if not provider:
        logger.error(f"[QR Webhook] Unknown provider: {provider_id}")
        raise HTTPException(status_code=404, detail="Provider not found")

    body = await request.body()
    body_str = body.decode("utf-8")

    # Verify webhook signature per docs:
    # Header: Payments-Signature: "t=<timestamp>,s=<signature>"
    sig_header = request.headers.get("Payments-Signature", "")

    # Determine which integration's secret to use based on webhook data
    try:
        webhook_data = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Try to find matching operation to determine method
    op_id = webhook_data.get("id") or webhook_data.get("payload", {}).get("id") or webhook_data.get("operation_id")
    operation = None
    secret_key = ""

    if op_id:
        operation = await db.qr_provider_operations.find_one({
            "provider_id": provider_id, "trustgain_operation_id": op_id
        }, {"_id": 0})
        if operation:
            method = operation.get("payment_method", "nspk")
            secret_key = provider.get(f"{method}_secret_key", "")

    # If no operation found, try both secrets
    if not secret_key:
        secret_key = provider.get("nspk_secret_key", "") or provider.get("transgrant_secret_key", "")

    if secret_key and sig_header:
        from services.trustgain_client import TrustGainClient
        if not TrustGainClient.verify_webhook_signature(secret_key, sig_header, body_str):
            logger.error(f"[QR Webhook] Invalid signature for provider {provider_id}")
            raise HTTPException(status_code=400, detail="Invalid signature")

    logger.info(f"[QR Webhook] Received for provider {provider_id}: event={webhook_data.get('event', 'unknown')}")

    # Store webhook
    webhook_record = {
        "id": str(uuid.uuid4()),
        "provider_id": provider_id,
        "data": webhook_data,
        "signature": sig_header,
        "processed": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.qr_provider_webhooks.insert_one(webhook_record)

    background_tasks.add_task(process_webhook, provider_id, webhook_data, webhook_record["id"])
    return {"status": "ok"}


async def process_webhook(provider_id: str, webhook_data: dict, webhook_record_id: str):
    """Process a TrustGain webhook - update operation status"""
    try:
        # New format: {id, created_at, event, payload}
        # Legacy format: {operation_id, operation_amount, operation_status, ...}
        payload = webhook_data.get("payload", webhook_data)
        operation_id = payload.get("id") or payload.get("operation_id")
        status = payload.get("status") or payload.get("operation_status", "")

        if not operation_id:
            logger.warning(f"[QR Webhook] No operation_id in webhook for provider {provider_id}")
            await db.qr_provider_webhooks.update_one(
                {"id": webhook_record_id}, {"$set": {"processed": True, "error": "no_operation_id"}}
            )
            return

        operation = await db.qr_provider_operations.find_one({
            "provider_id": provider_id, "trustgain_operation_id": operation_id
        }, {"_id": 0})

        if not operation:
            logger.warning(f"[QR Webhook] Operation not found: {operation_id}")
            await db.qr_provider_webhooks.update_one(
                {"id": webhook_record_id}, {"$set": {"processed": True, "error": "operation_not_found"}}
            )
            return

        # Map TrustGain statuses to our statuses per docs
        status_map = {
            "auto_approved": "completed",
            "manually_approved": "completed",
            "created": "pending",
            "in_progress": "processing",
            "paid": "paid",
            "expired": "expired",
            "cancelled": "cancelled",
            "rejected": "rejected",
        }

        mapped_status = status_map.get(status.lower(), status.lower())

        update_data = {
            "status": mapped_status,
            "webhook_data": webhook_data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        approved_amount = payload.get("approved_amount")
        if approved_amount and mapped_status == "completed":
            update_data["approved_amount_rub"] = float(approved_amount)
            update_data["completed_at"] = datetime.now(timezone.utc).isoformat()

        await db.qr_provider_operations.update_one(
            {"id": operation["id"]}, {"$set": update_data}
        )

        # Update active operations count
        if mapped_status in ("completed", "rejected", "expired", "cancelled"):
            await db.qr_providers.update_one(
                {"id": provider_id, "active_operations_count": {"$gt": 0}},
                {"$inc": {"active_operations_count": -1}}
            )

        # Complete trade
        if mapped_status == "completed" and operation.get("trade_id"):
            # Check if the trade is already cancelled — auto_approve came after cancellation
            trade = await db.trades.find_one({"id": operation["trade_id"]}, {"_id": 0})
            if trade and trade.get("status") == "cancelled":
                # Payment confirmed after trade was cancelled — try to complete with balance check
                logger.info(f"[QR Webhook] auto_approve on cancelled trade {operation['trade_id']} — attempting deferred completion")
                await _try_complete_trade_with_balance_check(trade, provider_id, source="webhook_auto_approve")
            elif trade and trade.get("status") == "pending_completion":
                # Already pending — try again (maybe balance was added)
                logger.info(f"[QR Webhook] auto_approve on pending_completion trade {operation['trade_id']} — retrying")
                await _try_complete_trade_with_balance_check(trade, provider_id, source="webhook_retry")
            else:
                await _complete_qr_trade(operation, provider_id)

        # Cancel trade
        if mapped_status in ("rejected", "expired", "cancelled") and operation.get("trade_id"):
            await _cancel_qr_trade(operation)

        # Update provider stats
        if mapped_status == "completed":
            await db.qr_providers.update_one(
                {"id": provider_id},
                {"$inc": {"completed_operations": 1, "total_operations": 1}}
            )
        elif mapped_status in ("rejected", "expired", "cancelled"):
            await db.qr_providers.update_one(
                {"id": provider_id},
                {"$inc": {"total_operations": 1}}
            )

        await db.qr_provider_webhooks.update_one(
            {"id": webhook_record_id}, {"$set": {"processed": True}}
        )

        logger.info(f"[QR Webhook] Processed: op={operation_id}, status={mapped_status}")

    except Exception as e:
        logger.error(f"[QR Webhook] Error: {e}")
        await db.qr_provider_webhooks.update_one(
            {"id": webhook_record_id}, {"$set": {"processed": True, "error": str(e)}}
        )
