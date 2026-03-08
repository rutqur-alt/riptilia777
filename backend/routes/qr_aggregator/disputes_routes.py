from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Body

from core.auth import get_current_user
from core.database import db

from .router import logger, router
from .schemas import QRDisputeRequest, QRDisputeResolveRequest
from .dispute_utils import (
    _audit_log_dispute,
    _build_dispute_system_message,
    _check_dispute_eligibility,
    _create_qr_dispute_conversation,
)
from .trade_logic import _try_complete_trade_with_balance_check

# ==================== Dispute Routes ====================

@router.post("/qr-aggregator/trades/{trade_id}/dispute")
async def open_qr_dispute(trade_id: str, data: QRDisputeRequest = Body(...), user: dict = Depends(get_current_user)):
    """Open dispute on QR aggregator trade (authenticated user).
    Per spec: only merchant or exchange trader (buyer) can open.
    Conditions: active >60min OR cancelled status.
    """
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    # Check eligibility (QR only, status conditions)
    eligible, err = _check_dispute_eligibility(trade)
    if not eligible:
        raise HTTPException(status_code=400, detail=err)

    # Check no existing active dispute
    existing_dispute = await db.unified_conversations.find_one(
        {"related_id": trade_id, "type": "p2p_dispute", "status": {"$nin": ["resolved", "closed"]}},
        {"_id": 0}
    )
    if existing_dispute:
        raise HTTPException(status_code=400, detail="По этой сделке уже есть активный спор")

    user_id = user["id"]
    user_role = user.get("role", "")
    is_admin = user.get("admin_role") in ("admin", "owner", "mod_p2p")

    # Per spec section 4: only merchant or exchange trader (buyer) can open
    is_merchant = user_id == trade.get("merchant_id") or user_role == "merchant"
    is_buyer_trader = (
        user_role == "trader" and
        user_id == trade.get("buyer_id") and
        not trade.get("merchant_id")  # exchange trade (stakan), no merchant
    )

    if not is_merchant and not is_buyer_trader and not is_admin:
        raise HTTPException(status_code=403, detail="Только мерчант или покупатель (трейдер на бирже) могут открыть спор")

    if is_merchant:
        opener = "мерчант"
        opener_en = "merchant"
    elif is_buyer_trader:
        opener = "покупатель (трейдер)"
        opener_en = "trader"
    else:
        opener = "администратор"
        opener_en = "admin"

    reason = data.reason or "Проблема с оплатой"
    now = datetime.now(timezone.utc).isoformat()

    # Freeze provider funds (if not already frozen from trade creation)
    provider_id = trade.get("provider_id")
    total_freeze_usdt = trade.get("total_freeze_usdt", 0)
    freeze_applied = False
    if provider_id and total_freeze_usdt > 0 and trade.get("status") == "cancelled":
        # On cancelled trades, funds were already unfrozen by _cancel_qr_trade.
        # Re-freeze them for the dispute period.
        result = await db.qr_providers.update_one(
            {"id": provider_id, "balance_usdt": {"$gte": total_freeze_usdt}},
            {"$inc": {"frozen_usdt": total_freeze_usdt}}
        )
        freeze_applied = result.modified_count > 0
        if freeze_applied:
            logger.info(f"[QR Dispute] Re-frozen {total_freeze_usdt:.4f} USDT for provider {provider_id} (dispute on cancelled trade)")
    elif provider_id and total_freeze_usdt > 0:
        # For active trades, funds are already frozen from trade creation — keep them frozen
        freeze_applied = True
        logger.info(f"[QR Dispute] Funds already frozen for provider {provider_id} (active trade dispute)")

    # Update trade status
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "disputed", "disputed_at": now,
            "dispute_reason": reason, "disputed_by": user_id,
            "disputed_by_role": opener_en, "has_dispute": True,
            "is_qr_aggregator_dispute": True,
            "dispute_freeze_applied": freeze_applied,
            "previous_status": trade.get("status"),
        }}
    )

    # Create conversation in existing P2P chat system
    conv = await _create_qr_dispute_conversation(trade, reason, opener, user_id)

    # Build detailed system message per spec section 10
    detail_content = _build_dispute_system_message(trade, opener, reason, now)
    system_msg = {
        "id": str(uuid.uuid4()), "trade_id": trade_id,
        "sender_id": "system", "sender_type": "system",
        "is_system": True, "sender_role": "system",
        "content": detail_content,
        "created_at": now
    }
    await db.trade_messages.insert_one(system_msg)

    # Audit log
    await _audit_log_dispute("dispute_opened", trade_id, user_id, opener_en, {
        "reason": reason, "freeze_applied": freeze_applied,
        "total_freeze_usdt": total_freeze_usdt,
        "previous_status": trade.get("status"),
    })

    # Webhook to merchant
    try:
        from routes.trades import send_merchant_webhook_on_trade
        await send_merchant_webhook_on_trade(trade, "disputed", {
            "trade_id": trade_id, "reason": reason,
            "disputed_at": now, "disputed_by": opener_en,
            "is_qr_aggregator": True,
        })
    except Exception as e:
        logger.error(f"[QR Dispute] Webhook error: {e}")

    logger.info(f"[QR Dispute] Trade {trade_id} disputed by {opener_en} ({user_id}): {reason}")
    return {"status": "dispute_opened", "conversation_id": conv["id"], "trade_id": trade_id}


