from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import JSONResponse, Response
import json as _json
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import require_admin_level, log_admin_action
from .utils import clean_doc

router = APIRouter()

# ==================== ADMIN: TRADES ====================

@router.get("/admin/trades")
async def get_all_trades_admin(
    skip: int = 0,
    limit: int = 50,
    status: str = None,
    user: dict = Depends(require_admin_level(30))
):
    """Get all trades"""
    import logging
    logger = logging.getLogger("admin_trades")
    try:
        query = {}
        if status:
            query["status"] = status
        
        trades = await db.trades.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        total = await db.trades.count_documents(query)
        
        cleaned = []
        for t in trades:
            ct = {}
            for k, v in t.items():
                if k == "_id":
                    continue
                ct[k] = clean_doc(v)
            cleaned.append(ct)
        
        body_str = _json.dumps({"trades": cleaned, "total": total}, default=str, ensure_ascii=False)
        result = _json.loads(body_str)
        return JSONResponse(content=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e), "trades": [], "total": 0}, status_code=500)


@router.get("/admin/trades/{trade_id}")
async def get_trade_details_admin(trade_id: str, user: dict = Depends(require_admin_level(30))):
    """Get detailed trade info including chat"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Get chat messages
    messages = await db.trade_messages.find({"trade_id": trade_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    
    # Get trader and buyer info
    trader = await db.traders.find_one({"id": trade.get("trader_id")}, {"_id": 0, "password_hash": 0, "password": 0, "login": 1, "nickname": 1})
    buyer = await db.traders.find_one({"id": trade.get("buyer_id")}, {"_id": 0, "password_hash": 0, "password": 0, "login": 1, "nickname": 1}) if trade.get("buyer_id") else None
    
    return Response(content=_json.dumps({
        "trade": clean_doc(trade),
        "messages": [clean_doc(m) for m in messages],
        "trader": clean_doc(trader) if trader else None,
        "buyer": clean_doc(buyer) if buyer else None
    }, default=str), media_type="application/json")


@router.delete("/admin/trades/{trade_id}")
async def delete_trade(trade_id: str, user: dict = Depends(require_admin_level(100))):
    """Delete a trade (owner only)"""
    trade = await db.trades.find_one({"id": trade_id})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    await db.trades.delete_one({"id": trade_id})
    await db.trade_messages.delete_many({"trade_id": trade_id})
    
    await log_admin_action(user["id"], "delete_trade", "trade", trade_id, {})
    
    return {"status": "deleted"}


# ==================== ADMIN: TRADES HISTORY ====================

@router.get("/admin/trades-history")
async def get_all_trades_history(
    status: str = None,
    limit: int = 100,
    user: dict = Depends(require_admin_level(30))
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


@router.get("/admin/trades-history/{trade_id}")
async def get_trade_history_details(trade_id: str, user: dict = Depends(require_admin_level(30))):
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

@router.get("/admin/marketplace-history")
async def get_marketplace_orders_history(
    status: str = None,
    limit: int = 100,
    user: dict = Depends(require_admin_level(30))
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


@router.get("/admin/marketplace-history/{order_id}")
async def get_marketplace_order_history(order_id: str, user: dict = Depends(require_admin_level(30))):
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
