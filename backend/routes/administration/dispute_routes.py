from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import require_role, require_admin_level, log_admin_action
from .models import MessageCreate
from .utils import clean_doc

router = APIRouter()

# ==================== DISPUTES ====================

@router.get("/admin/disputes")
async def get_disputes(user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Get all disputed trades for admin/mod_p2p"""
    disputes = await db.trades.find({"status": "disputed"}, {"_id": 0}).sort("disputed_at", -1).to_list(100)
    
    for dispute in disputes:
        dispute["trade_id"] = dispute["id"]
        
        seller = await db.traders.find_one({"id": dispute.get("trader_id")}, {"_id": 0, "login": 1, "nickname": 1})
        if seller:
            dispute["seller_login"] = seller.get("login", "")
            dispute["seller_nickname"] = seller.get("nickname", seller.get("login", ""))
        
        buyer = await db.traders.find_one({"id": dispute.get("client_id")}, {"_id": 0, "login": 1, "nickname": 1})
        if buyer:
            dispute["buyer_login"] = buyer.get("login", "")
            dispute["buyer_nickname"] = buyer.get("nickname", buyer.get("login", ""))
        
        messages = await db.trade_messages.find({"trade_id": dispute["id"]}, {"_id": 0}).sort("created_at", -1).limit(3).to_list(3)
        dispute["last_messages"] = list(reversed(messages))
        
        unread = await db.trade_messages.count_documents({
            "trade_id": dispute["id"],
            "sender_type": {"$in": ["client", "trader"]},
            "read_by_admin": {"$ne": True}
        })
        dispute["unread_count"] = unread
    
    return disputes


@router.post("/admin/disputes/{trade_id}/message")
async def send_admin_dispute_message(trade_id: str, data: MessageCreate, user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Admin or mod_p2p sends message to dispute chat"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Используем admin_role если есть, иначе role
    sender_role = user.get("admin_role") or user.get("role", "admin")
    
    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": user["id"],
        "sender_type": "admin",
        "sender_role": sender_role,
        "sender_name": user.get("login", "Администрация"),
        "content": data.content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.trade_messages.insert_one(msg)
    
    await db.trade_messages.update_many(
        {"trade_id": trade_id},
        {"$set": {"read_by_admin": True}}
    )
    
    return {k: v for k, v in msg.items() if k != "_id"}


@router.get("/admin/disputes/{trade_id}")
async def get_dispute_details(trade_id: str, user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Get full dispute details for admin/mod_p2p"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    trader = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0})
    if trader:
        trade["trader_login"] = trader.get("login", "")
        trade["trader_balance"] = trader.get("balance_usdt", 0)
    
    messages = await db.trade_messages.find({"trade_id": trade_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    trade["messages"] = messages
    
    if trade.get("requisite_ids"):
        requisites = []
        for req_id in trade["requisite_ids"]:
            req = await db.requisites.find_one({"id": req_id}, {"_id": 0})
            if req:
                requisites.append(req)
        trade["requisites"] = requisites
    
    await db.trade_messages.update_many(
        {"trade_id": trade_id},
        {"$set": {"read_by_admin": True}}
    )
    
    return trade


@router.post("/admin/trades/{trade_id}/resolve")
async def resolve_trade_dispute(trade_id: str, data: dict = Body(...), user: dict = Depends(require_admin_level(50))):
    """Resolve a disputed trade
    decision: 'favor_buyer' or 'favor_seller'
    reason: text explanation
    """
    decision = data.get("decision", data.get("resolution", ""))
    reason = data.get("reason", "")
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade["status"] not in ["disputed", "dispute", "paid", "pending", "pending_payment"]:
        raise HTTPException(status_code=400, detail=f"Cannot resolve trade in status: {trade['status']}")
    
    # Normalize decision values
    # favor_buyer / favor_client / refund_buyer / complete_trade -> two outcomes
    buyer_wins = decision in ["favor_buyer", "favor_client", "complete_trade", "refund_buyer"]
    seller_wins = decision in ["favor_seller", "favor_trader", "cancel", "release_seller"]
    
    if not buyer_wins and not seller_wins:
        raise HTTPException(status_code=400, detail="Invalid decision. Use 'favor_buyer' or 'favor_seller'")
    
    try:
        from routes.websockets import ws_manager
    except ImportError:
        ws_manager = None
    
    # Handle both trade schemas: amount_usdt (new) and amount (old)
    trade_amount = trade.get("amount_usdt") or trade.get("amount", 0)
    
    if buyer_wins:
        # BUYER WINS: Complete the trade, credit USDT to buyer
        new_status = "completed"
        
        # Credit USDT to buyer
        if trade.get("buyer_id") and trade.get("buyer_type") == "trader":
            await db.traders.update_one(
                {"id": trade["buyer_id"]},
                {"$inc": {"balance_usdt": trade_amount}}
            )
            message = f"✅ Спор решён в пользу покупателя. Сделка завершена, {trade_amount} USDT зачислены покупателю."
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
            
            # Update invoice status to completed
            if trade.get("invoice_id"):
                await db.merchant_invoices.update_one(
                    {"id": trade["invoice_id"]},
                    {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
                )
            
            message = f"✅ Спор решён в пользу клиента. Мерчант получил {merchant_receives_rub:.0f} RUB ({merchant_receives_usdt:.2f} USDT)."
        else:
            message = f"✅ Спор решён в пользу покупателя. Сделка завершена."
        
        if reason:
            message += f"\nПричина: {reason}"
        
        # Update offer sold_usdt
        if trade.get("offer_id"):
            await db.offers.update_one(
                {"id": trade["offer_id"]},
                {"$inc": {
                    "sold_usdt": trade_amount,
                    "actual_commission": trade.get("trader_commission", 0)
                }}
            )
    
    else:
        # SELLER WINS: Cancel the trade, return USDT to seller's offer or balance
        new_status = "cancelled"
        
        if trade.get("offer_id"):
            await db.offers.update_one(
                {"id": trade["offer_id"]},
                {"$inc": {"available_usdt": trade_amount}}
            )
        else:
            await db.traders.update_one(
                {"id": trade["trader_id"]},
                {"$inc": {"balance_usdt": trade_amount}}
            )
        
        message = f"❌ Спор решён в пользу продавца. Сделка отменена, {trade_amount} USDT возвращены продавцу."
        if reason:
            message += f"\nПричина: {reason}"
    
    # Update trade status
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": new_status,
            "dispute_resolved_at": datetime.now(timezone.utc).isoformat(),
            "dispute_resolved_by": user["id"],
            "dispute_resolution": decision,
            "resolution_reason": reason
        }}
    )
    
    # Send system message to trade chat
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Send webhook to merchant
    if trade.get("invoice_id"):
        from routes.invoice.webhook_utils import send_webhook_notification
        await send_webhook_notification(trade["invoice_id"], new_status, {
            "dispute_resolution": decision,
            "resolution_reason": reason
        })
    
    # Auto-archive the unified conversation
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
    
    # WebSocket broadcast
    if ws_manager:
        msg_broadcast = {k: v for k, v in system_msg.items() if k != "_id"}
        await ws_manager.broadcast(f"trade_{trade_id}", {"type": "message", **msg_broadcast})
        await ws_manager.broadcast(f"trade_{trade_id}", {"type": "status_update", "status": new_status, "trade_id": trade_id})
        # Notify trader
        if trade.get("trader_id"):
            await ws_manager.broadcast(f"user_{trade['trader_id']}", {"type": "trade_resolved", "trade_id": trade_id, "status": new_status})
        if trade.get("buyer_id"):
            await ws_manager.broadcast(f"user_{trade['buyer_id']}", {"type": "trade_resolved", "trade_id": trade_id, "status": new_status})
    
    await log_admin_action(user["id"], "resolve_dispute", "trade", trade_id, {"resolution": decision, "reason": reason, "new_status": new_status})
    
    return {"status": new_status, "message": message}