@router.post("/qr-aggregator/trades/{trade_id}/dispute-public")
async def open_qr_dispute_public(trade_id: str, data: QRDisputeRequest = Body(...)):
    """Open dispute on QR trade without auth (merchant's client scenario).
    Per spec: client of merchant cannot open dispute directly.
    This endpoint is kept for backward compat but now returns guidance.
    """
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    if not trade.get("qr_aggregator_trade") and not trade.get("is_qr_aggregator"):
        raise HTTPException(status_code=400, detail="Не является сделкой QR-агрегатора")

    if trade["status"] == "disputed":
        return {"status": "already_disputed", "message": "Спор уже открыт"}

    # Per spec: client cannot open dispute. Instruct to contact merchant.
    return {
        "status": "not_allowed",
        "message": "Клиент мерчанта не может открыть спор напрямую. Обратитесь к мерчанту для открытия спора."
    }


@router.post("/qr-aggregator/trades/{trade_id}/resolve-dispute")
async def resolve_qr_dispute(
    trade_id: str,
    data: QRDisputeResolveRequest = Body(...),
    user: dict = Depends(get_current_user)
):
    """Resolve QR aggregator dispute (admin/moderator only).
    Per spec section 12:
    - 'complete': complete trade with standard calculations, close dispute
    - 'cancel': cancel trade, unfreeze provider funds, close dispute
    """
    is_admin = user.get("admin_role") in ("admin", "owner", "mod_p2p")
    if not is_admin:
        raise HTTPException(status_code=403, detail="Только администратор или модератор может разрешить спор")

    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    if trade.get("status") not in ("disputed",):
        raise HTTPException(status_code=400, detail="Сделка не в статусе спора")

    resolution = data.decision if hasattr(data, "decision") else data.resolution
    resolve_reason = data.comment if hasattr(data, "comment") else data.reason or ""
    now = datetime.now(timezone.utc).isoformat()
    provider_id = trade.get("provider_id")
    total_freeze_usdt = trade.get("total_freeze_usdt", 0)

    if resolution == "complete":
        # --- COMPLETE TRADE: check provider balance first ---
        # First unfreeze the dispute-frozen funds (they were frozen during dispute opening)
        if provider_id and total_freeze_usdt > 0 and trade.get("dispute_freeze_applied"):
            await db.qr_providers.update_one(
                {"id": provider_id, "frozen_usdt": {"$gte": total_freeze_usdt}},
                {"$inc": {"frozen_usdt": -total_freeze_usdt}}
            )
            logger.info(f"[QR Dispute Resolve] Unfrozen dispute-held {total_freeze_usdt:.4f} USDT for provider {provider_id}")

        # Now try to complete with balance check (will set pending_completion if insufficient)
        # Mark dispute as resolved first
        await db.trades.update_one(
            {"id": trade_id},
            {"$set": {
                "dispute_resolved_at": now, "dispute_resolved_by": user["id"],
                "dispute_resolution": "completed",
            }}
        )

        completed = await _try_complete_trade_with_balance_check(trade, provider_id, source="dispute_resolve")

        if completed:
            message = f"Спор разрешён: сделка завершена. Стандартные расчёты выполнены. {resolve_reason}"
        else:
            message = f"Спор разрешён в пользу покупателя. Ожидание баланса провайдера для завершения. {resolve_reason}"

        # Webhook
        try:
            from routes.trades import send_merchant_webhook_on_trade
            updated_trade = await db.trades.find_one({"id": trade_id}, {"_id": 0}) or trade
            status_for_webhook = "completed" if completed else "pending_completion"
            await send_merchant_webhook_on_trade(updated_trade, status_for_webhook, {
                "trade_id": trade_id,
                "qr_aggregator": True, "resolved_from_dispute": True,
                "pending_completion": not completed,
            })
        except Exception as e:
            logger.error(f"[QR Dispute Resolve] Webhook error: {e}")

    elif resolution == "cancel" or resolution == "cancel_dispute":
        # --- CANCEL TRADE: unfreeze provider funds, no calculations ---
        if provider_id and total_freeze_usdt > 0:
            result = await db.qr_providers.update_one(
                {"id": provider_id, "frozen_usdt": {"$gte": total_freeze_usdt}},
                {"$inc": {"frozen_usdt": -total_freeze_usdt}}
            )
            if result.modified_count == 0:
                prov = await db.qr_providers.find_one({"id": provider_id})
                if prov:
                    new_frozen = max(0, prov.get("frozen_usdt", 0) - total_freeze_usdt)
                    await db.qr_providers.update_one(
                        {"id": provider_id},
                        {"$set": {"frozen_usdt": new_frozen}}
                    )
            logger.info(f"[QR Dispute Resolve] Unfrozen {total_freeze_usdt:.4f} USDT for provider {provider_id}")

        await db.trades.update_one(
            {"id": trade_id},
            {"$set": {
                "status": "cancelled", "cancelled_at": now,
                "dispute_resolved_at": now, "dispute_resolved_by": user["id"],
                "dispute_resolution": "cancelled",
            }}
        )

        if trade.get("invoice_id"):
            await db.merchant_invoices.update_one(
                {"id": trade["invoice_id"]}, {"$set": {"status": "cancelled"}}
            )

        message = f"Спор разрешён: сделка отменена. Средства провайдера разморожены. {resolve_reason}"

        # Webhook
        try:
            from routes.trades import send_merchant_webhook_on_trade
            await send_merchant_webhook_on_trade(trade, "cancelled", {
                "trade_id": trade_id, "cancelled_at": now,
                "qr_aggregator": True, "resolved_from_dispute": True,
            })
        except Exception as e:
            logger.error(f"[QR Dispute Resolve] Webhook error: {e}")

    else:
        raise HTTPException(status_code=400, detail="Invalid resolution")

    # Update conversation status
    await db.unified_conversations.update_one(
        {"related_id": trade_id, "type": "p2p_dispute"},
        {"$set": {
            "resolved": True, "resolved_at": now,
            "resolved_by": user["id"], "status": "resolved",
            "resolution_note": message
        }}
    )

    # Add system message
    conv = await db.unified_conversations.find_one({"related_id": trade_id, "type": "p2p_dispute"})
    if conv:
        await db.unified_messages.insert_one({
            "id": str(uuid.uuid4()), "conversation_id": conv["id"],
            "sender_id": "system", "sender_role": "system",
            "sender_name": "Система",
            "content": message,
            "is_system": True, "is_deleted": False, "created_at": now,
        })

    # Audit log
    await _audit_log_dispute("dispute_resolved", trade_id, user["id"], user.get("role", "admin"), {
        "resolution": resolution, "reason": resolve_reason
    })

    return {"status": "success", "resolution": resolution}


