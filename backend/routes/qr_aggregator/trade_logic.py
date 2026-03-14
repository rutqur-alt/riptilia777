from datetime import datetime, timezone
import logging

from core.database import db

from .utils import get_base_rate
from .dispute_utils import _audit_log_dispute

# Import from other modules (external dependencies)
# We use lazy imports or direct imports if no circular dependency
from routes.trades import send_merchant_webhook_on_trade

logger = logging.getLogger(__name__)


async def _complete_qr_trade(operation: dict, provider_id: str):
    """
    Complete a QR aggregator trade when payment is confirmed by TrustGain.
    
    Distribution logic:
    - Exchange trade (no merchant): volume_usdt -> buyer wallet, platform_commission -> platform
    - Merchant trade: (volume - merchant_fee) -> merchant, merchant_fee -> platform, platform_commission -> platform
    
    Provider balance: unfreeze total_freeze, deduct total_freeze from balance
    """
    trade_id = operation.get("trade_id")
    if not trade_id:
        return

    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade or trade["status"] in ("completed",):
        return

    now = datetime.now(timezone.utc).isoformat()
    base_rate = await get_base_rate()
    was_disputed = trade.get("status") == "disputed"

    # Mark trade completed (handle disputed trades too — auto-close dispute per spec)
    if trade["status"] in ("pending", "disputed"):
        await db.trades.update_one(
            {"id": trade_id}, {"$set": {"status": "paid", "paid_at": now}}
        )

    result = await db.trades.update_one(
        {"id": trade_id, "status": {"$in": ["paid", "pending", "disputed"]}},
        {"$set": {"status": "completed", "completed_at": now}}
    )
    if result.modified_count == 0:
        return

    # Auto-close dispute if trade was disputed (per spec: provider callback auto-resolves)
    if was_disputed:
        await db.unified_conversations.update_one(
            {"related_id": trade_id, "type": "p2p_dispute"},
            {"$set": {
                "resolved": True, "resolved_at": now,
                "resolved_by": "system_auto", "status": "resolved",
            }}
        )
        conv = await db.unified_conversations.find_one(
            {"related_id": trade_id, "type": "p2p_dispute"}, {"_id": 0}
        )
        if conv:
            import uuid
            await db.unified_messages.insert_one({
                "id": str(uuid.uuid4()), "conversation_id": conv["id"],
                "sender_id": "system", "sender_role": "system",
                "sender_name": "Система",
                "content": "Спор автоматически закрыт: провайдер подтвердил оплату. Сделка завершена.",
                "is_system": True, "is_deleted": False, "created_at": now,
            })
        await _audit_log_dispute("dispute_auto_closed", trade_id, "system", "system", {
            "reason": "provider_callback_completed"
        })
        logger.info(f"[QR Dispute] Auto-closed dispute for trade {trade_id} (provider callback)")


    amount_usdt = trade.get("amount_usdt", 0)
    amount_rub = operation.get("amount_rub", 0)
    platform_commission_usdt = trade.get("platform_commission_usdt", 0)
    total_freeze_usdt = trade.get("total_freeze_usdt", 0)

    # If old trade without new fields, calculate from scratch
    if total_freeze_usdt == 0 and amount_usdt > 0:
        platform_markup_pct = trade.get("platform_markup_pct", 5.0)
        platform_commission_usdt = round(amount_usdt * platform_markup_pct / 100, 6)
        total_freeze_usdt = round(amount_usdt + platform_commission_usdt, 6)

    # ---- DISTRIBUTION ----
    platform_total_usdt = platform_commission_usdt  # Platform always gets its markup commission

    if trade.get("merchant_id"):
        # MERCHANT TRADE: client pays on merchant site
        merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0})
        if merchant:
            merchant_commission_rate = merchant.get("commission_rate", 5.0)  # e.g. 5%
            original_amount_rub = amount_rub

            if trade.get("invoice_id"):
                invoice = await db.merchant_invoices.find_one({"id": trade["invoice_id"]}, {"_id": 0})
                if invoice:
                    original_amount_rub = invoice.get("original_amount_rub", amount_rub)

            # Merchant commission in USDT
            merchant_commission_usdt = round(amount_usdt * merchant_commission_rate / 100, 6)
            merchant_receives_usdt = round(amount_usdt - merchant_commission_usdt, 6)

            # Platform gets: platform_markup_commission + merchant_commission
            platform_total_usdt = round(platform_commission_usdt + merchant_commission_usdt, 6)

            # Calculate RUB equivalents for consistency with regular trades
            platform_fee_rub = round(original_amount_rub * merchant_commission_rate / 100, 2)
            merchant_receives_rub = round(original_amount_rub - platform_fee_rub, 2)

            await db.trades.update_one(
                {"id": trade_id},
                {"$set": {
                    "original_amount_rub": original_amount_rub,
                    "merchant_receives_usdt": merchant_receives_usdt,
                    "merchant_commission_usdt": merchant_commission_usdt,
                    "merchant_commission": merchant_commission_usdt,
                    "merchant_commission_percent": merchant_commission_rate,
                    "merchant_receives_rub": merchant_receives_rub,
                    "platform_fee_rub": platform_fee_rub,
                    "platform_receives_usdt": platform_total_usdt,
                    "qr_aggregator_trade": True,
                }}
            )

            # Credit merchant
            await db.merchants.update_one(
                {"id": trade["merchant_id"]},
                {"$inc": {
                    "balance_usdt": merchant_receives_usdt,
                    "total_commission_paid": merchant_commission_usdt
                }}
            )

            logger.info(f"[QR Trade] Merchant {trade['merchant_id']} credited {merchant_receives_usdt:.4f} USDT "
                       f"(volume={amount_usdt}, merchant_fee={merchant_commission_usdt})")
    else:
        # EXCHANGE TRADE: user buys in order book
        # Buyer gets amount_usdt credited to their wallet
        buyer_id = trade.get("buyer_id")
        if buyer_id:
            # Credit buyer's USDT balance
            buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0})
            if not buyer:
                buyer = await db.traders.find_one({"id": buyer_id}, {"_id": 0})

            if buyer:
                # Credit via traders collection (main balance)
                await db.traders.update_one(
                    {"id": buyer_id},
                    {"$inc": {"balance_usdt": amount_usdt}}
                )
                logger.info(f"[QR Trade] Buyer {buyer_id} credited {amount_usdt:.4f} USDT")

        await db.trades.update_one(
            {"id": trade_id},
            {"$set": {
                "platform_receives_usdt": platform_total_usdt,
                "buyer_receives_usdt": amount_usdt,
                "qr_aggregator_trade": True,
            }}
        )

    # ---- PROVIDER BALANCE: unfreeze + deduct ----
    # Atomic: unfreeze and deduct from balance, prevent negative values
    result = await db.qr_providers.update_one(
        {"id": provider_id, "frozen_usdt": {"$gte": total_freeze_usdt}, "balance_usdt": {"$gte": total_freeze_usdt}},
        {"$inc": {
            "frozen_usdt": -total_freeze_usdt,
            "balance_usdt": -total_freeze_usdt,
            "active_operations_count": -1,
        }}
    )
    if result.modified_count == 0:
        # Fallback: force correct values (never go negative)
        provider_now = await db.qr_providers.find_one({"id": provider_id})
        if provider_now:
            new_frozen = max(0, provider_now.get("frozen_usdt", 0) - total_freeze_usdt)
            new_balance = max(0, provider_now.get("balance_usdt", 0) - total_freeze_usdt)
            new_active = max(0, provider_now.get("active_operations_count", 0) - 1)
            await db.qr_providers.update_one(
                {"id": provider_id},
                {"$set": {"frozen_usdt": new_frozen, "balance_usdt": new_balance, "active_operations_count": new_active}}
            )
        logger.warning(f"[QR Trade] Balance correction for provider {provider_id} on complete (trade {trade_id})")
    else:
        logger.info(f"[QR Trade] Provider {provider_id}: unfrozen and deducted {total_freeze_usdt:.4f} USDT")

    # ---- PLATFORM BALANCE: credit platform earnings ----
    await db.settings.update_one(
        {"type": "platform_balance"},
        {"$inc": {"balance_usdt": platform_total_usdt}},
        upsert=True
    )
    logger.info(f"[QR Trade] Platform credited {platform_total_usdt:.4f} USDT")

    # Update invoice / payment link
    if trade.get("invoice_id"):
        await db.merchant_invoices.update_one(
            {"id": trade["invoice_id"]}, {"$set": {"status": "completed", "completed_at": now}}
        )
    if trade.get("payment_link_id"):
        await db.payment_links.update_one(
            {"id": trade["payment_link_id"]}, {"$set": {"status": "completed"}}
        )

    # Record transaction
    from services.realtime_events import emit_balance_update, emit_trade_update
    await db.transactions.insert_one({
        "id": f"tx_{trade_id}_complete",
        "type": "qr_trade_completion",
        "amount_usdt": amount_usdt,
        "amount_rub": amount_rub,
        "trade_id": trade_id,
        "provider_id": provider_id,
        "merchant_id": trade.get("merchant_id"),
        "buyer_id": trade.get("buyer_id"),
        "platform_commission": platform_total_usdt,
        "created_at": now
    })

    # Webhook to merchant
    try:
        updated_trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
        await send_merchant_webhook_on_trade(updated_trade, "completed", {
            "trade_id": trade_id,
            "qr_aggregator": True,
            "rate": base_rate,
            "merchant_amount_usdt": updated_trade.get("merchant_receives_usdt"),
            "merchant_receives_rub": updated_trade.get("merchant_receives_rub"),
            "completed_at": now
        })
    except Exception as e:
        logger.error(f"[QR Trade] Webhook error: {e}")

    # Realtime updates
    if trade.get("buyer_id"):
        await emit_balance_update(trade["buyer_id"])
    if trade.get("merchant_id"):
        await emit_balance_update(trade["merchant_id"])
    await emit_trade_update(trade_id, "completed")


