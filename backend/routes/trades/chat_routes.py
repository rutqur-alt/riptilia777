from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import get_current_user, require_role
from core.websocket import manager
from models.schemas import MessageCreate
from .utils import _ws_broadcast, _create_trade_notification, _clean_doc

router = APIRouter()

@router.get("/trades/{trade_id}/messages")
async def get_trade_messages(trade_id: str, user: dict = Depends(get_current_user)):
    """Get trade messages"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    messages = await db.trade_messages.find({"trade_id": trade_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    return messages


@router.get("/trades/{trade_id}/messages-public")
async def get_trade_messages_public(trade_id: str):
    """Get trade messages - public endpoint for client"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    messages = await db.trade_messages.find({"trade_id": trade_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    return messages


@router.post("/trades/{trade_id}/messages")
async def send_trade_message(trade_id: str, data: MessageCreate, user: dict = Depends(get_current_user)):
    """Send message in trade chat"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Determine sender type
    if user["role"] == "admin":
        sender_type = "admin"
    elif user["role"] == "merchant":
        sender_type = "merchant"
    elif user["role"] == "trader":
        if trade["trader_id"] == user["id"]:
            sender_type = "trader"
        elif trade.get("buyer_id") == user["id"]:
            sender_type = "buyer"
        else:
            sender_type = "trader"
    else:
        sender_type = "client"
    
    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": user["id"],
        "sender_type": sender_type,
        "sender_role": user.get("role", "trader"),
        "sender_nickname": user.get("nickname", user.get("login", "")),
        "content": data.content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.trade_messages.insert_one(msg)
    await manager.broadcast(f"trade_{trade_id}", {k: v for k, v in msg.items() if k != "_id"})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in msg.items() if k != "_id"}})
    
    # Create notification for the other participant about new message
    try:
        notify_id = None
        if trade["trader_id"] != user["id"]:
            notify_id = trade["trader_id"]
        elif trade.get("buyer_id") and trade["buyer_id"] != user["id"]:
            notify_id = trade["buyer_id"]
        if notify_id:
            await _create_trade_notification(
                user_id=notify_id,
                notif_type="trade_message",
                title="Сообщение в сделке",
                message=f"Новое сообщение в сделке #{trade_id[:8]}",
                link=f"/trader/sales/{trade_id}"
            )
    except Exception:
        pass
    
    return {k: v for k, v in msg.items() if k != "_id"}


@router.post("/trades/{trade_id}/messages-public")
async def send_trade_message_public(trade_id: str, data: MessageCreate):
    """Send message as client (no auth) to trade chat"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade["status"] in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Сделка завершена, чат закрыт")
    
    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "client",
        "sender_type": "client",
        "sender_role": "client",
        "sender_nickname": "Покупатель",
        "content": data.content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.trade_messages.insert_one(msg)
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in msg.items() if k != "_id"}})
    
    # Create notification for trader about client message
    try:
        await _create_trade_notification(
            user_id=trade["trader_id"],
            notif_type="trade_message",
            title="Сообщение в сделке",
            message=f"Покупатель написал в сделке #{trade_id[:8]}",
            link=f"/trader/sales/{trade_id}"
        )
    except Exception:
        pass
    
    return {k: v for k, v in msg.items() if k != "_id"}


@router.get("/trades/chat-history")
async def get_trade_chat_history(user: dict = Depends(require_role(["admin", "mod_p2p", "owner", "super_admin"]))):
    """Get chat history for all trades (admin only)"""
    # Get all trades with messages
    pipeline = [
        {
            "$lookup": {
                "from": "trade_messages",
                "localField": "id",
                "foreignField": "trade_id",
                "as": "messages"
            }
        },
        {
            "$match": {
                "messages": {"$ne": []}
            }
        },
        {
            "$sort": {"created_at": -1}
        },
        {
            "$limit": 50
        },
        {
            "$project": {
                "id": 1,
                "status": 1,
                "amount_usdt": 1,
                "amount_rub": 1,
                "created_at": 1,
                "trader_id": 1,
                "buyer_id": 1,
                "merchant_id": 1,
                "qr_aggregator_trade": 1,  # Include QR flag
                "last_message": {"$arrayElemAt": ["$messages", -1]}
            }
        }
    ]
    
    chats = await db.trades.aggregate(pipeline).to_list(50)
    
    # Enrich with user info
    for chat in chats:
        # Trader info
        if chat.get("trader_id"):
            trader = await db.traders.find_one({"id": chat["trader_id"]}, {"_id": 0, "login": 1, "nickname": 1})
            if trader:
                chat["trader_login"] = trader.get("login", "")
                chat["trader_nickname"] = trader.get("nickname", "")
        
        # Buyer info
        if chat.get("buyer_id"):
            buyer = await db.traders.find_one({"id": chat["buyer_id"]}, {"_id": 0, "login": 1, "nickname": 1})
            if buyer:
                chat["buyer_login"] = buyer.get("login", "")
                chat["buyer_nickname"] = buyer.get("nickname", "")
        
        # Merchant info
        if chat.get("merchant_id"):
            merchant = await db.merchants.find_one({"id": chat["merchant_id"]}, {"_id": 0, "login": 1, "nickname": 1})
            if merchant:
                chat["merchant_login"] = merchant.get("login", "")
                chat["merchant_nickname"] = merchant.get("nickname", "")
                
    return [_clean_doc(c) for c in chats]
