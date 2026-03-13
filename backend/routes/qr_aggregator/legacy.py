"""
QR Aggregator Routes v2
Fully rewritten per TZ requirements:
- Two separate integrations: NSPK (QR) and TransGrant (CNG)
- Provider balance in USDT
- Provider deposit via USDT (same as regular users)
- Provider withdrawal (same as regular users)
- Separate statistics per integration
- Commission settings per integration
- Strict TrustGain API integration per https://docs.trustgain.io/
"""
import os
from fastapi import HTTPException, Depends, Request, BackgroundTasks, Body
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import uuid
import hmac
import hashlib
import json
import asyncio

from core.database import db
from core.auth import get_current_user, require_role, require_admin_level, create_token, hash_password, verify_password

from .router import router, logger

from .trade_logic import (
    _complete_qr_trade,
    _try_complete_trade_with_balance_check,
    _process_pending_completions,
    _cancel_qr_trade,
)

# ==================== Pydantic Models ====================

from .schemas import (
    AdminAdjustBalance,
    QRAggregatorBuyPublicRequest,
    QRAggregatorBuyRequest,
    QRAggregatorSettings,
    QRDisputeRequest,
    QRDisputeResolveRequest,
    QRProviderCreate,
    QRProviderLogin,
    QRProviderUpdate,
    WithdrawRequest,
)

from .utils import (
    get_base_rate as _get_base_rate,
    get_qr_provider_user as _get_qr_provider_user,
    mask_key as _mask_key,
    mask_secret as _mask_secret,
)

# ==================== QR Provider Routes ====================
# (extracted to backend/routes/qr_aggregator/provider_routes.py)

# ==================== Admin Routes ====================
# (extracted to backend/routes/qr_aggregator/admin_routes.py)

# ==================== Health Check Background Task ====================

async def _cleanup_failed_trustgain_trades():
    """Auto-cancel QR trades where TrustGain operation creation failed.
    
    These are trades that:
    - Have status 'paid' or 'pending' 
    - Have empty trustgain_operation_id (TrustGain never got the operation)
    - Their QR operation has trustgain_data.success == False
    - Have been stuck for more than 2 minutes
    
    This happens when TrustGain returns errors like 'Temporarily no payment_requisite available'.
    """
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        now = datetime.now(timezone.utc).isoformat()

        # Find QR trades that are stuck with no TrustGain operation
        stuck_trades = await db.trades.find({
            "$or": [{"trader_id": "qr_aggregator"}, {"qr_aggregator_trade": True}],
            "status": {"$in": ["pending", "paid"]},
            "trustgain_operation_id": {"$in": [None, ""]},
            "created_at": {"$lt": cutoff},
        }).to_list(100)

        cancelled_count = 0
        for trade in stuck_trades:
            trade_id = trade["id"]
            provider_id = trade.get("provider_id")
            total_freeze = trade.get("total_freeze_usdt", 0)

            # Verify the QR operation also failed
            op = await db.qr_provider_operations.find_one(
                {"trade_id": trade_id},
                {"_id": 0, "trustgain_data": 1, "trustgain_operation_id": 1, "id": 1}
            )
            
            # Only cancel if operation has trustgain_data.success == False or no operation at all
            if op:
                tg_data = op.get("trustgain_data", {})
                tg_op_id = op.get("trustgain_operation_id", "")
                if tg_data.get("success") is not False and tg_op_id:
                    # Operation seems valid, skip
                    continue

            # Cancel the trade
            await db.trades.update_one(
                {"id": trade_id, "status": {"$in": ["pending", "paid"]}},
                {"$set": {
                    "status": "cancelled",
                    "cancelled_at": now,
                    "cancel_reason": "trustgain_creation_failed",
                }}
            )

            # Unfreeze provider funds
            if provider_id and total_freeze > 0:
                result = await db.qr_providers.update_one(
                    {"id": provider_id, "frozen_usdt": {"$gte": total_freeze}},
                    {"$inc": {"frozen_usdt": -total_freeze, "active_operations_count": -1}}
                )
                if result.modified_count == 0:
                    p = await db.qr_providers.find_one({"id": provider_id})
                    if p:
                        await db.qr_providers.update_one(
                            {"id": provider_id},
                            {"$set": {
                                "frozen_usdt": max(0, p.get("frozen_usdt", 0) - total_freeze),
                                "active_operations_count": max(0, p.get("active_operations_count", 0) - 1),
                            }}
                        )

            # Cancel the QR operation too
            if op:
                await db.qr_provider_operations.update_one(
                    {"id": op["id"]},
                    {"$set": {"status": "cancelled", "updated_at": now}}
                )

            cancelled_count += 1
            tg_errors = ""
            if op:
                tg_errors = str(op.get("trustgain_data", {}).get("errors", ""))
            logger.info(f"[QR Cleanup] Auto-cancelled failed trade {trade_id}: "
                       f"unfrozen {total_freeze:.4f} USDT for provider {provider_id}. "
                       f"TrustGain errors: {tg_errors}")

        if cancelled_count > 0:
            logger.info(f"[QR Cleanup] Auto-cancelled {cancelled_count} failed TrustGain trades")
    except Exception as e:
        logger.error(f"[QR Cleanup] Error in _cleanup_failed_trustgain_trades: {e}")


