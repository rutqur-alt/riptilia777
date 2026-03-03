"""
Admin Chats Routes - Migrated from server.py
Handles merchant chats, dispute chats, application chats, user chats, staff chats, chat management
Also includes basic chat routes for admin/merchant chat system
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List
from datetime import datetime, timezone
import uuid

from core.auth import require_role, get_current_user
from core.websocket import manager
from core.database import db
from models.schemas import MessageCreate, MessageResponse

router = APIRouter(tags=["admin_chats"])


# ==================== BASIC CHAT ROUTES (Admin/Merchant) ====================

@router.get("/chats")
async def get_chats(user: dict = Depends(get_current_user)):
    if user.get("role") == "admin":
        chats = await db.chats.find({}, {"_id": 0}).to_list(100)
    elif user.get("role") == "merchant":
        chats = await db.chats.find({"merchant_id": user["id"]}, {"_id": 0}).to_list(10)
    else:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return chats


@router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(chat_id: str, user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Check access
    if user.get("role") == "merchant" and chat["merchant_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    messages = await db.messages.find({"chat_id": chat_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    
    # Mark as read
    if user.get("role") == "admin":
        await db.chats.update_one({"id": chat_id}, {"$set": {"unread_admin": 0}})
    elif user.get("role") == "merchant":
        await db.chats.update_one({"id": chat_id}, {"$set": {"unread_merchant": 0}})
    
    return messages


@router.post("/chats/{chat_id}/messages", response_model=MessageResponse)
async def send_message(chat_id: str, data: MessageCreate, user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Check access
    if user.get("role") == "merchant" and chat["merchant_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    sender_name = user.get("login", "Unknown")
    if user.get("role") == "admin":
        sender_name = "Администратор"
    elif user.get("role") == "merchant":
        sender_name = user.get("merchant_name", user.get("login"))
    
    msg_doc = {
        "id": str(uuid.uuid4()),
        "chat_id": chat_id,
        "sender_id": user["id"],
        "sender_type": user.get("role"),
        "sender_name": sender_name,
        "content": data.content,
        "attachment_url": data.attachment_url,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.messages.insert_one(msg_doc)
    
    # Update chat
    update_field = "unread_merchant" if user.get("role") == "admin" else "unread_admin"
    await db.chats.update_one(
        {"id": chat_id},
        {
            "$set": {"last_message_at": msg_doc["created_at"]},
            "$inc": {update_field: 1}
        }
    )
    
    # Broadcast via WebSocket
    await manager.broadcast(chat_id, msg_doc)
    
    return msg_doc


# ==================== MERCHANT CHAT ====================

@router.get("/admin/merchant-chat/{merchant_id}")
async def get_merchant_chat(merchant_id: str, user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Get chat messages with merchant"""
    messages = await db.merchant_chats.find(
        {"merchant_id": merchant_id}, 
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return messages


@router.post("/admin/merchant-chat/{merchant_id}")
async def send_merchant_chat(merchant_id: str, data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Send message to merchant"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    msg = {
        "id": str(uuid.uuid4()),
        "merchant_id": merchant_id,
        "sender_id": user["id"],
        "sender_login": user.get("login", "Admin"),
        "sender_role": user.get("admin_role", "admin"),
        "sender_type": "admin",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.merchant_chats.insert_one(msg)
    return {"status": "sent"}


@router.post("/admin/merchant/{merchant_id}/pending-commission")
async def set_pending_commission(merchant_id: str, data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Set pending commission for merchant (before approval)"""
    commission = data.get("commission", 0.5)
    admin_role = user.get("admin_role", "admin")
    
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0, "commission_set_by": 1})
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    if merchant.get("commission_set_by") and admin_role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Только админ может изменить комиссию")
    
    await db.merchants.update_one(
        {"id": merchant_id},
        {"$set": {
            "pending_commission": commission,
            "commission_set_by": user["id"],
            "commission_set_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"status": "saved", "commission": commission}


# ==================== DISPUTE CHAT ====================

@router.get("/admin/dispute-chat/{trade_id}")
async def get_dispute_chat(trade_id: str, user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Get chat messages for a dispute"""
    messages = await db.dispute_chats.find(
        {"trade_id": trade_id}, 
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return messages


@router.post("/admin/dispute-chat/{trade_id}")
async def send_dispute_message(trade_id: str, data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Send message to dispute chat"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": user["id"],
        "sender_login": user.get("login", "Admin"),
        "sender_role": user.get("admin_role", "admin"),
        "sender_type": "admin",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.dispute_chats.insert_one(msg)
    return {"status": "sent"}


# ==================== SHOP APPLICATION CHAT ====================

@router.get("/admin/shop-application-chat/{user_id}")
async def get_shop_application_chat(user_id: str, user: dict = Depends(require_role(["admin", "mod_market"]))):
    """Get chat messages with shop applicant"""
    messages = await db.shop_application_chats.find(
        {"applicant_id": user_id}, 
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return messages


@router.post("/admin/shop-application-chat/{user_id}")
async def send_shop_application_chat(user_id: str, data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_market"]))):
    """Send message to shop applicant"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    msg = {
        "id": str(uuid.uuid4()),
        "applicant_id": user_id,
        "sender_id": user["id"],
        "sender_login": user.get("login", "Admin"),
        "sender_role": user.get("admin_role", "admin"),
        "sender_type": "admin",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.shop_application_chats.insert_one(msg)
    return {"status": "sent"}


# ==================== ADMIN MESSAGES TO USERS ====================

@router.get("/admin/user-messages/{user_id}")
async def get_user_messages(user_id: str, user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get messages between admin/staff and user"""
    messages = await db.admin_user_messages.find(
        {"user_id": user_id}, 
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return messages


@router.post("/admin/user-messages/{user_id}")
async def send_user_message(user_id: str, data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Send message to user"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    msg = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "sender_id": user["id"],
        "sender_login": user.get("login", "Admin"),
        "sender_role": user.get("admin_role", "admin"),
        "sender_type": "admin",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.admin_user_messages.insert_one(msg)
    
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "admin_message",
        "title": "Сообщение от администрации",
        "message": message[:100] + "..." if len(message) > 100 else message,
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"status": "sent"}


# ==================== STAFF CHATS (ЧАТЫ ПЕРСОНАЛА) ====================

@router.post("/admin/staff-chats")
async def create_staff_chat(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))
):
    """Create a new staff chat (group chat for staff members)"""
    name = data.get("name", "")
    participants = data.get("participants", [])
    
    if not name:
        raise HTTPException(status_code=400, detail="Название чата обязательно")
    
    now = datetime.now(timezone.utc).isoformat()
    chat_id = str(uuid.uuid4())
    
    if user["id"] not in participants:
        participants.append(user["id"])
    
    chat = {
        "id": chat_id,
        "type": "staff_chat",
        "name": name,
        "created_by": user["id"],
        "created_by_name": user.get("nickname", user.get("login", "")),
        "staff_participants": participants,
        "left_staff": [],
        "created_at": now,
        "updated_at": now
    }
    await db.unified_conversations.insert_one(chat)
    
    system_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": chat_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"💬 Чат «{name}» создан сотрудником @{user.get('login', 'персонал')}",
        "is_system": True,
        "created_at": now
    }
    await db.unified_messages.insert_one(system_msg)
    
    return {"status": "created", "chat_id": chat_id, "name": name}


@router.get("/admin/staff-chats")
async def get_staff_chats_v2(user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))):
    """Get all staff chats visible to current user"""
    user_id = user["id"]
    admin_role = user.get("admin_role", "admin")
    
    if admin_role in ["owner", "admin"]:
        query = {"type": "staff_chat", "left_staff": {"$ne": user_id}}
    else:
        query = {
            "type": "staff_chat",
            "staff_participants": user_id,
            "left_staff": {"$ne": user_id}
        }
    
    chats = await db.unified_conversations.find(query, {"_id": 0}).sort("updated_at", -1).to_list(50)
    
    for chat in chats:
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": chat["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        chat["last_message"] = last_msg
        
        participant_names = []
        for pid in chat.get("staff_participants", [])[:5]:
            staff = await db.admins.find_one({"id": pid}, {"login": 1, "nickname": 1, "_id": 0})
            if staff:
                participant_names.append(staff.get("nickname", staff.get("login", "")))
        chat["participant_names"] = participant_names
        chat["participants_count"] = len(chat.get("staff_participants", []))
    
    return chats


# ==================== USER CHATS (ЧАТЫ С ПОЛЬЗОВАТЕЛЯМИ) ====================

@router.post("/admin/user-chats")
async def create_user_chat(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))
):
    """Create a new chat with a user (trader or merchant)"""
    target_user_id = data.get("user_id")
    user_type = data.get("user_type", "trader")
    subject = data.get("subject", "")
    
    if not target_user_id:
        raise HTTPException(status_code=400, detail="user_id обязателен")
    
    if user_type == "merchant":
        target = await db.merchants.find_one({"id": target_user_id}, {"_id": 0, "merchant_name": 1, "nickname": 1})
        target_name = target.get("merchant_name", target.get("nickname", "")) if target else "Мерчант"
    else:
        target = await db.traders.find_one({"id": target_user_id}, {"_id": 0, "nickname": 1, "login": 1})
        target_name = target.get("nickname", target.get("login", "")) if target else "Пользователь"
    
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    now = datetime.now(timezone.utc).isoformat()
    chat_id = str(uuid.uuid4())
    
    chat = {
        "id": chat_id,
        "type": "admin_user_chat",
        "target_user_id": target_user_id,
        "target_user_type": user_type,
        "target_user_name": target_name,
        "subject": subject,
        "title": f"Чат с @{target_name}",
        "subtitle": subject or "Сообщение от администрации",
        "created_by": user["id"],
        "created_by_name": user.get("nickname", user.get("login", "")),
        "participants": [target_user_id],
        "staff_participants": [user["id"]],
        "left_staff": [],
        "created_at": now,
        "updated_at": now
    }
    await db.unified_conversations.insert_one(chat)
    
    system_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": chat_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"💬 Чат создан сотрудником @{user.get('login', 'персонал')}" + (f"\n📝 Тема: {subject}" if subject else ""),
        "is_system": True,
        "created_at": now
    }
    await db.unified_messages.insert_one(system_msg)
    
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": target_user_id,
        "type": "new_admin_chat",
        "title": "Новое сообщение от администрации",
        "message": subject or "Администрация начала с вами чат",
        "conversation_id": chat_id,
        "is_read": False,
        "created_at": now
    })
    
    return {"status": "created", "chat_id": chat_id, "target_name": target_name}