async def _set_pending_completion(trade: dict, provider_id: str):
    """Set trade to pending_completion status due to insufficient provider balance"""
    trade_id = trade["id"]
    now = datetime.now(timezone.utc).isoformat()
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "pending_completion",
            "pending_completion_at": now,
            "status_message": "Оплата подтверждена. Ожидание баланса провайдера для завершения сделки."
        }}
    )
    
    # Also update operation status
    await db.qr_provider_operations.update_one(
        {"trade_id": trade_id},
        {"$set": {"status": "pending_completion"}}
    )
    
    logger.warning(f"[QR Trade] Trade {trade_id} set to pending_completion (insufficient provider balance)")
    
    # Notify merchant via webhook about pending completion?
    # Spec says: "If provider balance insufficient -> clock icon, wait".
    # We might send a webhook with status "pending_completion" if needed, but for now we wait.


async def _try_complete_trade_with_balance_check(trade: dict, provider_id: str, source: str = "unknown") -> bool:
    """
    Try to complete a trade, but check provider balance first.
    If balance insufficient -> set to pending_completion.
    If balance sufficient -> complete trade.
    Returns True if completed, False if pending.
    """
    if not provider_id:
        provider_id = trade.get("provider_id")
    
    if not provider_id:
        logger.error(f"[QR Trade] Cannot complete trade {trade['id']}: no provider_id")
        return False
        
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        logger.error(f"[QR Trade] Provider {provider_id} not found")
        return False
        
    total_freeze_usdt = trade.get("total_freeze_usdt", 0)
    
    # Check if funds are already frozen for this trade (e.g. active trade)
    # If trade was cancelled, funds were unfrozen. If pending/paid, they are frozen.
    # We need to know if we need to DEDUCT from available or just use frozen.
    
    # Logic:
    # 1. If trade is active (paid/pending) -> funds are frozen. We just need to check if they exist (sanity check).
    # 2. If trade is cancelled -> funds were unfrozen. We need to check if provider has enough FREE balance to cover.
    # 3. If trade is pending_completion -> funds are NOT frozen (we couldn't freeze them). Check free balance.
    
    status = trade.get("status")
    balance_usdt = provider.get("balance_usdt", 0)
    frozen_usdt = provider.get("frozen_usdt", 0)
    available_usdt = balance_usdt - frozen_usdt
    
    can_complete = False
    
    if status in ("pending", "paid", "disputed") and not trade.get("dispute_freeze_applied"):
        # Funds should be frozen. Check if we have enough total balance.
        # Actually, if they are frozen, they are in frozen_usdt.
        # _complete_qr_trade deducts from balance and frozen.
        # So we just need balance >= total_freeze.
        if balance_usdt >= total_freeze_usdt:
            can_complete = True
    else:
        # Cancelled or pending_completion or disputed-with-unfreeze
        # Funds are NOT frozen for this trade (or were re-frozen for dispute).
        # If cancelled -> need available balance.
        # If pending_completion -> need available balance.
        
        # For cancelled trade auto-approve: we need to re-freeze and then complete.
        # So we need available >= total_freeze.
        
        if available_usdt >= total_freeze_usdt:
            # Re-freeze first to satisfy _complete_qr_trade expectation
            await db.qr_providers.update_one(
                {"id": provider_id},
                {"$inc": {"frozen_usdt": total_freeze_usdt}}
            )
            can_complete = True
    
    if can_complete:
        # Get operation data for amount_rub
        operation = await db.qr_provider_operations.find_one({"trade_id": trade["id"]})
        if not operation:
            # Fallback if operation missing (should not happen)
            operation = {"trade_id": trade["id"], "amount_rub": trade.get("amount_rub", 0)}
            
        await _complete_qr_trade(operation, provider_id)
        return True
    else:
        await _set_pending_completion(trade, provider_id)
        return False