async def _cleanup_expired_trades():
    """Cleanup expired QR trades and unfreeze provider funds"""
    try:
        now = datetime.now(timezone.utc).isoformat()
        expired_trades = await db.trades.find({
            "$or": [{"trader_id": "qr_aggregator"}, {"qr_aggregator_trade": True}],
            "status": "pending",
            "expires_at": {"$lt": now}
        }).to_list(100)
        
        for trade in expired_trades:
            provider_id = trade.get("provider_id")
            total_freeze = trade.get("total_freeze_usdt", 0)
            
            await db.trades.update_one(
                {"id": trade["id"], "status": "pending"},
                {"$set": {"status": "cancelled", "cancelled_at": now, "cancel_reason": "expired"}}
            )
            
            if provider_id and total_freeze > 0:
                result = await db.qr_providers.update_one(
                    {"id": provider_id, "frozen_usdt": {"$gte": total_freeze}},
                    {"$inc": {"frozen_usdt": -total_freeze, "active_operations_count": -1}}
                )
                if result.modified_count == 0:
                    p = await db.qr_providers.find_one({"id": provider_id})
                    if p:
                        await db.qr_providers.update_one(
                            {"id": provider_id},
                            {"$set": {
                                "frozen_usdt": max(0, p.get("frozen_usdt", 0) - total_freeze),
                                "active_operations_count": max(0, p.get("active_operations_count", 0) - 1)
                            }}
                        )
                logger.info(f"[QR Cleanup] Expired trade {trade['id']}: unfrozen {total_freeze:.4f} USDT for provider {provider_id}")
            
            # Cancel the TrustGain operation too
            op = await db.qr_provider_operations.find_one({"trade_id": trade["id"], "status": "pending"})
            if op:
                await db.qr_provider_operations.update_one(
                    {"id": op["id"]},
                    {"$set": {"status": "cancelled", "updated_at": now}}
                )
        
        if expired_trades:
            logger.info(f"[QR Cleanup] Cleaned up {len(expired_trades)} expired trades")
    except Exception as e:
        logger.error(f"[QR Cleanup] Error: {e}")