@router.get("/admin/user-chats")
async def get_user_chats(user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))):
    """Get admin-to-user chats CREATED by current user only"""
    user_id = user["id"]
    
    query = {
        "type": "admin_user_chat",
        "created_by": user_id,
        "left_staff": {"$ne": user_id}
    }
    
    chats = await db.unified_conversations.find(query, {"_id": 0}).sort("updated_at", -1).to_list(100)
    
    for chat in chats:
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": chat["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        chat["last_message"] = last_msg
    
    return chats


@router.get("/admin/invited-chats")
async def get_invited_chats(user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))):
    """Get all chats where current staff member was INVITED to participate"""
    user_id = user["id"]
    
    all_chats = []
    
    conv_query = {
        "staff_participants": user_id,
        "left_staff": {"$ne": user_id}
    }
    
    conversations = await db.unified_conversations.find(conv_query, {"_id": 0}).sort("updated_at", -1).to_list(200)
    
    type_labels = {
        "p2p_dispute": "🔴 Спор P2P",
        "merchant_application": "💼 Заявка мерчанта",
        "shop_application": "🏪 Заявка магазина",
        "marketplace_guarantor": "🛡️ Гарант-сделка",
        "admin_user_chat": "💬 Чат с пользователем",
        "staff_chat": "👥 Чат персонала"
    }
    
    for conv in conversations:
        conv_type = conv.get("type", "chat")
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        
        title = conv.get("title", "")
        if not title:
            if conv_type == "admin_user_chat":
                title = f"Чат с @{conv.get('target_user_name', 'пользователь')}"
            elif conv_type == "p2p_dispute":
                title = f"Спор #{conv.get('related_id', '')[:8]}"
            elif conv_type == "merchant_application":
                title = f"Заявка: {conv.get('user_name', 'мерчант')}"
            elif conv_type == "shop_application":
                title = f"Магазин: {conv.get('user_name', 'заявка')}"
            else:
                title = conv.get("user_name", "Чат")
        
        all_chats.append({
            "id": conv["id"],
            "type": conv_type,
            "title": title,
            "subtitle": type_labels.get(conv_type, conv_type),
            "subject": conv.get("subject", ""),
            "last_message": last_msg,
            "updated_at": conv.get("updated_at"),
            "created_at": conv.get("created_at"),
            "unread_count": conv.get("unread_counts", {}).get(user_id, 0),
            "staff_participants": conv.get("staff_participants", []),
            "related_id": conv.get("related_id"),
            "data": conv
        })
    
    all_chats.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    
    return all_chats