async def _process_pending_completions(provider_id: str) -> int:
    """
    Process trades in pending_completion status for a provider.
    Called when provider balance is updated.
    Returns number of completed trades.
    """
    pending_trades = await db.trades.find({
        "provider_id": provider_id,
        "status": "pending_completion"
    }).sort("created_at", 1).to_list(100)
    
    completed_count = 0
    for trade in pending_trades:
        # Try to complete each one
        if await _try_complete_trade_with_balance_check(trade, provider_id, source="process_pending"):
            completed_count += 1
            
    if completed_count > 0:
        logger.info(f"[QR Admin] Processed {completed_count} pending trades for provider {provider_id}")
        
    return completed_count


async def _cancel_qr_trade(operation: dict):
    """
    Cancel a QR trade (e.g. on timeout or rejection).
    Unfreeze provider funds.
    """
    trade_id = operation.get("trade_id")
    if not trade_id:
        return

    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade or trade["status"] in ("completed", "cancelled"):
        return

    now = datetime.now(timezone.utc).isoformat()
    provider_id = trade.get("provider_id")
    total_freeze_usdt = trade.get("total_freeze_usdt", 0)

    # Update trade status
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {"status": "cancelled", "cancelled_at": now, "cancel_reason": "qr_payment_failed"}}
    )
    
    # Update invoice status if exists
    if trade.get("invoice_id"):
        await db.merchant_invoices.update_one(
            {"id": trade["invoice_id"]}, {"$set": {"status": "cancelled"}}
        )

    # Unfreeze provider funds
    if provider_id and total_freeze_usdt > 0:
        # Atomic unfreeze
        result = await db.qr_providers.update_one(
            {"id": provider_id, "frozen_usdt": {"$gte": total_freeze_usdt}},
            {"$inc": {
                "frozen_usdt": -total_freeze_usdt,
                "active_operations_count": -1
            }}
        )
        if result.modified_count == 0:
            # Fallback fix
            provider = await db.qr_providers.find_one({"id": provider_id})
            if provider:
                new_frozen = max(0, provider.get("frozen_usdt", 0) - total_freeze_usdt)
                new_active = max(0, provider.get("active_operations_count", 0) - 1)
                await db.qr_providers.update_one(
                    {"id": provider_id},
                    {"$set": {"frozen_usdt": new_frozen, "active_operations_count": new_active}}
                )
        
        logger.info(f"[QR Trade] Cancelled {trade_id}, unfrozen {total_freeze_usdt:.4f} USDT")

    # Webhook to merchant
    try:
        await send_merchant_webhook_on_trade(trade, "cancelled", {
            "trade_id": trade_id,
            "qr_aggregator": True,
            "cancelled_at": now
        })
    except Exception as e:
        logger.error(f"[QR Trade] Webhook error: {e}")
    
    # Realtime update
    from services.realtime_events import emit_trade_update
    await emit_trade_update(trade_id, "cancelled")