async def _sync_orphaned_operations():
    """Sync operations whose trades were cancelled/completed but operation status wasn't updated.
    
    This catches edge cases where trade cleanup runs but the operation status update
    fails or is skipped (e.g. race condition, error during cleanup).
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        # Find operations still in pending/processing/paid but whose trade is already done
        orphaned_ops = await db.qr_provider_operations.find({
            "status": {"$in": ["pending", "processing", "paid"]},
            "trade_id": {"$exists": True, "$ne": None}
        }).to_list(100)

        synced = 0
        for op in orphaned_ops:
            trade_id = op.get("trade_id")
            if not trade_id:
                continue
            trade = await db.trades.find_one({"id": trade_id}, {"_id": 0, "status": 1})
            if not trade:
                continue
            t_status = trade.get("status", "")
            if t_status == "cancelled":
                await db.qr_provider_operations.update_one(
                    {"id": op["id"]},
                    {"$set": {"status": "cancelled", "updated_at": now}}
                )
                synced += 1
            elif t_status == "completed":
                await db.qr_provider_operations.update_one(
                    {"id": op["id"]},
                    {"$set": {"status": "completed", "updated_at": now}}
                )
                synced += 1
        if synced > 0:
            logger.info(f"[QR Cleanup] Synced {synced} orphaned operations to match trade status")
    except Exception as e:
        logger.error(f"[QR Cleanup] Error in _sync_orphaned_operations: {e}")


async def _reconcile_frozen_balances():
    """Reconcile frozen_usdt and active_operations_count for all providers.
    
    Recalculates these values from actual active trades to fix any drift
    caused by race conditions or errors in the freeze/unfreeze logic.
    """
    try:
        providers = await db.qr_providers.find({}, {"_id": 0, "id": 1, "frozen_usdt": 1, "active_operations_count": 1}).to_list(100)
        for provider in providers:
            pid = provider.get("id")
            if not pid:
                continue

            # Calculate correct frozen amount from active trades
            active_trades = await db.trades.find({
                "provider_id": pid,
                "status": {"$in": ["pending", "paid", "processing", "pending_completion"]},
                "total_freeze_usdt": {"$gt": 0}
            }, {"_id": 0, "total_freeze_usdt": 1}).to_list(200)

            correct_frozen = sum(t.get("total_freeze_usdt", 0) for t in active_trades)
            correct_active = len(active_trades)
            current_frozen = provider.get("frozen_usdt", 0)
            current_active = provider.get("active_operations_count", 0)

            # Only update if there's a discrepancy
            if abs(correct_frozen - current_frozen) > 0.001 or correct_active != current_active:
                await db.qr_providers.update_one(
                    {"id": pid},
                    {"$set": {
                        "frozen_usdt": correct_frozen,
                        "active_operations_count": correct_active,
                    }}
                )
                logger.info(
                    f"[QR Reconcile] Provider {pid}: "
                    f"frozen {current_frozen:.4f} -> {correct_frozen:.4f}, "
                    f"active_ops {current_active} -> {correct_active}"
                )
    except Exception as e:
        logger.error(f"[QR Reconcile] Error: {e}")


async def qr_health_check_loop():
    """Background task to check QR provider health every N seconds"""
    while True:
        # Cleanup expired trades on each cycle
        await _cleanup_expired_trades()

        # Auto-cancel trades where TrustGain creation failed
        await _cleanup_failed_trustgain_trades()

        # Sync orphaned operations whose trades are already done
        await _sync_orphaned_operations()

        # Reconcile frozen balances to fix any drift
        await _reconcile_frozen_balances()

        # Process pending completions for all providers
        try:
            providers_with_pending = await db.trades.distinct("provider_id", {"status": "pending_completion"})
            for pid in providers_with_pending:
                if pid:
                    try:
                        completed = await _process_pending_completions(pid)
                        if completed > 0:
                            logger.info(f"[QR Health] Auto-completed {completed} pending trades for provider {pid}")
                    except Exception as e:
                        logger.error(f"[QR Health] Error processing pending for {pid}: {e}")
        except Exception as e:
            logger.error(f"[QR Health] Pending completions check error: {e}")

        interval = 45
        try:
            settings = await db.qr_aggregator_settings.find_one({"type": "main"}, {"_id": 0})
            if settings:
                interval = settings.get("health_check_interval", 45)
                if not settings.get("is_enabled", True):
                    await asyncio.sleep(interval)
                    continue

            providers = await db.qr_providers.find({"is_active": True}, {"_id": 0}).to_list(100)

            for provider in providers:
                for prefix in ("nspk", "transgrant"):
                    api_key = provider.get(f"{prefix}_api_key", "")
                    secret_key = provider.get(f"{prefix}_secret_key", "")
                    api_url = provider.get(f"{prefix}_api_url", "https://api.trustgain.io")

                    if not api_key or api_key.startswith("demo") or len(api_key) < 10:
                        continue

                    try:
                        from services.trustgain_client import TrustGainClient
                        client = TrustGainClient(api_url=api_url, api_key=api_key, secret_key=secret_key)
                        is_healthy = await client.check_health()
                        await client.close()

                        await db.qr_providers.update_one(
                            {"id": provider["id"]},
                            {"$set": {
                                f"{prefix}_api_available": is_healthy,
                                "last_health_check": datetime.now(timezone.utc).isoformat(),
                            }}
                        )

                        if not is_healthy:
                            logger.warning(f"[QR Health] Provider {provider['id']} {prefix} API unavailable")
                    except Exception as e:
                        logger.error(f"[QR Health] Error checking {prefix} for {provider['id']}: {e}")

        except Exception as e:
            logger.error(f"[QR Health] Loop error: {e}")

        await asyncio.sleep(interval)
