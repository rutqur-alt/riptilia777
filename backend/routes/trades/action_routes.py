from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
import uuid

from core.database import db
from core.auth import require_role
from .utils import (
    _ws_broadcast, 
    send_merchant_webhook_on_trade, 
    _create_trade_notification
)

router = APIRouter()

@router.post("/trades/{trade_id}/confirm")
async def confirm_trade(trade_id: str, user: dict = Depends(require_role(["trader"]))):
    """Trader confirms payment received. Only allowed if client marked as paid or dispute."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade["trader_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your trade")
    
    # Trader can confirm ONLY if:
    # 1. Client marked as paid (status = "paid")
    # 2. Trade is in dispute (status = "disputed")
    if trade["status"] not in ["paid", "disputed"]:
        raise HTTPException(status_code=400, detail="Можно подтвердить только после оплаты клиентом")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update trade status
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "completed",
            "completed_at": now
        }}
    )
    
    # If direct P2P trade (trader-to-trader), credit USDT to buyer
    if trade.get("buyer_type") == "trader" and trade.get("buyer_id"):
        buyer_receives = trade["amount_usdt"]
        await db.traders.update_one(
            {"id": trade["buyer_id"]},
            {"$inc": {"balance_usdt": buyer_receives}}
        )
        # Notify buyer about balance update
        await _ws_broadcast(f"user_{trade['buyer_id']}", {
            "type": "balance_update",
            "amount": buyer_receives,
            "reason": "trade_completed"
        })
    # If merchant trade, transfer to merchant
    elif trade.get("merchant_id"):
        # Get merchant's commission rate (set by admin on approval)
        merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0})
        commission_rate = merchant.get("commission_rate", 10.0) if merchant else 10.0
        
        # Get original amount from invoice (what merchant requested, NOT what client paid)
        # This is the base for commission calculation
        original_amount_rub = None
        invoice_exchange_rate = None
        if trade.get("invoice_id"):
            invoice = await db.merchant_invoices.find_one({"id": trade["invoice_id"]}, {"_id": 0})
            if invoice:
                original_amount_rub = invoice.get("original_amount_rub")
                invoice_exchange_rate = invoice.get("exchange_rate")
        
        # Fallback to trade amounts if no invoice found
        if not original_amount_rub:
            original_amount_rub = trade.get("client_amount_rub") or trade.get("amount_rub", 0)
        
        # Use invoice exchange rate (fixed at creation) to avoid rate drift between
        # invoice creation and trade confirmation. Fallback to current rate if no invoice.
        if invoice_exchange_rate:
            base_rate = invoice_exchange_rate
        else:
            payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
            base_rate = payout_settings.get("base_rate", 78.5) if payout_settings else 78.5
        
        # Merchant receives: original_amount - commission%
        # Commission is calculated from ORIGINAL order amount, not what client paid
        merchant_receives_rub = original_amount_rub * (100 - commission_rate) / 100
        platform_fee_rub = original_amount_rub * commission_rate / 100
        merchant_receives_usdt = merchant_receives_rub / base_rate
        
        # Update trade with calculated amounts
        commission_usdt = platform_fee_rub / base_rate
        trader_comm = trade.get("trader_commission", 0)
        await db.trades.update_one(
            {"id": trade_id},
            {"$set": {
                "original_amount_rub": original_amount_rub,
                "merchant_commission_percent": commission_rate,
                "platform_fee_rub": platform_fee_rub,
                "merchant_receives_rub": merchant_receives_rub,
                "merchant_receives_usdt": merchant_receives_usdt,
                "merchant_commission": commission_usdt,
                "total_commission": round(trader_comm + commission_usdt, 4)
            }}
        )
        
        # Credit merchant balance and update commission paid
        await db.merchants.update_one(
            {"id": trade["merchant_id"]},
            {"$inc": {
                "balance_usdt": merchant_receives_usdt,
                "total_commission_paid": commission_usdt
            }}
        )
        
        # Update payment link status
        if trade.get("payment_link_id"):
            await db.payment_links.update_one(
                {"id": trade["payment_link_id"]},
                {"$set": {"status": "completed"}}
            )
        
        # Update invoice status to completed
        if trade.get("invoice_id"):
            await db.merchant_invoices.update_one(
                {"id": trade["invoice_id"]},
                {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
            )
    
    # Update offer's sold_usdt and actual_commission
    # Commission is already reserved in offer, no need to deduct from trader balance
    trader_commission = trade.get("trader_commission", 0)
    if trade.get("offer_id"):
        await db.offers.update_one(
            {"id": trade["offer_id"]},
            {"$inc": {
                "sold_usdt": trade["amount_usdt"],
                "actual_commission": trader_commission
            }}
        )
        # Log commission deduction from reserved funds
        if trader_commission > 0:
            await db.transactions.insert_one({
                "id": str(uuid.uuid4()),
                "trader_id": trade["trader_id"],
                "type": "commission",
                "amount": -trader_commission,
                "description": f"Комиссия 1% со сделки #{trade_id[:8]} ({trade['amount_usdt']:.2f} USDT) - из заморозки",
                "reference_trade_id": trade_id,
                "from_reserved": True,
                "created_at": now
            })
    
    # Process referral earnings
    referral_rate = 0.005  # 0.5%
    referral_amount = trade["amount_usdt"] * referral_rate
    
    # Case 1: Trader (seller) is referred → their referrer earns from sales
    seller = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0})
    if seller and seller.get("referred_by"):
        referrer = await db.traders.find_one({"id": seller["referred_by"]}, {"_id": 0})
        if referrer:
            await db.traders.update_one(
                {"id": seller["referred_by"]},
                {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
            )
            await db.transactions.insert_one({
                "id": str(uuid.uuid4()),
                "trader_id": seller["referred_by"],
                "type": "referral_bonus",
                "amount": referral_amount,
                "description": f"Реферальный бонус от сделки #{trade_id[:8]}",
                "from_platform": True,
                "reference_trade_id": trade_id,
                "referred_user_id": seller["id"],
                "created_at": now
            })
        else:
            # Check if referrer is merchant
            referrer = await db.merchants.find_one({"id": seller["referred_by"]}, {"_id": 0})
            if referrer:
                await db.merchants.update_one(
                    {"id": seller["referred_by"]},
                    {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                )
                await db.transactions.insert_one({
                    "id": str(uuid.uuid4()),
                    "merchant_id": seller["referred_by"],
                    "type": "referral_bonus",
                    "amount": referral_amount,
                    "description": f"Реферальный бонус от сделки #{trade_id[:8]}",
                    "from_platform": True,
                    "reference_trade_id": trade_id,
                    "referred_user_id": seller["id"],
                    "created_at": now
                })
    
    # Case 2: Merchant is referred → their referrer earns from purchases
    if trade.get("merchant_id"):
        merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0})
        if merchant and merchant.get("referred_by"):
            referrer = await db.traders.find_one({"id": merchant["referred_by"]}, {"_id": 0})
            if referrer:
                await db.traders.update_one(
                    {"id": merchant["referred_by"]},
                    {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                )
                await db.transactions.insert_one({
                    "id": str(uuid.uuid4()),
                    "trader_id": merchant["referred_by"],
                    "type": "referral_bonus",
                    "amount": referral_amount,
                    "description": f"Реферальный бонус от сделки #{trade_id[:8]}",
                    "from_platform": True,
                    "reference_trade_id": trade_id,
                    "referred_user_id": merchant["id"],
                    "created_at": now
                })
            else:
                referrer = await db.merchants.find_one({"id": merchant["referred_by"]}, {"_id": 0})
                if referrer:
                    await db.merchants.update_one(
                        {"id": merchant["referred_by"]},
                        {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                    )
                    await db.transactions.insert_one({
                        "id": str(uuid.uuid4()),
                        "merchant_id": merchant["referred_by"],
                        "type": "referral_bonus",
                        "amount": referral_amount,
                        "description": f"Реферальный бонус от сделки #{trade_id[:8]}",
                        "from_platform": True,
                        "reference_trade_id": trade_id,
                        "referred_user_id": merchant["id"],
                        "created_at": now
                    })
    
    # Process multi-level referral bonuses (3 levels: 5%, 3%, 1%)
    # Based on trader's commission from the trade
    trader_commission = trade.get("trader_commission", 0)
    if trader_commission > 0:
        try:
            from routes.referral import process_referral_bonus
            await process_referral_bonus(trade["trader_id"], trader_commission)
        except Exception as e:
            # Log but don't fail the trade
            print(f"Referral bonus error: {e}")
    
    # Update unified conversation
    await db.unified_conversations.update_one(
        {"$or": [
            {"related_id": trade_id, "type": "p2p_trade"},
            {"related_id": trade_id, "type": "p2p_dispute"}
        ]},
        {"$set": {
            "status": "completed",
            "resolved": True,
            "resolved_at": now,
            "archived": True
        }}
    )
    
    # Send system message about completion - разное сообщение для мерчант клиента и P2P
    is_merchant_trade = trade.get("payment_link_id") or trade.get("merchant_id")
    if is_merchant_trade:
        # Для клиента мерчанта - не показываем USDT
        completion_text = f"✅ Сделка завершена! Оплата подтверждена. Средства зачислены."
    else:
        # Для P2P сделки - показываем USDT
        completion_text = f"✅ Сделка завершена! Продавец подтвердил получение оплаты. {trade['amount_usdt']} USDT переведены покупателю."
    
    confirm_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "sender_role": "system",
        "content": completion_text,
        "created_at": now
    }
    await db.trade_messages.insert_one(confirm_msg)
    
    # Broadcast via WebSocket to both parties
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in confirm_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "completed", "trade_id": trade_id})
    
    # Also notify buyer directly
    if trade.get("buyer_id"):
        await _ws_broadcast(f"user_{trade['buyer_id']}", {
            "type": "trade_completed",
            "trade_id": trade_id,
            "amount_usdt": trade["amount_usdt"],
            "status": "completed"
        })
    
    # Send webhook to merchant (COMPLETED)
    # Re-read trade to get freshly calculated merchant_receives_usdt
    updated_trade = await db.trades.find_one({"id": trade_id}, {"_id": 0}) or trade
    # Get base_rate for webhook (may have been calculated above for merchant trades)
    payout_settings_for_wh = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    wh_base_rate = payout_settings_for_wh.get("base_rate", 78.5) if payout_settings_for_wh else 78.5
    await send_merchant_webhook_on_trade(updated_trade, "completed", {
        "trade_id": trade_id,
        "amount_usdt": updated_trade.get("amount_usdt", trade["amount_usdt"]),
        "client_amount_rub": updated_trade.get("client_amount_rub"),
        "merchant_receives_rub": updated_trade.get("merchant_receives_rub"),
        "merchant_receives_usdt": updated_trade.get("merchant_receives_usdt"),
        "rate": wh_base_rate,
        "merchant_amount_usdt": updated_trade.get("merchant_receives_usdt"),
        "completed_at": now
    })
    
    # Create event notifications for both parties
    if trade.get("trader_id"):
        await _create_trade_notification(
            trade["trader_id"], 
            "trade_completed",
            "Сделка завершена",
            f"Сделка на {trade['amount_usdt']:.2f} USDT успешно завершена",
            f"/trader/sales/{trade_id}",
            trade_id
        )
    if trade.get("buyer_id") and trade.get("buyer_type") == "trader":
        await _create_trade_notification(
            trade["buyer_id"],
            "trade_completed", 
            "Сделка завершена",
            f"Сделка на {trade['amount_usdt']:.2f} USDT успешно завершена",
            f"/trader/purchases/{trade_id}",
            trade_id
        )
    
    return {"status": "completed"}


@router.post("/trades/{trade_id}/mark-paid")
async def mark_trade_paid(trade_id: str):
    """Mark a trade as paid by customer (no auth required for customer)"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade["status"] != "pending":
        raise HTTPException(status_code=400, detail="Trade not pending")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {"status": "paid", "paid_at": now}}
    )
    
    # Send system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": f"✅ Клиент подтвердил оплату {trade['amount_rub']:,.0f} ₽. Трейдер, проверьте поступление средств на ваши реквизиты.",
        "created_at": now
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Broadcast via WebSocket to trade channel
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in system_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "paid", "trade_id": trade_id})
    
    # Also broadcast to trader's user channel for immediate notification
    await _ws_broadcast(f"user_{trade['trader_id']}", {
        "type": "trade_status_update",
        "trade_id": trade_id,
        "status": "paid",
        "message": f"Клиент оплатил сделку {trade_id[:12]}"
    })
    
    # Create notification for trader about payment
    try:
        await _create_trade_notification(
            user_id=trade["trader_id"],
            notif_type="trade_payment",
            title="Оплата получена",
            message=f"Клиент оплатил сделку на {trade['amount_rub']:,.0f} \u20bd",
            link=f"/trader/sales/{trade_id}"
        )
    except Exception:
        pass
    
    # Send webhook to merchant (PAID)
    await send_merchant_webhook_on_trade(trade, "paid", {
        "trade_id": trade_id,
        "paid_at": now
    })
    
    return {"status": "paid"}


