"""
Admin routes - Administrative functions
Organized into logical groups for maintainability
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import uuid

from core.database import db
from core.auth import require_role, get_current_user
from models.schemas import MessageCreate, CommissionSettings, UpdateCommissionSettings

router = APIRouter(prefix="/admin", tags=["admin"])


# ==================== DISPUTES ====================

@router.get("/disputes")
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


@router.get("/trades-history")
async def get_all_trades_history(
    status: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(require_role(["admin", "mod_p2p"]))
):
    """
    Получить все сделки с полной историей чата.
    Включает: pending, paid, completed, cancelled, disputed.
    Для админов и модераторов P2P.
    """
    query = {}
    if status:
        query["status"] = status
    
    trades = await db.trades.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    
    for trade in trades:
        trade["trade_id"] = trade["id"]
        
        # Seller info
        seller = await db.traders.find_one({"id": trade.get("trader_id")}, {"_id": 0, "login": 1, "nickname": 1})
        if seller:
            trade["seller_login"] = seller.get("login", "")
            trade["seller_nickname"] = seller.get("nickname", seller.get("login", ""))
        
        # Buyer info
        buyer = await db.traders.find_one({"id": trade.get("buyer_id")}, {"_id": 0, "login": 1, "nickname": 1})
        if buyer:
            trade["buyer_login"] = buyer.get("login", "")
            trade["buyer_nickname"] = buyer.get("nickname", buyer.get("login", ""))
        
        # Полная история сообщений
        messages = await db.trade_messages.find({"trade_id": trade["id"]}, {"_id": 0}).sort("created_at", 1).to_list(500)
        trade["messages"] = messages
        trade["messages_count"] = len(messages)
        
        # Реквизиты которые были выданы
        trade["requisites_history"] = trade.get("requisites", [])
    
    return trades


@router.get("/trades-history/{trade_id}")
async def get_trade_history_details(trade_id: str, user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """
    Получить полную историю конкретной сделки.
    Включает все сообщения, реквизиты, статусы.
    """
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    trade["trade_id"] = trade["id"]
    
    # Seller info
    seller = await db.traders.find_one({"id": trade.get("trader_id")}, {"_id": 0})
    if seller:
        trade["seller_info"] = {
            "login": seller.get("login"),
            "nickname": seller.get("nickname"),
            "balance_usdt": seller.get("balance_usdt", 0)
        }
    
    # Buyer info
    if trade.get("buyer_id"):
        buyer = await db.traders.find_one({"id": trade["buyer_id"]}, {"_id": 0})
        if buyer:
            trade["buyer_info"] = {
                "login": buyer.get("login"),
                "nickname": buyer.get("nickname")
            }
    
    # ВСЯ история сообщений
    messages = await db.trade_messages.find({"trade_id": trade_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    trade["messages"] = messages
    
    # Реквизиты
    trade["requisites_history"] = trade.get("requisites", [])
    
    return trade


# ==================== MARKETPLACE ORDERS HISTORY ====================

@router.get("/marketplace-history")
async def get_marketplace_orders_history(
    status: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """
    Получить все заказы маркетплейса с историей чата.
    Для админов и модераторов.
    """
    query = {}
    if status:
        query["status"] = status
    
    orders = await db.marketplace_purchases.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    
    for order in orders:
        order["order_id"] = order["id"]
        
        # Buyer info
        buyer = await db.traders.find_one({"id": order.get("buyer_id")}, {"_id": 0, "login": 1, "nickname": 1})
        if buyer:
            order["buyer_login"] = buyer.get("login", "")
            order["buyer_nickname"] = buyer.get("nickname", buyer.get("login", ""))
        
        # Seller info
        seller = await db.traders.find_one({"id": order.get("seller_id")}, {"_id": 0, "login": 1, "nickname": 1})
        if seller:
            order["seller_login"] = seller.get("login", "")
            order["seller_nickname"] = seller.get("nickname", seller.get("login", ""))
        
        # Ищем conversation для этого заказа
        conv = await db.unified_conversations.find_one({"type": "marketplace", "related_id": order["id"]}, {"_id": 0})
        if conv:
            messages = await db.unified_messages.find({"conversation_id": conv["id"]}, {"_id": 0}).sort("created_at", 1).to_list(500)
            order["messages"] = messages
            order["messages_count"] = len(messages)
        else:
            order["messages"] = []
            order["messages_count"] = 0
    
    return orders


@router.get("/marketplace-history/{order_id}")
async def get_marketplace_order_history(order_id: str, user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))):
    """
    Получить полную историю конкретного заказа маркетплейса.
    """
    order = await db.marketplace_purchases.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order["order_id"] = order["id"]
    
    # Buyer info
    buyer = await db.traders.find_one({"id": order.get("buyer_id")}, {"_id": 0})
    if buyer:
        order["buyer_info"] = {
            "login": buyer.get("login"),
            "nickname": buyer.get("nickname")
        }
    
    # Seller info
    seller = await db.traders.find_one({"id": order.get("seller_id")}, {"_id": 0})
    if seller:
        order["seller_info"] = {
            "login": seller.get("login"),
            "nickname": seller.get("nickname")
        }
    
    # Product info
    product = await db.shop_products.find_one({"id": order.get("product_id")}, {"_id": 0, "name": 1, "price": 1})
    if product:
        order["product_info"] = product
    
    # История чата
    conv = await db.unified_conversations.find_one({"type": "marketplace", "related_id": order_id}, {"_id": 0})
    if conv:
        messages = await db.unified_messages.find({"conversation_id": conv["id"]}, {"_id": 0}).sort("created_at", 1).to_list(1000)
        order["messages"] = messages
    else:
        order["messages"] = []
    
    return order


@router.post("/disputes/{trade_id}/message")
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


@router.get("/disputes/{trade_id}")
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


@router.post("/disputes/{trade_id}/resolve")
async def resolve_dispute(trade_id: str, data: dict, user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Resolve a disputed trade - admin or mod_p2p"""
    resolution = data.get("resolution")  # "refund_buyer" or "complete_trade"
    reason = data.get("reason", "")
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade.get("status") != "disputed":
        raise HTTPException(status_code=400, detail="Trade is not in disputed status")
    
    resolver_name = user.get("login", "Администрация")
    resolver_role = user.get("role", "admin")
    role_label = "Модератор P2P" if resolver_role == "mod_p2p" else "Администрация"
    
    if resolution == "refund_buyer":
        # Refund - cancel trade, return funds to offer
        await db.trades.update_one({"id": trade_id}, {"$set": {
            "status": "cancelled",
            "resolved_by": user["id"],
            "resolved_by_role": resolver_role,
            "resolution": "refund_buyer",
            "resolution_reason": reason,
            "resolved_at": datetime.now(timezone.utc).isoformat()
        }})
        
        # Return funds to offer
        if trade.get("offer_id"):
            await db.offers.update_one({"id": trade["offer_id"]}, {"$inc": {"available_usdt": trade["amount_usdt"]}})
        
        # Add system message
        sys_msg = {
            "id": str(uuid.uuid4()),
            "trade_id": trade_id,
            "sender_type": "system",
            "sender_role": "system",
            "content": f"⚠️ Спор решён в пользу покупателя. {role_label} {resolver_name}: {reason or 'Без комментария'}",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.trade_messages.insert_one(sys_msg)
        
    elif resolution == "complete_trade":
        # Force complete - transfer funds to buyer
        await db.trades.update_one({"id": trade_id}, {"$set": {
            "status": "completed",
            "resolved_by": user["id"],
            "resolved_by_role": resolver_role,
            "resolution": "complete_trade",
            "resolution_reason": reason,
            "resolved_at": datetime.now(timezone.utc).isoformat()
        }})
        
        # Transfer funds to buyer
        if trade.get("buyer_id"):
            await db.traders.update_one({"id": trade["buyer_id"]}, {"$inc": {"balance_usdt": trade["amount_usdt"]}})
        
        # Add system message
        sys_msg = {
            "id": str(uuid.uuid4()),
            "trade_id": trade_id,
            "sender_type": "system",
            "sender_role": "system",
            "content": f"✅ Спор решён в пользу продавца. Сделка завершена. {role_label} {resolver_name}: {reason or 'Без комментария'}",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.trade_messages.insert_one(sys_msg)
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution. Use 'refund_buyer' or 'complete_trade'")
    
    return {"status": "success", "resolution": resolution, "resolved_by": resolver_name}


# ==================== COMMISSION SETTINGS ====================

@router.get("/commission-settings", response_model=CommissionSettings)
async def get_commission_settings(user: dict = Depends(require_role(["admin"]))):
    """Get platform commission settings"""
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {"trader_commission": 1.0, "minimum_commission": 0.01}
    return settings


@router.put("/commission-settings", response_model=CommissionSettings)
async def update_commission_settings(data: UpdateCommissionSettings, user: dict = Depends(require_role(["admin"]))):
    """Update platform commission settings"""
    update_data = {}
    if data.trader_commission is not None:
        update_data["trader_commission"] = data.trader_commission
    if data.minimum_commission is not None:
        update_data["minimum_commission"] = data.minimum_commission
    if data.gambling_commission is not None:
        update_data["gambling_commission"] = data.gambling_commission
    if data.casino_commission is not None:
        update_data["casino_commission"] = data.casino_commission
    if data.high_risk_commission is not None:
        update_data["high_risk_commission"] = data.high_risk_commission
    if data.default_price_rub is not None:
        update_data["default_price_rub"] = data.default_price_rub
    
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        update_data["updated_by"] = user["id"]
        await db.commission_settings.update_one({}, {"$set": update_data}, upsert=True)
    
    return await db.commission_settings.find_one({}, {"_id": 0})


@router.get("/commission-history")
async def get_commission_history(user: dict = Depends(require_role(["admin"]))):
    """Get commission payment history"""
    history = await db.commission_payments.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return history


# ==================== MONITORING & STATS ====================

@router.get("/monitoring")
async def get_monitoring_data(user: dict = Depends(require_role(["admin"]))):
    """Get real-time monitoring data"""
    now = datetime.now(timezone.utc)
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    
    active_trades = await db.trades.count_documents({"status": {"$in": ["pending", "paid"]}})
    disputed_trades = await db.trades.count_documents({"status": "disputed"})
    
    trades_last_hour = await db.trades.count_documents({
        "created_at": {"$gte": hour_ago.isoformat()}
    })
    
    completed_today = await db.trades.count_documents({
        "status": "completed",
        "completed_at": {"$gte": day_ago.isoformat()}
    })
    
    total_volume_today = 0
    pipeline = [
        {"$match": {"status": "completed", "completed_at": {"$gte": day_ago.isoformat()}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount_usdt"}}}
    ]
    result = await db.trades.aggregate(pipeline).to_list(1)
    if result:
        total_volume_today = result[0].get("total", 0)
    
    online_traders = await db.traders.count_documents({
        "last_activity": {"$gte": (now - timedelta(minutes=15)).isoformat()}
    })
    
    return {
        "active_trades": active_trades,
        "disputed_trades": disputed_trades,
        "trades_last_hour": trades_last_hour,
        "completed_today": completed_today,
        "volume_today_usdt": round(total_volume_today, 2),
        "online_traders": online_traders,
        "timestamp": now.isoformat()
    }


@router.get("/stats")
async def get_admin_stats(user: dict = Depends(require_role(["admin"]))):
    """Get overall platform statistics"""
    total_traders = await db.traders.count_documents({})
    total_merchants = await db.merchants.count_documents({})
    total_trades = await db.trades.count_documents({})
    completed_trades = await db.trades.count_documents({"status": "completed"})
    
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount_usdt"}}}
    ]
    result = await db.trades.aggregate(pipeline).to_list(1)
    total_volume = result[0].get("total", 0) if result else 0
    
    pipeline = [
        {"$group": {"_id": None, "total": {"$sum": "$trader_commission"}}}
    ]
    result = await db.commission_payments.aggregate(pipeline).to_list(1)
    total_commission = result[0].get("total", 0) if result else 0
    
    return {
        "total_traders": total_traders,
        "total_merchants": total_merchants,
        "total_trades": total_trades,
        "completed_trades": completed_trades,
        "total_volume_usdt": round(total_volume, 2),
        "total_commission_usdt": round(total_commission, 4),
        "success_rate": round(completed_trades / total_trades * 100, 1) if total_trades > 0 else 0
    }


# ==================== TRADERS MANAGEMENT ====================

@router.get("/traders")
async def get_all_traders(user: dict = Depends(require_role(["admin"]))):
    """Get all traders for admin"""
    traders = await db.traders.find({}, {"_id": 0, "password": 0}).sort("created_at", -1).to_list(500)
    
    for trader in traders:
        trade_count = await db.trades.count_documents({"trader_id": trader["id"]})
        trader["trade_count"] = trade_count
        
        completed = await db.trades.count_documents({"trader_id": trader["id"], "status": "completed"})
        trader["completed_trades"] = completed
    
    return traders


@router.put("/traders/{trader_id}")
async def update_trader_admin(
    trader_id: str, 
    commission_rate: Optional[float] = None, 
    is_blocked: Optional[bool] = None, 
    user: dict = Depends(require_role(["admin"]))
):
    """Update trader settings"""
    update = {}
    if commission_rate is not None:
        update["commission_rate"] = commission_rate
    if is_blocked is not None:
        update["is_blocked"] = is_blocked
    
    if update:
        await db.traders.update_one({"id": trader_id}, {"$set": update})
    
    return {"status": "updated"}


@router.post("/traders/{trader_id}/adjust-balance")
async def adjust_trader_balance(trader_id: str, amount: float, reason: str, user: dict = Depends(require_role(["admin"]))):
    """Adjust trader balance (positive or negative)"""
    trader = await db.traders.find_one({"id": trader_id}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    
    await db.traders.update_one({"id": trader_id}, {"$inc": {"balance_usdt": amount}})
    
    await db.transactions.insert_one({
        "id": str(uuid.uuid4()),
        "trader_id": trader_id,
        "type": "admin_adjustment",
        "amount": amount,
        "reason": reason,
        "admin_id": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"status": "adjusted", "new_balance": trader["balance_usdt"] + amount}


# ==================== MERCHANTS MANAGEMENT ====================

@router.get("/merchants")
async def admin_get_all_merchants(user: dict = Depends(require_role(["admin"]))):
    """Get all merchants for admin"""
    merchants = await db.merchants.find({}, {"_id": 0, "password": 0, "api_key": 0}).to_list(100)
    return merchants


@router.post("/merchants/{merchant_id}/status")
async def admin_update_merchant_status(merchant_id: str, status: str, user: dict = Depends(require_role(["admin"]))):
    """Update merchant status (pending/approved/rejected/blocked)"""
    valid_statuses = ["pending", "approved", "rejected", "blocked", "active"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    await db.merchants.update_one({"id": merchant_id}, {"$set": {"status": status}})
    return {"status": "updated"}


# ==================== OFFERS MANAGEMENT ====================

@router.get("/offers")
async def get_all_offers(user: dict = Depends(require_role(["admin"]))):
    """Get all P2P offers for admin"""
    offers = await db.offers.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    for offer in offers:
        # Strip ObjectId _id from embedded requisites
        if "requisites" in offer:
            for req in offer["requisites"]:
                req.pop("_id", None)
        
        trader = await db.traders.find_one({"id": offer["trader_id"]}, {"_id": 0, "login": 1, "nickname": 1})
        if trader:
            offer["trader_login"] = trader.get("login", "")
            offer["trader_nickname"] = trader.get("nickname", "")
    
    return offers


@router.put("/offers/{offer_id}/deactivate")
async def deactivate_offer(offer_id: str, user: dict = Depends(require_role(["admin"]))):
    """Deactivate an offer"""
    offer = await db.offers.find_one({"id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    await db.offers.update_one(
        {"id": offer_id},
        {"$set": {
            "is_active": False,
            "deactivated_by": user["id"],
            "deactivated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if offer.get("available_usdt", 0) > 0:
        await db.traders.update_one(
            {"id": offer["trader_id"]},
            {"$inc": {"balance_usdt": offer["available_usdt"]}}
        )
    
    return {"status": "deactivated"}


@router.put("/offers/{offer_id}/toggle")
async def toggle_offer(offer_id: str, user: dict = Depends(require_role(["admin"]))):
    """Toggle offer active status"""
    offer = await db.offers.find_one({"id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    new_status = not offer.get("is_active", True)
    await db.offers.update_one({"id": offer_id}, {"$set": {"is_active": new_status}})
    
    return {"status": "toggled", "is_active": new_status}


# ==================== TRADES MANAGEMENT ====================

@router.get("/trades")
async def get_all_trades_admin(
    status: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(require_role(["admin"]))
):
    """Get all trades for admin"""
    query = {}
    if status:
        query["status"] = status
    
    trades = await db.trades.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return trades


@router.get("/trades/{trade_id}")
async def get_trade_admin(trade_id: str, user: dict = Depends(require_role(["admin"]))):
    """Get trade details for admin"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    trader = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0, "login": 1, "nickname": 1, "balance_usdt": 1})
    if trader:
        trade["trader_info"] = trader
    
    if trade.get("buyer_id"):
        buyer = await db.traders.find_one({"id": trade["buyer_id"]}, {"_id": 0, "login": 1, "nickname": 1})
        if buyer:
            trade["buyer_info"] = buyer
    
    messages = await db.trade_messages.find({"trade_id": trade_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    trade["messages"] = messages
    
    return trade


@router.delete("/trades/{trade_id}")
async def delete_trade_admin(trade_id: str, user: dict = Depends(require_role(["admin"]))):
    """Delete a trade (admin only)"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade["status"] in ["pending", "paid"]:
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
    
    await db.trades.delete_one({"id": trade_id})
    await db.trade_messages.delete_many({"trade_id": trade_id})
    
    return {"status": "deleted"}


# ==================== MERCHANT FEE SETTINGS ====================

@router.get("/merchants/{merchant_id}/fee-settings")
async def get_merchant_fee_settings(merchant_id: str, user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Получить настройки комиссий мерчанта"""
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    return {
        "merchant_id": merchant_id,
        "merchant_name": merchant.get("merchant_name") or merchant.get("login", ""),
        "fee_model": "merchant_pays",
        "commission_rate": merchant.get("commission_rate", 3.0),
        "withdrawal_commission": merchant.get("withdrawal_commission", 3.0),
        "method_commissions": merchant.get("method_commissions", {}),
        "payment_method_commissions": merchant.get("payment_method_commissions", [])
    }


@router.put("/merchants/{merchant_id}/fee-settings")
async def update_merchant_fee_settings(
    merchant_id: str,
    data: dict,
    user: dict = Depends(require_role(["admin", "mod_p2p"]))
):
    """
    Обновить настройки комиссий мерчанта.
    
    fee_model: всегда "merchant_pays" — мерчант платит комиссию
    """
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    fee_model = "merchant_pays"
    commission_rate = data.get("commission_rate", 3.0)
    withdrawal_commission = data.get("withdrawal_commission", 3.0)
    
    await db.merchants.update_one(
        {"id": merchant_id},
        {"$set": {
            "fee_model": fee_model,
            "commission_rate": commission_rate,
            "withdrawal_commission": withdrawal_commission,
            "fee_settings_updated_at": datetime.now(timezone.utc).isoformat(),
            "fee_settings_updated_by": user["id"]
        }}
    )
    
    return {
        "status": "success",
        "message": "Настройки комиссий обновлены",
        "fee_model": fee_model,
        "commission_rate": commission_rate
    }


@router.get("/merchants/{merchant_id}/method-commissions")
async def get_merchant_method_commissions(merchant_id: str, user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Получить настройки комиссий по методам оплаты"""
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    return {
        "merchant_id": merchant_id,
        "methods": merchant.get("payment_method_commissions", [])
    }


@router.put("/merchants/{merchant_id}/method-commissions")
async def update_merchant_method_commissions(
    merchant_id: str,
    data: dict,
    user: dict = Depends(require_role(["admin", "mod_p2p"]))
):
    """
    Обновить настройки комиссий по методам оплаты.
    
    Формат methods:
    [
        {
            "payment_method": "card",
            "intervals": [
                {"min_amount": 100, "max_amount": 999, "percent": 15},
                {"min_amount": 1000, "max_amount": 4999, "percent": 12},
                {"min_amount": 5000, "max_amount": 100000, "percent": 10}
            ]
        }
    ]
    
    Используется для fee_model = "merchant_pays" (Тип 1)
    """
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    methods = data.get("methods", [])
    
    # Validate methods structure
    valid_payment_methods = ['card', 'sbp', 'sim', 'mono_bank', 'sng_sbp', 'sng_card', 'qr_code']
    
    methods_data = []
    for method in methods:
        payment_method = method.get("payment_method")
        if payment_method not in valid_payment_methods:
            continue
        
        intervals = method.get("intervals", [])
        validated_intervals = []
        
        for interval in intervals:
            validated_intervals.append({
                "min_amount": float(interval.get("min_amount", 0)),
                "max_amount": float(interval.get("max_amount", 999999)),
                "percent": float(interval.get("percent", 10))
            })
        
        if validated_intervals:
            methods_data.append({
                "payment_method": payment_method,
                "intervals": validated_intervals
            })
    
    await db.merchants.update_one(
        {"id": merchant_id},
        {"$set": {
            "payment_method_commissions": methods_data,
            "method_commissions_updated_at": datetime.now(timezone.utc).isoformat(),
            "method_commissions_updated_by": user["id"]
        }}
    )
    
    return {
        "status": "success",
        "message": "Настройки комиссий по методам обновлены",
        "methods_count": len(methods_data)
    }

