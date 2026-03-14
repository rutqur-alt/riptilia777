from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import get_current_user, require_role
from .utils import (
    _ws_broadcast, 
    send_merchant_webhook_on_trade, 
    _create_trade_notification
)

router = APIRouter()

@router.post("/trades/{trade_id}/dispute")
async def open_dispute(trade_id: str, reason: str = "", user: dict = Depends(get_current_user)):
    """Open a dispute. Trader can open immediately after payment, client after 10 minutes."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Check if dispute is already open
    if trade["status"] == "disputed":
        raise HTTPException(status_code=400, detail="Спор уже открыт")
    
    # Only paid trades can be disputed
    if trade["status"] != "paid":
        raise HTTPException(status_code=400, detail="Спор можно открыть только после оплаты")
    
    # Trader can open dispute immediately, merchant immediately, client after 10 minutes
    is_seller = user and user.get("role") == "trader" and user.get("id") == trade.get("trader_id")
    is_buyer = user and user.get("role") == "trader" and user.get("id") == trade.get("buyer_id")
    is_merchant = user and user.get("role") == "merchant" and user.get("id") == trade.get("merchant_id")
    
    if not is_seller and not is_merchant:
        # Buyer/Client needs to wait 10 minutes
        paid_at = trade.get("paid_at")
        if paid_at:
            paid_time = datetime.fromisoformat(paid_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            minutes_passed = (now - paid_time).total_seconds() / 60
            
            if minutes_passed < 10:
                remaining = int(10 - minutes_passed)
                raise HTTPException(status_code=400, detail=f"Спор можно открыть через {remaining} мин.")
    
    # Determine who opened dispute
    if is_seller:
        opener = "продавцом"
    elif is_merchant:
        opener = "мерчантом"
    elif is_buyer:
        opener = "покупателем"
    else:
        opener = "клиентом"
    
    # Update trade status to disputed
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "disputed",
            "disputed_at": datetime.now(timezone.utc).isoformat(),
            "dispute_reason": reason or "Не указана",
            "disputed_by": user.get("id") if user else "client",
            "disputed_by_role": opener
        }}
    )
    
    # Send system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "is_system": True,
        "sender_role": "system",
        "content": f"⚠️ Спор открыт {opener}! Причина: {reason or 'не указана'}. Администратор подключится к чату.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "disputed", "trade_id": trade_id})
    
    # Create notification for participants about dispute (using event_notifications)
    try:
        participants = set()
        if trade.get("trader_id"):
            participants.add(trade["trader_id"])
        if trade.get("buyer_id"):
            participants.add(trade["buyer_id"])
        if user and user.get("id"):
            participants.discard(user["id"])
        
        for pid in participants:
            # Create in event_notifications (new system)
            await db.event_notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": pid,
                "type": "trade_disputed",
                "title": "Спор по сделке",
                "message": f"Открыт спор по сделке #{trade_id[:8]} на {trade.get('amount_usdt', 0):.2f} USDT",
                "link": f"/trader/sales/{trade_id}",
                "reference_id": trade_id,
                "reference_type": "trade_dispute",
                "extra_data": {"reason": reason or "Не указана"},
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            # Also create in old system for backward compatibility
            await _create_trade_notification(
                user_id=pid,
                notif_type="trade_disputed",
                title="Спор открыт",
                message=f"Открыт спор по сделке #{trade_id[:8]}",
                link=f"/trader/sales/{trade_id}",
                trade_id=trade_id
            )
            # Real-time WebSocket notification
            await _ws_broadcast(f"user_{pid}", {
                "type": "new_notification",
                "notification": {
                    "id": str(uuid.uuid4()),
                    "type": "trade_disputed",
                    "title": "Спор по сделке",
                    "message": f"Открыт спор по сделке #{trade_id[:8]}",
                    "link": f"/trader/sales/{trade_id}"
                }
            })
    except Exception:
        pass
    
    # Create notification for MERCHANT about dispute
    if trade.get("merchant_id"):
        try:
            await db.event_notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": trade["merchant_id"],
                "type": "trade_disputed",
                "title": "Спор по сделке",
                "message": f"Открыт спор по сделке #{trade_id[:8]} на {trade.get('amount_usdt', 0):.2f} USDT",
                "link": "/merchant/payments",
                "reference_id": trade_id,
                "reference_type": "trade_dispute",
                "extra_data": {"reason": reason or "Не указана"},
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            # Real-time WebSocket notification for merchant
            await _ws_broadcast(f"user_{trade['merchant_id']}", {
                "type": "new_notification",
                "notification": {
                    "id": str(uuid.uuid4()),
                    "type": "trade_disputed",
                    "title": "Спор по сделке",
                    "message": f"Открыт спор по сделке #{trade_id[:8]}",
                    "link": "/merchant/payments"
                }
            })
        except Exception:
            pass
    
    # Send webhook to merchant (DISPUTED)
    await send_merchant_webhook_on_trade(trade, "disputed", {
        "trade_id": trade_id,
        "reason": reason or "Не указана",
        "disputed_at": datetime.now(timezone.utc).isoformat(),
        "disputed_by": opener
    })
    
    return {"status": "disputed"}


@router.post("/trades/{trade_id}/dispute-public")
async def open_dispute_public(trade_id: str, reason: str = ""):
    """Open a dispute by client (no auth) - only after 10 minutes since payment."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Check if dispute is already open
    if trade["status"] == "disputed":
        raise HTTPException(status_code=400, detail="Спор уже открыт")
    
    if trade["status"] != "paid":
        raise HTTPException(status_code=400, detail="Спор можно открыть только после оплаты")
    
    paid_at = trade.get("paid_at")
    if paid_at:
        paid_time = datetime.fromisoformat(paid_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        minutes_passed = (now - paid_time).total_seconds() / 60
        
        if minutes_passed < 10:
            remaining = int(10 - minutes_passed)
            raise HTTPException(status_code=400, detail=f"Спор можно открыть через {remaining} мин.")
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "disputed",
            "disputed_at": datetime.now(timezone.utc).isoformat(),
            "dispute_reason": reason or "Не указана",
            "disputed_by": "client",
            "disputed_by_role": "клиентом"
        }}
    )
    
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "is_system": True,
        "sender_role": "system",
        "content": f"⚠️ Спор открыт клиентом! Причина: {reason or 'не указана'}. Администратор подключится к чату.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Send webhook to merchant (DISPUTED)
    await send_merchant_webhook_on_trade(trade, "disputed", {
        "trade_id": trade_id,
        "reason": reason or "Не указана",
        "disputed_at": datetime.now(timezone.utc).isoformat(),
        "disputed_by": "клиентом"
    })
    
    return {"status": "disputed"}


