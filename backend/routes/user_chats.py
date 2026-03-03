"""
User Chats Routes - Migrated from server.py
User-side endpoints for viewing and replying to admin messages, merchant chats, shop application chats
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.auth import get_current_user
from core.database import db

router = APIRouter(tags=["user_chats"])


# ==================== USER MESSAGES FROM ADMIN (User side) ====================

@router.get("/my/admin-messages")
async def get_my_admin_messages(user: dict = Depends(get_current_user)):
    """Get messages from admin/staff to current user"""
    messages = await db.admin_user_messages.find(
        {"user_id": user["id"]}, 
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return messages


@router.post("/my/admin-messages/reply")
async def reply_to_admin_message(data: dict = Body(...), user: dict = Depends(get_current_user)):
    """User replies to admin messages"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    msg = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "sender_id": user["id"],
        "sender_login": user.get("login", user.get("nickname", "User")),
        "sender_role": "user",
        "sender_type": "user",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.admin_user_messages.insert_one(msg)
    return {"status": "sent"}


@router.get("/my/admin-messages/unread")
async def get_unread_admin_messages_count(user: dict = Depends(get_current_user)):
    """Get count of unread messages from admin"""
    count = await db.admin_user_messages.count_documents({
        "user_id": user["id"],
        "sender_type": "admin",
        "read": {"$ne": True}
    })
    return {"unread": count}


# ==================== MERCHANT APPLICATION CHAT ====================

@router.get("/my/merchant-chat")
async def get_my_merchant_chat(user: dict = Depends(get_current_user)):
    """Get merchant's application chat (unified conversations)"""
    user_id = user["id"]
    
    # Find merchant's application conversation
    conv = await db.unified_conversations.find_one(
        {"type": "merchant_application", "participants": {"$in": [user_id]}},
        {"_id": 0}
    )
    
    if not conv:
        # Try to find by related merchant application
        app = await db.merchant_applications.find_one({"user_id": user_id}, {"_id": 0})
        if app:
            conv = await db.unified_conversations.find_one(
                {"type": "merchant_application", "related_id": app["id"]},
                {"_id": 0}
            )
    
    if not conv:
        return {"conversation": None, "messages": []}
    
    # Get messages
    messages = await db.unified_messages.find(
        {"conversation_id": conv["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    return {"conversation": conv, "messages": messages}


@router.post("/my/merchant-chat/send")
async def send_merchant_chat_message(data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Send message in merchant's application chat"""
    user_id = user["id"]
    content = data.get("content", "").strip()
    
    if not content:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    # Find conversation
    conv = await db.unified_conversations.find_one(
        {"type": "merchant_application", "participants": {"$in": [user_id]}},
        {"_id": 0}
    )
    
    if not conv:
        app = await db.merchant_applications.find_one({"user_id": user_id}, {"_id": 0})
        if app:
            conv = await db.unified_conversations.find_one(
                {"type": "merchant_application", "related_id": app["id"]},
                {"_id": 0}
            )
    
    if not conv:
        raise HTTPException(status_code=404, detail="Чат заявки не найден")
    
    # Create message
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": user_id,
        "sender_nickname": user.get("nickname", user.get("merchant_name", user.get("login", "Мерчант"))),
        "sender_role": "merchant",
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.unified_messages.insert_one(msg)
    
    # Update conversation
    await db.unified_conversations.update_one(
        {"id": conv["id"]},
        {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    msg.pop("_id", None)
    return msg


# ==================== SHOP APPLICATION CHAT (for user) ====================

@router.get("/my/shop-application-chat")
async def get_my_shop_application_chat(user: dict = Depends(get_current_user)):
    """Get user's shop application chat (unified conversations)"""
    user_id = user["id"]
    
    # Find user's shop application conversation
    conv = await db.unified_conversations.find_one(
        {"type": "shop_application", "participants": {"$in": [user_id]}},
        {"_id": 0}
    )
    
    if not conv:
        # Try to find by related shop application
        app = await db.shop_applications.find_one({"user_id": user_id, "status": "pending"}, {"_id": 0})
        if app:
            conv = await db.unified_conversations.find_one(
                {"type": "shop_application", "related_id": app["id"]},
                {"_id": 0}
            )
    
    if not conv:
        return {"conversation": None, "messages": []}
    
    # Get messages
    messages = await db.unified_messages.find(
        {"conversation_id": conv["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    return {"conversation": conv, "messages": messages}


@router.post("/my/shop-application-chat/send")
async def send_shop_application_chat_message(data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Send message in user's shop application chat"""
    user_id = user["id"]
    content = data.get("content", "").strip()
    
    if not content:
        raise HTTPException(status_code=400, detail="Сообщение не може быть пустым")
    
    # Find conversation
    conv = await db.unified_conversations.find_one(
        {"type": "shop_application", "participants": {"$in": [user_id]}},
        {"_id": 0}
    )
    
    if not conv:
        app = await db.shop_applications.find_one({"user_id": user_id, "status": "pending"}, {"_id": 0})
        if app:
            conv = await db.unified_conversations.find_one(
                {"type": "shop_application", "related_id": app["id"]},
                {"_id": 0}
            )
    
    if not conv:
        raise HTTPException(status_code=404, detail="Чат заявки не найден")
    
    # Create message
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": user_id,
        "sender_nickname": user.get("nickname", user.get("login", "Пользователь")),
        "sender_role": "user",
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.unified_messages.insert_one(msg)
    
    # Update conversation
    await db.unified_conversations.update_one(
        {"id": conv["id"]},
        {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    msg.pop("_id", None)
    return msg
