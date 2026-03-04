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
        
        # Get original_amount_rub from linked invoice (merchant's requested amount)
        # This is what we show to the merchant - NOT what client paid with trader markup
        original_rub = t.get("original_amount_rub")
        if not original_rub and t.get("invoice_id"):
            invoice = await db.merchant_invoices.find_one({"id": t["invoice_id"]}, {"_id": 0, "original_amount_rub": 1})
            if invoice:
                original_rub = invoice.get("original_amount_rub")
        
        # Map amount fields - use original_amount_rub (merchant's price)
        display_amount = original_rub or t.get("client_amount_rub") or t.get("amount_rub", 0)
        if not t.get("amount"):
            t["amount"] = display_amount
        if not t.get("fiat_amount"):
            t["fiat_amount"] = display_amount
        t["original_amount_rub"] = original_rub
        t["client_pays_rub"] = t.get("client_pays_rub") or t.get("amount_rub")  # What client actually paid
        if not t.get("currency"):
            t["currency"] = "RUB"  # Show in RUB, not USDT
        trades.append(t)
    
    # NOTE: crypto_orders НЕ добавляем здесь - они показываются в разделе "Заявки на выплаты"
    # crypto_orders - это когда трейдер покупает USDT с баланса мерчанта
    
    # From merchant_invoices collection (Invoice API payments)
    # Skip invoices that already have a trade_id - they are already in trades list
    if type == "sell":
        inv_query = {"merchant_id": user_id}
        if status == "active":
            inv_query["status"] = {"$in": ["pending", "waiting_requisites", "paid", "waiting"]}
        elif status == "completed":
            inv_query["status"] = "completed"
        elif status == "dispute":
            inv_query["status"] = {"$in": ["dispute", "disputed"]}
        elif status == "cancelled":
            inv_query["status"] = {"$in": ["cancelled", "expired"]}
        
        invoices = await db.merchant_invoices.find(inv_query, {"_id": 0}).sort("created_at", -1).to_list(100)
        
        # Get list of trade IDs already in result to avoid duplicates
        existing_trade_ids = {t.get("id") for t in trades}
        existing_invoice_ids = {t.get("invoice_id") for t in trades if t.get("invoice_id")}
        
        for inv in invoices:
            # Skip if we already have this invoice's trade in the list
            if inv.get("trade_id") and inv["trade_id"] in existing_trade_ids:
                continue
            # Skip if we already added this invoice
            if inv["id"] in existing_invoice_ids:
                continue
            
            # IMPORTANT: If invoice has a trade_id, check if trade exists in DB
            # If trade exists and has different status, skip this invoice to avoid duplicates
            if inv.get("trade_id"):
                existing_trade = await db.trades.find_one({"id": inv["trade_id"]}, {"_id": 0, "status": 1})
                if existing_trade:
                    # Skip - trade will be shown from trades collection with correct status
                    continue
            
            # Find related trade if exists
            related_trade = None
            if inv.get("trade_id"):
                related_trade = await db.trades.find_one({"id": inv["trade_id"]}, {"_id": 0})
            
            # Find conversation
            conv = await db.unified_conversations.find_one(
                {"related_id": inv.get("trade_id") or inv["id"]},
                {"_id": 0, "id": 1}
            )
            
            # Use trade_id as primary ID if it exists, otherwise use invoice_id
            # This ensures ALL roles see the SAME ID for the same deal
            primary_id = inv.get("trade_id") or inv["id"]
            
            payment = {
                "id": primary_id,  # Unified ID - same for merchant, trader, admin
                "trade_id": inv.get("trade_id"),
                "invoice_id": inv["id"],
                "status": inv["status"],
                "original_amount_rub": inv.get("original_amount_rub"),
                "client_pays_rub": related_trade.get("client_pays_rub") if related_trade else None,
                "amount_rub": inv.get("original_amount_rub"),  # Show merchant's price, not trader markup
                "amount_usdt": inv.get("amount_usdt"),
                "amount": inv.get("original_amount_rub") or inv.get("amount_rub", 0),
                "fiat_amount": inv.get("original_amount_rub") or inv.get("amount_rub", 0),
                "currency": "RUB",
                "order_id": inv.get("order_id"),
                "created_at": inv.get("created_at"),
                "expires_at": inv.get("expires_at"),
                "completed_at": inv.get("completed_at"),
                "conversation_id": conv["id"] if conv else None,
                "client_nickname": related_trade.get("buyer_nickname") if related_trade else inv.get("buyer_nickname"),
                "source": "invoice_api"
            }
            
            # Add trade details if available
            if related_trade:
                payment["operator_nickname"] = related_trade.get("seller_nickname")
                payment["requisites"] = related_trade.get("requisites")
            
            trades.append(payment)
    
    # Sort by created_at
    trades.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return trades