@router.get("/qr-aggregator/trades/{trade_id}/dispute-status")
async def get_qr_dispute_status(trade_id: str):
    """Get dispute status for a trade (public/authenticated)."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    dispute = await db.unified_conversations.find_one(
        {"related_id": trade_id, "type": "p2p_dispute"},
        {"_id": 0}
    )

    return {
        "has_dispute": bool(dispute),
        "dispute_status": dispute.get("status") if dispute else None,
        "resolved": dispute.get("resolved", False) if dispute else False,
        "trade_status": trade.get("status"),
        "can_open_dispute": _check_dispute_eligibility(trade)[0]
    }


@router.get("/qr-aggregator/provider/disputes")
async def get_provider_disputes(user: dict = Depends(get_current_user)):
    """Get disputes for the authenticated provider."""
    if user.get("role") != "qr_provider":
        raise HTTPException(status_code=403, detail="Only providers can access this")

    provider_id = user["id"]
    
    # Find trades where provider is involved AND has dispute
    trades = await db.trades.find({
        "provider_id": provider_id,
        "has_dispute": True
    }).sort("disputed_at", -1).to_list(100)
    
    result = []
    for t in trades:
        conv = await db.unified_conversations.find_one(
            {"related_id": t["id"], "type": "p2p_dispute"}
        )
        
        # Check for unread messages
        has_unread = False
        if conv:
            last_msg = await db.unified_messages.find_one(
                {"conversation_id": conv["id"]},
                sort=[("created_at", -1)]
            )
            if last_msg and not last_msg.get("read_by_provider"):
                has_unread = True
        
        result.append({
            "trade_id": t["id"],
            "transaction_id": t.get("trustgain_operation_id") or t.get("qr_operation_id"),
            "amount_usdt": t.get("amount_usdt"),
            "amount_rub": t.get("amount_rub"),
            "status": t.get("status"),
            "dispute_status": conv.get("status") if conv else "active",
            "created_at": t.get("created_at"),
            "disputed_at": t.get("disputed_at"),
            "merchant_id": t.get("merchant_id"),
            "has_unread": has_unread
        })
        
    return result


@router.get("/admin/qr-aggregator/disputes")
async def get_qr_disputes_admin(user: dict = Depends(require_admin_level(50))):
    """Admin: Get all QR aggregator disputes."""
    trades = await db.trades.find({
        "$or": [{"qr_aggregator_trade": True}, {"is_qr_aggregator": True}],
        "has_dispute": True
    }).sort("disputed_at", -1).to_list(100)
    
    result = []
    for t in trades:
        conv = await db.unified_conversations.find_one(
            {"related_id": t["id"], "type": "p2p_dispute"}
        )
        
        result.append({
            "trade_id": t["id"],
            "transaction_id": t.get("trustgain_operation_id"),
            "provider_id": t.get("provider_id"),
            "merchant_id": t.get("merchant_id"),
            "amount_usdt": t.get("amount_usdt"),
            "status": t.get("status"),
            "dispute_status": conv.get("status") if conv else "active",
            "disputed_at": t.get("disputed_at"),
            "disputed_by": t.get("disputed_by_role"),
        })
        
    return result


@router.get("/admin/qr-aggregator/dispute-logs/{trade_id}")
async def get_dispute_audit_log(trade_id: str, user: dict = Depends(require_admin_level(50))):
    """Admin: Get audit logs for a specific dispute."""
    logs = await db.dispute_audit_log.find({"trade_id": trade_id}).sort("created_at", -1).to_list(100)
    return logs


# --- Provider Chat Endpoints ---

@router.get("/qr-aggregator/provider/disputes/{trade_id}/chat")
async def get_provider_dispute_chat(trade_id: str, user: dict = Depends(get_current_user)):
    """Get chat messages for a dispute (Provider view)"""
    if user.get("role") != "qr_provider":
        raise HTTPException(status_code=403, detail="Only providers")
        
    # Verify provider owns this trade
    trade = await db.trades.find_one({"id": trade_id, "provider_id": user["id"]})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
        
    conv = await db.unified_conversations.find_one({"related_id": trade_id, "type": "p2p_dispute"})
    if not conv:
        return {"messages": []}
        
    messages = await db.unified_messages.find(
        {"conversation_id": conv["id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    # Mark as read
    await db.unified_messages.update_many(
        {"conversation_id": conv["id"], "read_by_provider": {"$ne": True}},
        {"$set": {"read_by_provider": True}}
    )
    
    return {"messages": messages, "conversation_id": conv["id"]}


@router.post("/qr-aggregator/provider/disputes/{trade_id}/chat")
async def provider_send_dispute_message(trade_id: str, body: dict = Body(...), user: dict = Depends(get_current_user)):
    """Send message to dispute chat (Provider)"""
    if user.get("role") != "qr_provider":
        raise HTTPException(status_code=403, detail="Only providers")
        
    trade = await db.trades.find_one({"id": trade_id, "provider_id": user["id"]})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
        
    conv = await db.unified_conversations.find_one({"related_id": trade_id, "type": "p2p_dispute"})
    if not conv:
        raise HTTPException(status_code=404, detail="Dispute not found")
        
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Empty message")
        
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": user["id"],
        "sender_role": "qr_provider",
        "sender_name": f"[Провайдер] {user.get('display_name', 'Provider')}",
        "content": content,
        "is_system": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_by_provider": True
    }
    
    await db.unified_messages.insert_one(msg)
    
    # Update conversation updated_at
    await db.unified_conversations.update_one(
        {"id": conv["id"]},
        {"$set": {"updated_at": msg["created_at"]}}
    )
    
    return msg
