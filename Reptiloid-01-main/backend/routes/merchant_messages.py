"""
Merchant Messages Routes - Migrated from server.py
Handles merchant conversations, messages, and trades
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.auth import get_current_user
from core.database import db

router = APIRouter(tags=["merchant_messages"])


# ==================== MERCHANT MESSAGES API ====================

@router.get("/msg/merchant/conversations")
async def get_merchant_conversations(user: dict = Depends(get_current_user)):
    """Get all conversations for a merchant"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    user_id = user["id"]
    
    # Find conversations where merchant is participant
    convs = await db.unified_conversations.find(
        {
            "$or": [
                {"participants": user_id},
                {"merchant_id": user_id},
                {"seller_id": user_id},
                {"buyer_id": user_id}
            ],
            "deleted": {"$ne": True}
        },
        {"_id": 0}
    ).sort("updated_at", -1).to_list(200)
    
    # Enrich with unread counts and last message
    result = []
    for conv in convs:
        # Get unread count
        last_read = conv.get("last_read", {}).get(user_id)
        if last_read:
            unread = await db.unified_messages.count_documents({
                "conversation_id": conv["id"],
                "sender_id": {"$ne": user_id},
                "created_at": {"$gt": last_read}
            })
        else:
            unread = await db.unified_messages.count_documents({
                "conversation_id": conv["id"],
                "sender_id": {"$ne": user_id}
            })
        
        # Get last message
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"]},
            {"_id": 0, "content": 1},
            sort=[("created_at", -1)]
        )
        
        conv["unread_count"] = unread
        conv["last_message"] = last_msg.get("content", "")[:50] if last_msg else ""
        result.append(conv)
    
    return result


@router.get("/msg/merchant/conversations/{conversation_id}/messages")
async def get_merchant_conversation_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user)
):
    """Get messages for a merchant conversation"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    # Check access
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    user_id = user["id"]
    has_access = (
        user_id in conv.get("participants", []) or
        conv.get("merchant_id") == user_id or
        conv.get("seller_id") == user_id or
        conv.get("buyer_id") == user_id
    )
    
    if not has_access:
        raise HTTPException(status_code=403, detail="Нет доступа к чату")
    
    messages = await db.unified_messages.find(
        {"conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    return messages


@router.post("/msg/merchant/conversations/{conversation_id}/messages")
async def send_merchant_message(
    conversation_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """Send message to a merchant conversation"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    content = data.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    # Check access
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    user_id = user["id"]
    has_access = (
        user_id in conv.get("participants", []) or
        conv.get("merchant_id") == user_id or
        conv.get("seller_id") == user_id or
        conv.get("buyer_id") == user_id
    )
    
    if not has_access:
        raise HTTPException(status_code=403, detail="Нет доступа к чату")
    
    now = datetime.now(timezone.utc).isoformat()
    msg_id = str(uuid.uuid4())
    
    msg = {
        "id": msg_id,
        "conversation_id": conversation_id,
        "sender_id": user_id,
        "sender_nickname": user.get("nickname") or user.get("merchant_name") or user.get("login"),
        "sender_role": "merchant",
        "content": content,
        "created_at": now
    }
    
    await db.unified_messages.insert_one(msg)
    
    # Update conversation
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$set": {"updated_at": now}}
    )
    
    msg.pop("_id", None)
    return msg


@router.post("/msg/merchant/conversations/{conversation_id}/read")
async def mark_merchant_conversation_read(
    conversation_id: str,
    user: dict = Depends(get_current_user)
):
    """Mark conversation as read for merchant"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    now = datetime.now(timezone.utc).isoformat()
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$set": {f"last_read.{user['id']}": now}}
    )
    
    return {"status": "ok"}


# ==================== MERCHANT TRADES ====================

@router.get("/merchant/trades")
async def get_merchant_trades(
    type: str = "sell",  # sell or buy
    status: str = None,
    user: dict = Depends(get_current_user)
):
    """Get merchant's P2P trades"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    user_id = user["id"]
    
    # Build query based on type
    if type == "sell":
        # Trades where merchant is selling (merchant_id or seller_id)
        query = {"$or": [{"merchant_id": user_id}, {"seller_id": user_id}]}
    else:
        # Trades where merchant is buying
        query = {"buyer_id": user_id}
    
    # Filter by status
    if status == "active":
        query["status"] = {"$in": ["pending", "active", "paid", "waiting"]}
    elif status == "completed":
        query["status"] = "completed"
    elif status == "dispute":
        query["status"] = {"$in": ["dispute", "disputed"]}
    elif status == "cancelled":
        query["status"] = "cancelled"
    
    # Get trades from both collections
    trades = []
    
    # From trades collection
    db_trades = await db.trades.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    for t in db_trades:
        # Find conversation
        conv = await db.unified_conversations.find_one(
            {"related_id": t["id"]},
            {"_id": 0, "id": 1}
        )
        t["conversation_id"] = conv["id"] if conv else None
        t["client_nickname"] = t.get("buyer_nickname") if type == "sell" else t.get("seller_nickname")
        # Map amount fields for frontend compatibility
        if not t.get("amount"):
            t["amount"] = t.get("amount_usdt", 0)
        if not t.get("fiat_amount"):
            t["fiat_amount"] = t.get("amount_rub") or t.get("total_rub", 0)
        if not t.get("currency"):
            t["currency"] = t.get("crypto", "USDT")
        trades.append(t)
    
    # From crypto_orders collection (withdrawal requests)
    crypto_query = {"merchant_id": user_id} if type == "sell" else {"buyer_id": user_id, "merchant_id": user_id}
    crypto_orders = await db.crypto_orders.find(crypto_query, {"_id": 0}).sort("created_at", -1).to_list(100)
    for o in crypto_orders:
        # Find conversation
        conv = await db.unified_conversations.find_one(
            {"related_id": o["id"]},
            {"_id": 0, "id": 1}
        )
        o["conversation_id"] = conv["id"] if conv else None
        o["client_nickname"] = o.get("buyer_nickname")
        o["amount"] = o.get("amount_usdt")
        o["fiat_amount"] = o.get("amount_rub")
        o["currency"] = "USDT"
        trades.append(o)
    
    # Sort by created_at
    trades.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return trades