# ==================== CHAT MANAGEMENT (LEAVE/ARCHIVE/DELETE/SEARCH) ====================

@router.post("/msg/conversations/{conversation_id}/leave")
async def leave_conversation(conversation_id: str, user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Leave a conversation - the conversation disappears from staff's chat list
    
    RESTRICTIONS:
    - Cannot leave if conversation requires action (active order, pending dispute, etc.)
    - Cannot leave crypto_order chats that are pending/in progress
    - Cannot leave disputes that are not resolved
    """
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    conv_type = conv.get("type", "")
    conv_status = conv.get("status", "")
    
    # CHECK: Cannot leave if conversation requires action
    # 1. Crypto orders (payouts) - cannot leave if pending/active
    if conv_type == "crypto_order":
        related_id = conv.get("related_id")
        if related_id:
            order = await db.crypto_orders.find_one({"id": related_id}, {"_id": 0})
            if order:
                order_status = order.get("status", "")
                if order_status in ["pending", "paid", "dispute"]:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Невозможно выйти: заказ требует решения (статус: {order_status})"
                    )
    
    # 2. P2P disputes - cannot leave if not resolved
    if conv_type in ["p2p_dispute", "p2p_trade"]:
        if conv_status not in ["resolved", "closed", "completed"]:
            raise HTTPException(
                status_code=400,
                detail="Невозможно выйти: спор требует решения"
            )
    
    # 3. Guarantor deals - cannot leave if active
    if conv_type == "marketplace_guarantor":
        related_id = conv.get("related_id")
        if related_id:
            order = await db.marketplace_orders.find_one({"id": related_id}, {"_id": 0})
            if order and order.get("status") in ["guarantor_active", "pending"]:
                raise HTTPException(
                    status_code=400,
                    detail="Невозможно выйти: гарант-сделка активна"
                )
    
    # 4. Support tickets - cannot leave if open
    if conv_type == "support_ticket":
        related_id = conv.get("related_id")
        if related_id:
            ticket = await db.support_tickets.find_one({"id": related_id}, {"_id": 0})
            if ticket and ticket.get("status") == "open":
                raise HTTPException(
                    status_code=400,
                    detail="Невозможно выйти: тикет открыт и требует ответа"
                )
    
    # 5. Merchant applications - cannot leave if pending
    if conv_type == "merchant_application":
        related_id = conv.get("related_id")
        if related_id:
            app = await db.merchant_applications.find_one({"id": related_id}, {"_id": 0})
            if app and app.get("status") == "pending":
                raise HTTPException(
                    status_code=400,
                    detail="Невозможно выйти: заявка ожидает рассмотрения"
                )
    
    # 6. Shop applications - cannot leave if pending
    if conv_type == "shop_application":
        related_id = conv.get("related_id")
        if related_id:
            app = await db.shop_applications.find_one({"id": related_id}, {"_id": 0})
            if app and app.get("status") == "pending":
                raise HTTPException(
                    status_code=400,
                    detail="Невозможно выйти: заявка ожидает рассмотрения"
                )
    
    user_id = user["id"]
    now = datetime.now(timezone.utc).isoformat()
    
    # Get role label for system message
    role_labels = {
        "owner": "👑 Владелец",
        "admin": "🔴 Администратор",
        "mod_p2p": "🟡 Модератор P2P",
        "mod_market": "🟡 Гарант",
        "support": "🔵 Поддержка"
    }
    role_label = role_labels.get(user.get("admin_role", ""), "Сотрудник")
    user_name = user.get("nickname") or user.get("login", "Сотрудник")
    
    # Add system message about leaving
    leave_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"👋 {role_label} @{user_name} покинул чат",
        "is_system": True,
        "created_at": now
    }
    await db.unified_messages.insert_one(leave_msg)
    
    # Remove staff from staff_participants
    update_ops = {
        "$pull": {"staff_participants": user_id},
        "$addToSet": {"left_staff": user_id},
        "$set": {"updated_at": now}
    }
    
    # If staff was assigned to this conversation, unassign
    if conv.get("assigned_to") == user_id:
        update_ops["$set"]["assigned_to"] = None
        update_ops["$set"]["assigned_to_name"] = None
        update_ops["$set"]["assigned_at"] = None
    
    await db.unified_conversations.update_one({"id": conversation_id}, update_ops)
    
    return {"status": "left", "message": "Вы вышли из чата"}


@router.post("/msg/conversations/{conversation_id}/archive")
async def archive_conversation(conversation_id: str, user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Archive a conversation"""
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "status": "archived",
            "archived_by": user["id"],
            "archived_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"status": "archived"}


@router.delete("/msg/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(require_role(["admin"]))):
    """Delete a conversation (admin only)"""
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "deleted": True,
            "deleted_by": user["id"],
            "deleted_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"status": "deleted"}


@router.get("/msg/conversations/search")
async def search_conversations(
    q: str,
    limit: int = 20,
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))
):
    """Search conversations by title or participant"""
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Минимум 2 символа для поиска")
    
    user_id = user["id"]
    admin_role = user.get("admin_role", "admin")
    
    base_query = {
        "deleted": {"$ne": True},
        "$or": [
            {"title": {"$regex": q, "$options": "i"}},
            {"target_user_name": {"$regex": q, "$options": "i"}},
            {"name": {"$regex": q, "$options": "i"}}
        ]
    }
    
    if admin_role not in ["owner", "admin"]:
        base_query["$and"] = [
            {"$or": [
                {"staff_participants": user_id},
                {"participants": user_id},
                {"created_by": user_id}
            ]}
        ]
    
    conversations = await db.unified_conversations.find(base_query, {"_id": 0}).limit(limit).to_list(limit)
    
    for conv in conversations:
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        conv["last_message"] = last_msg
    
    return {"results": conversations, "total": len(conversations)}