@router.post("/trades/{trade_id}/cancel")
async def cancel_trade(trade_id: str, user: dict = Depends(require_role(["trader"]))):
    """Trader can cancel ONLY if pending and 30 minutes passed without payment."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade["trader_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your trade")
    
    if trade["status"] != "pending":
        raise HTTPException(status_code=400, detail="Отменить можно только если клиент не оплатил")
    
    created_at = datetime.fromisoformat(trade["created_at"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    minutes_passed = (now - created_at).total_seconds() / 60
    
    if minutes_passed < 30:
        remaining = int(30 - minutes_passed)
        raise HTTPException(status_code=400, detail=f"Отменить можно через {remaining} мин. если клиент не оплатит")
    
    # Return funds
    if trade.get("offer_id"):
        await db.offers.update_one(
            {"id": trade["offer_id"]},
            {"$inc": {"available_usdt": trade["amount_usdt"]}}
        )
    else:
        await db.traders.update_one(
            {"id": trade["trader_id"]},
            {"$inc": {"balance_usdt": trade["amount_usdt"]}}
        )
        # Notify seller about refund
        await _ws_broadcast(f"user_{trade['trader_id']}", {
            "type": "balance_update",
            "amount": trade["amount_usdt"],
            "reason": "trade_cancelled"
        })
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {"status": "cancelled", "cancelled_at": now.isoformat()}}
    )
    
    # Update invoice status to cancelled
    if trade.get("invoice_id"):
        await db.merchant_invoices.update_one(
            {"id": trade["invoice_id"]},
            {"$set": {"status": "cancelled", "cancelled_at": now.isoformat()}}
        )
    
    # System message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": "❌ Сделка отменена трейдером (клиент не оплатил в течение 30 минут).",
        "created_at": now.isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Broadcast via WebSocket
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in system_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "cancelled", "trade_id": trade_id})
    
    # Send webhook to merchant (CANCELLED)
    await send_merchant_webhook_on_trade(trade, "cancelled", {
        "trade_id": trade_id,
        "reason": "Клиент не оплатил в течение 30 минут",
        "cancelled_at": now.isoformat()
    })
    
    # Create event notifications for both parties
    if trade.get("trader_id"):
        await _create_trade_notification(
            trade["trader_id"],
            "trade_cancelled",
            "Сделка отменена",
            f"Сделка на {trade['amount_usdt']:.2f} USDT была отменена",
            f"/trader/sales/{trade_id}",
            trade_id
        )
    if trade.get("buyer_id") and trade.get("buyer_type") == "trader":
        await _create_trade_notification(
            trade["buyer_id"],
            "trade_cancelled",
            "Сделка отменена",
            f"Сделка на {trade['amount_usdt']:.2f} USDT была отменена",
            f"/trader/purchases/{trade_id}",
            trade_id
        )
    
    return {"status": "cancelled"}


@router.post("/trades/{trade_id}/cancel-client")
async def cancel_trade_client(trade_id: str):
    """Client can cancel trade at any time (pending, paid, disputed)."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Client can cancel at any active status
    if trade["status"] in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Сделка уже завершена или отменена.")
    
    # Return funds
    if trade.get("offer_id"):
        # Trade from offer - return to offer's available_usdt
        await db.offers.update_one(
            {"id": trade["offer_id"]},
            {"$inc": {"available_usdt": trade["amount_usdt"]}}
        )
    else:
        # Direct trade - return to trader's balance
        await db.traders.update_one(
            {"id": trade["trader_id"]},
            {"$inc": {"balance_usdt": trade["amount_usdt"]}}
        )
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat(), "cancelled_by": "client"}}
    )
    
    # Update invoice status to cancelled
    if trade.get("invoice_id"):
        await db.merchant_invoices.update_one(
            {"id": trade["invoice_id"]},
            {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    # System message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": "❌ Сделка отменена покупателем.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Broadcast via WebSocket
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in system_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "cancelled", "trade_id": trade_id})
    
    # Notify trader that client cancelled the trade
    if trade.get("trader_id"):
        await _create_trade_notification(
            user_id=trade["trader_id"],
            notif_type="trade_cancelled",
            title="Сделка отменена",
            message=f"Покупатель отменил сделку на {trade['amount_usdt']:.2f} USDT",
            link=f"/trader/sales/{trade_id}",
            trade_id=trade_id
        )
    
    # Send webhook to merchant if applicable
    if trade.get("merchant_id"):
        await send_merchant_webhook_on_trade(trade, "cancelled", {
            "trade_id": trade_id,
            "reason": "Отменено покупателем",
            "cancelled_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {"status": "cancelled"}