@router.post("/trades/{trade_id}/resolve-dispute")
async def resolve_dispute(trade_id: str, resolution: str, user: dict = Depends(require_role(["admin"]))):
    """Resolve a dispute (admin only)
    - favor_client: Complete the trade (buyer gets USDT)
    - favor_trader: Cancel the trade (seller keeps USDT)
    """
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade["status"] not in ["disputed", "dispute"]:
        raise HTTPException(status_code=400, detail="Trade not in dispute")
    
    if resolution in ["favor_client", "refund_buyer", "favor_buyer"]:
        # Complete the trade - buyer wins, trade is completed
        new_status = "completed"
        
        # Update offer's sold_usdt if trade was from offer
        if trade.get("offer_id"):
            await db.offers.update_one(
                {"id": trade["offer_id"]},
                {"$inc": {
                    "sold_usdt": trade["amount_usdt"],
                    "actual_commission": trade["trader_commission"]
                }}
            )
        
        # Deduct commission from seller (1%)
        trader_commission_amt = trade.get("trader_commission", 0)
        if trader_commission_amt > 0:
            await db.traders.update_one(
                {"id": trade["trader_id"]},
                {"$inc": {"balance_usdt": -trader_commission_amt}}
            )
            now_ts = datetime.now(timezone.utc).isoformat()
            await db.transactions.insert_one({
                "id": str(uuid.uuid4()),
                "trader_id": trade["trader_id"],
                "type": "commission",
                "amount": -trader_commission_amt,
                "description": f"Комиссия площадки 1% со сделки #{trade_id[:8]} (спор)",
                "reference_trade_id": trade_id,
                "created_at": now_ts
            })
        
        # Record commission payment
        await db.commission_payments.insert_one({
            "id": str(uuid.uuid4()),
            "trade_id": trade_id,
            "trader_id": trade.get("trader_id"),
            "merchant_id": trade.get("merchant_id"),
            "trader_commission": trader_commission_amt,
            "merchant_commission": trade.get("merchant_commission", 0),
            "total_commission": trade.get("total_commission", 0),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # If direct P2P trade (trader-to-trader), credit USDT to buyer
        if trade.get("buyer_type") == "trader" and trade.get("buyer_id"):
            buyer_receives = trade["amount_usdt"]  # Buyer gets full amount
            await db.traders.update_one(
                {"id": trade["buyer_id"]},
                {"$inc": {"balance_usdt": buyer_receives}}
            )
            message = "✅ Спор разрешён в пользу покупателя. Сделка завершена, USDT зачислены на баланс."
        # If merchant trade, transfer to merchant with proper calculation
        elif trade.get("merchant_id"):
            # Get merchant's commission rate (set by admin on approval)
            merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0})
            commission_rate = merchant.get("commission_rate", 10.0) if merchant else 10.0
            
            # Get original amount from invoice (what merchant requested, NOT what client paid)
            original_amount_rub = None
            if trade.get("invoice_id"):
                invoice = await db.merchant_invoices.find_one({"id": trade["invoice_id"]}, {"_id": 0})
                if invoice:
                    original_amount_rub = invoice.get("original_amount_rub")
            
            # Fallback to trade amounts if no invoice found
            if not original_amount_rub:
                original_amount_rub = trade.get("client_amount_rub") or trade.get("amount_rub", 0)
            
            # Get base exchange rate
            payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
            base_rate = payout_settings.get("base_rate", 78.5) if payout_settings else 78.5
            
            # Merchant receives: original_amount - commission%
            # Commission is calculated from ORIGINAL order amount, not what client paid
            merchant_receives_rub = original_amount_rub * (100 - commission_rate) / 100
            platform_fee_rub = original_amount_rub * commission_rate / 100
            merchant_receives_usdt = merchant_receives_rub / base_rate
            commission_usdt = platform_fee_rub / base_rate
            
            # Update trade with calculated amounts
            await db.trades.update_one(
                {"id": trade_id},
                {"$set": {
                    "original_amount_rub": original_amount_rub,
                    "merchant_commission_percent": commission_rate,
                    "platform_fee_rub": platform_fee_rub,
                    "merchant_receives_rub": merchant_receives_rub,
                    "merchant_receives_usdt": merchant_receives_usdt,
                    "merchant_commission": commission_usdt
                }}
            )
            
            # Credit merchant balance
            await db.merchants.update_one(
                {"id": trade["merchant_id"]},
                {"$inc": {
                    "balance_usdt": merchant_receives_usdt,
                    "total_commission_paid": commission_usdt
                }}
            )
            message = f"✅ Спор разрешён в пользу клиента. Мерчант получил {merchant_receives_rub:.0f} RUB ({merchant_receives_usdt:.2f} USDT)."
        else:
            message = "✅ Спор разрешён в пользу покупателя. Сделка завершена."
        
        # Process referral earnings for completed dispute
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
            else:
                referrer = await db.merchants.find_one({"id": seller["referred_by"]}, {"_id": 0})
                if referrer:
                    await db.merchants.update_one(
                        {"id": seller["referred_by"]},
                        {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                    )
        
        # Case 2: Merchant (whose client is buying) is referred → their referrer earns from purchases
        if trade.get("merchant_id"):
            merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0})
            if merchant and merchant.get("referred_by"):
                referrer = await db.traders.find_one({"id": merchant["referred_by"]}, {"_id": 0})
                if referrer:
                    await db.traders.update_one(
                        {"id": merchant["referred_by"]},
                        {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                    )
                else:
                    referrer = await db.merchants.find_one({"id": merchant["referred_by"]}, {"_id": 0})
                    if referrer:
                        await db.merchants.update_one(
                            {"id": merchant["referred_by"]},
                            {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                        )
            
    elif resolution in ["favor_trader", "refund_seller", "cancel"]:
        # Cancel the trade - seller wins, gets USDT back to offer or balance
        new_status = "cancelled"
        
        # Return USDT to offer if it was a direct trade
        if trade.get("offer_id"):
            await db.offers.update_one(
                {"id": trade["offer_id"]},
                {"$inc": {"available_usdt": trade["amount_usdt"]}}
            )
        else:
            # Otherwise return to trader balance
            await db.traders.update_one(
                {"id": trade["trader_id"]},
                {"$inc": {"balance_usdt": trade["amount_usdt"]}}
            )
        
        message = "❌ Спор разрешён в пользу продавца. Сделка отменена, USDT возвращены."
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution. Use 'favor_client'/'refund_buyer' or 'favor_trader'/'refund_seller'")
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": new_status,
            "dispute_resolved_at": datetime.now(timezone.utc).isoformat(),
            "dispute_resolved_by": user["id"],
            "dispute_resolution": resolution
        }}
    )
    
    # Update invoice status to match trade status
    if trade.get("invoice_id"):
        await db.merchant_invoices.update_one(
            {"id": trade["invoice_id"]},
            {"$set": {"status": new_status, "dispute_resolved_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    # Send system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Auto-archive the unified conversation for this dispute
    await db.unified_conversations.update_one(
        {"$or": [
            {"related_id": trade_id, "type": "p2p_dispute"},
            {"related_id": trade_id, "type": "p2p_trade"}
        ]},
        {"$set": {
            "resolved": True,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolved_by": user["id"],
            "status": "resolved",
            "archived": True
        }}
    )
    
    return {"status": new_status}


@router.get("/trades/{trade_id}/dispute-public")
async def get_dispute_public(trade_id: str):
    """
    Публичный доступ к данным спора (для покупателей без авторизации)
    """
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    # Можно смотреть только disputed или resolved trades
    if trade["status"] not in ["disputed", "completed", "cancelled"]:
        raise HTTPException(status_code=403, detail="Нет доступа к данным сделки")
    
    # Получаем сообщения чата
    messages = await db.trade_messages.find(
        {"trade_id": trade_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    # Добавляем сообщения модераторов из dispute_chats
    dispute_messages = await db.dispute_chats.find(
        {"trade_id": trade_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    for msg in dispute_messages:
        messages.append({
            "id": msg["id"],
            "trade_id": trade_id,
            "sender_id": msg.get("sender_id"),
            "sender_type": "admin",
            "sender_role": msg.get("sender_role", "admin"),
            "content": msg.get("message"),
            "created_at": msg.get("created_at")
        })
    
    # Сортируем все сообщения по времени
    messages.sort(key=lambda x: x.get("created_at", ""))
    
    # Безопасный ответ
    return {
        "trade": {
            "id": trade["id"],
            "status": trade["status"],
            "amount_rub": trade.get("amount_rub"),
            "amount_usdt": trade.get("amount_usdt"),
            "dispute_reason": trade.get("dispute_reason"),
            "disputed_at": trade.get("disputed_at"),
            "created_at": trade.get("created_at"),
            "dispute_resolved_at": trade.get("dispute_resolved_at"),
            "dispute_resolution": trade.get("dispute_resolution")
        },
        "messages": messages
    }