@router.post("/msg/conversations/{conversation_id}/add-staff")
async def add_staff_to_conversation(
    conversation_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Add staff member to conversation"""
    staff_id = data.get("staff_id")
    if not staff_id:
        raise HTTPException(status_code=400, detail="staff_id обязателен")
    
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    staff = await db.admins.find_one({"id": staff_id}, {"_id": 0})
    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {
            "$addToSet": {"staff_participants": staff_id},
            "$pull": {"left_staff": staff_id}
        }
    )
    
    sys_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"➕ @{staff.get('login', 'сотрудник')} добавлен в чат",
        "is_system": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(sys_msg)
    
    return {"status": "added", "staff_name": staff.get("login")}


@router.post("/msg/conversations/{conversation_id}/remove-staff")
async def remove_staff_from_conversation(
    conversation_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin"]))
):
    """Remove staff member from conversation (admin only)"""
    staff_id = data.get("staff_id")
    if not staff_id:
        raise HTTPException(status_code=400, detail="staff_id обязателен")
    
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    staff = await db.admins.find_one({"id": staff_id}, {"_id": 0})
    
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$addToSet": {"left_staff": staff_id}}
    )
    
    sys_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"➖ @{staff.get('login', 'сотрудник') if staff else 'сотрудник'} удалён из чата",
        "is_system": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(sys_msg)
    
    return {"status": "removed"}


# ==================== APPLICATION CHATS ====================

# Role colors for UI
MSG_ROLE_COLORS = {
    "owner": "#ff0000",
    "admin": "#ff4444",
    "mod_p2p": "#ffa500",
    "mod_market": "#ffa500",
    "support": "#4488ff",
    "merchant": "#00cc00",
    "user": "#888888",
    "system": "#666666"
}

def get_msg_role_info(role: str, name: str = ""):
    """Get role display info"""
    labels = {
        "owner": "👑 Владелец",
        "admin": "🔴 Админ",
        "mod_p2p": "🟡 P2P Мод",
        "mod_market": "🟡 Гарант",
        "support": "🔵 Поддержка",
        "merchant": "💼 Мерчант",
        "user": "👤 Пользователь",
        "system": "🤖 Система"
    }
    return {
        "role": role,
        "label": labels.get(role, role),
        "color": MSG_ROLE_COLORS.get(role, "#888888"),
        "name": name
    }


@router.get("/msg/application/{app_type}/{user_id}")
async def get_application_chat(
    app_type: str,
    user_id: str,
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Get chat for merchant/shop application"""
    if app_type not in ["merchant", "shop"]:
        raise HTTPException(status_code=400, detail="Неверный тип заявки")
    
    conv_type = "merchant_application" if app_type == "merchant" else "shop_application"
    
    conv = await db.unified_conversations.find_one(
        {"type": conv_type, "related_id": user_id},
        {"_id": 0}
    )
    
    if not conv:
        # Create conversation
        from core.database import db as server_db
        applicant = await db.traders.find_one({"id": user_id}, {"_id": 0}) if app_type == "shop" else await db.merchants.find_one({"id": user_id}, {"_id": 0})
        if not applicant:
            raise HTTPException(status_code=404, detail="Заявитель не найден")
        
        applicant_name = applicant.get("nickname", applicant.get("company_name", applicant.get("login", "Заявитель")))
        admin_name = user.get("login", "Администратор")
        admin_role = user.get("admin_role", "admin")
        
        conv = {
            "id": str(uuid.uuid4()),
            "type": conv_type,
            "status": "active",
            "related_id": user_id,
            "title": f"Заявка на {'мерчанта' if app_type == 'merchant' else 'магазин'}: {applicant_name}",
            "delete_locked": False,
            "participants": [
                {"user_id": user_id, "role": "merchant" if app_type == "merchant" else "user", "name": applicant_name},
                {"user_id": user["id"], "role": admin_role, "name": admin_name}
            ],
            "unread_counts": {user_id: 0, user["id"]: 0},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.unified_conversations.insert_one(conv)
    
    # Get messages
    messages = await db.unified_messages.find(
        {"conversation_id": conv["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    
    for msg in messages:
        msg["sender_info"] = get_msg_role_info(msg.get("sender_role", "user"), msg.get("sender_name", ""))
    
    return {"conversation": conv, "messages": messages, "role_colors": MSG_ROLE_COLORS}


# ==================== ADMIN: VIEW ALL DISPUTED TRADES ====================

@router.get("/msg/admin/disputes")
async def get_all_disputes_with_chats(user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Get all disputed trades with their conversation IDs (exclude resolved)"""
    user_id = user["id"]
    admin_role = user.get("admin_role", "admin")
    
    # Get disputed trades
    query = {"status": {"$in": ["disputed", "dispute"]}}
    trades = await db.trades.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    disputes = []
    for trade in trades:
        # Find conversation for this trade
        conv = await db.unified_conversations.find_one(
            {"type": {"$in": ["p2p_trade", "p2p_dispute"]}, "related_id": trade["id"]},
            {"_id": 0, "id": 1, "status": 1}
        )
        
        # Get seller and buyer info
        seller = await db.traders.find_one({"id": trade.get("trader_id")}, {"_id": 0, "login": 1, "nickname": 1})
        buyer = await db.traders.find_one({"id": trade.get("buyer_id")}, {"_id": 0, "login": 1, "nickname": 1}) if trade.get("buyer_id") else None
        
        disputes.append({
            "trade": trade,
            "conversation_id": conv["id"] if conv else None,
            "seller": seller,
            "buyer": buyer
        })
    
    return disputes


@router.get("/admin/conversations")
async def get_all_conversations_admin(user: dict = Depends(require_role(["admin"]))):
    """Get all private conversations for monitoring"""
    conversations = await db.conversations.find({}, {"_id": 0}).sort("last_message_at", -1).limit(100).to_list(100)
    return conversations


@router.get("/admin/conversations/{conversation_id}/messages")
async def get_conversation_messages_admin(conversation_id: str, user: dict = Depends(require_role(["admin"]))):
    """Get all messages in a conversation"""
    messages = await db.unified_messages.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    if not messages:
        messages = await db.private_messages.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return messages


@router.get("/admin/unified-support-tickets")
async def get_unified_support_tickets(user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))):
    """Get support tickets from unified_conversations"""
    query = {
        "type": "support_ticket",
        "status": {"$ne": "archived"}
    }
    convs = await db.unified_conversations.find(query, {"_id": 0}).sort("updated_at", -1).to_list(100)
    
    result = []
    for conv in convs:
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        
        # Get user info from participants
        user_name = "Пользователь"
        user_nickname = ""
        for p in conv.get("participants", []):
            if p.get("role") == "user":
                user_name = p.get("name", "Пользователь")
                user_nickname = p.get("name", "")
                break
        
        result.append({
            "id": conv["id"],
            "subject": conv.get("title", "Обращение в поддержку"),
            "category": conv.get("category", "other"),
            "category_name": conv.get("category", "другое"),
            "status": conv.get("status", "active"),
            "user_nickname": user_nickname,
            "user_id": next((p["user_id"] for p in conv.get("participants", []) if p.get("role") == "user"), None),
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at"),
            "last_message": last_msg.get("content", "") if last_msg else "",
            "unread_count": 0,
            "source": "unified"
        })
    
    return result
