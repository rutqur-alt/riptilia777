"""
Chat Management Routes - Migrated from server.py
Handles user leave/archive, admin search, delete, archived, add/remove staff
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.auth import require_role, get_current_user, log_admin_action
from core.database import db

router = APIRouter(tags=["chat_management"])


# ==================== USER CHAT ACTIONS (LEAVE/ARCHIVE) ====================

@router.post("/msg/user/conversation/{conversation_id}/leave")
async def user_leave_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    """User or merchant leaves a conversation
    
    User can leave only if the conversation is completed/resolved.
    After leaving, user cannot see messages but can still view archived conversation.
    """
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    user_id = user["id"]
    participants = conv.get("participants", [])
    
    # Check if user is participant
    is_participant = False
    for p in participants:
        if p.get("id") == user_id:
            is_participant = True
            break
    
    if not is_participant:
        raise HTTPException(status_code=403, detail="Вы не участник этого чата")
    
    conv_type = conv.get("type", "")
    conv_status = conv.get("status", "")
    
    # Check if conversation can be left (only completed/resolved conversations)
    active_statuses = ["pending", "active", "paid", "dispute", "in_progress", "pending_delivery"]
    if conv_status in active_statuses:
        raise HTTPException(
            status_code=400,
            detail="Невозможно выйти: разговор ещё активен"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    user_name = user.get("nickname") or user.get("login", "Пользователь")
    
    # Add system message about leaving
    leave_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"👋 @{user_name} покинул чат",
        "is_system": True,
        "created_at": now
    }
    await db.unified_messages.insert_one(leave_msg)
    
    # Mark user as left
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {
            "$addToSet": {"left_participants": user_id},
            "$set": {"updated_at": now}
        }
    )
    
    return {"status": "left", "message": "Вы вышли из чата"}


@router.post("/msg/user/conversation/{conversation_id}/archive")
async def user_archive_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    """Archive conversation when user is the last one remaining
    
    Only the last remaining participant can archive the conversation.
    """
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    user_id = user["id"]
    participants = conv.get("participants", [])
    left_participants = conv.get("left_participants", [])
    staff_participants = conv.get("staff_participants", [])
    left_staff = conv.get("left_staff", [])
    
    # Count active participants
    active_user_participants = [p for p in participants if p.get("id") not in left_participants]
    active_staff = [s for s in staff_participants if s not in left_staff]
    
    total_active = len(active_user_participants) + len(active_staff)
    
    # Check if user is the last one
    if total_active > 1:
        raise HTTPException(
            status_code=400,
            detail="Только последний участник может архивировать чат"
        )
    
    # Check if user is participant
    is_participant = False
    for p in participants:
        if p.get("id") == user_id:
            is_participant = True
            break
    
    if not is_participant:
        raise HTTPException(status_code=403, detail="Вы не участник этого чата")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Archive the conversation
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "status": "archived",
            "archived": True,
            "archived_at": now,
            "archived_by": user_id,
            "updated_at": now
        }}
    )
    
    # Add system message
    archive_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": "📁 Чат был архивирован",
        "is_system": True,
        "created_at": now
    }
    await db.unified_messages.insert_one(archive_msg)
    
    return {"status": "archived", "message": "Чат архивирован"}




# ==================== ADMIN ARCHIVE ====================

@router.post("/msg/conversations/{conversation_id}/archive")
async def admin_archive_conversation(conversation_id: str, user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Archive conversation (admin/staff only)"""
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "status": "archived",
            "archived": True,
            "archived_at": now,
            "archived_by": user["id"],
            "updated_at": now
        }}
    )
    
    archive_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": "Чат архивирован администратором",
        "is_system": True,
        "created_at": now
    }
    await db.unified_messages.insert_one(archive_msg)
    
    return {"status": "archived", "message": "Чат архивирован"}

# ==================== ADMIN SEARCH ====================

@router.get("/msg/admin/search")
async def search_conversations(
    q: str = "",
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))
):
    """Search conversations by title, subtitle, nickname, merchant name, shop name
    
    Returns conversations matching the search query that are visible to current staff.
    """
    if not q or len(q) < 2:
        return []
    
    # Build search query
    search_regex = {"$regex": q, "$options": "i"}
    
    query = {
        "$or": [
            {"title": search_regex},
            {"subtitle": search_regex},
            {"merchant_name": search_regex},
            {"nickname": search_regex},
            {"data.merchant_name": search_regex},
            {"data.shop_name": search_regex},
            {"data.nickname": search_regex}
        ],
        "deleted": {"$ne": True},
        "resolved": {"$ne": True}
    }
    
    # Role-based filtering
    admin_role = user.get("admin_role", "admin")
    user_id = user["id"]
    
    # Filter out conversations that this staff has left (unless admin/owner)
    if admin_role not in ["owner", "admin"]:
        query["left_staff"] = {"$ne": user_id}
        
        # Also filter by type based on role
        if admin_role == "mod_p2p":
            query["type"] = {"$in": ["p2p_trade", "p2p_dispute", "merchant_application"]}
        elif admin_role == "mod_market":
            query["type"] = {"$in": ["marketplace_guarantor", "shop_application"]}
        elif admin_role == "support":
            query["type"] = "support_ticket"
    
    convs = await db.unified_conversations.find(query, {"_id": 0}).sort("updated_at", -1).limit(50).to_list(50)
    
    return convs


# ==================== ADMIN DELETE CONVERSATION ====================

@router.delete("/msg/conversations/{conversation_id}")
async def delete_conversation_admin_v2(conversation_id: str, user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))):
    """Delete a conversation (only resolved/archived conversations can be deleted)
    
    Rules:
    - Only admin/moderator can delete
    - Only resolved/archived conversations can be deleted
    - Messages are permanently removed from the database
    - The conversation is kept for audit but marked as deleted
    """
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    # Check if conversation is resolved or archived
    if not conv.get("resolved") and not conv.get("archived"):
        raise HTTPException(status_code=400, detail="Можно удалять только решённые/архивные чаты")
    
    # Mark conversation as deleted (soft delete for audit)
    now = datetime.now(timezone.utc).isoformat()
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "deleted": True,
            "deleted_at": now,
            "deleted_by": user["id"],
            "deleted_by_login": user.get("login", "")
        }}
    )
    
    # Delete all messages from this conversation
    deleted_count = await db.unified_messages.delete_many({"conversation_id": conversation_id})
    
    # Log action
    await log_admin_action(user["id"], "delete_conversation", "conversation", conversation_id, {
        "conv_type": conv.get("type"),
        "related_id": conv.get("related_id"),
        "messages_deleted": deleted_count.deleted_count
    })
    
    return {"status": "deleted", "messages_deleted": deleted_count.deleted_count}


# ==================== ADMIN ARCHIVED CONVERSATIONS ====================

@router.get("/msg/admin/archived")
async def get_archived_conversations(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get archived conversations for current staff member
    
    Returns conversations that:
    - Current user has left (user_id in left_staff) OR
    - Are closed/archived globally
    """
    user_id = user["id"]
    admin_role = user.get("admin_role", "admin")
    
    # Get conversations where user left OR globally archived
    query = {
        "$or": [
            {"left_staff": user_id},  # User left this chat
            {"status": "closed"},
            {"archived": True}
        ],
        "deleted": {"$ne": True}
    }
    
    convs = await db.unified_conversations.find(query, {"_id": 0}).sort("updated_at", -1).to_list(200)
    
    type_labels = {
        "p2p_dispute": "🔴 P2P Споры",
        "p2p_trade": "🔴 P2P Споры",
        "merchant_application": "💼 Заявки мерчантов",
        "shop_application": "🏪 Заявки магазинов",
        "marketplace_guarantor": "🛡️ Гарант-сделки",
        "admin_user_chat": "💬 Пользователям",
        "support_ticket": "🎫 Поддержка",
        "staff_chat": "👥 Персонал",
        "crypto_order": "💰 Выплаты",
        "invited_user": "👥 Приглашенные"
    }
    
    # Enrich with additional info
    for conv in convs:
        conv_type = conv.get("type", "chat")
        conv["category_label"] = type_labels.get(conv_type, conv_type)
        conv["is_left_by_me"] = user_id in conv.get("left_staff", [])
        
        # Get who closed it
        if conv.get("closed_by"):
            closer = await db.admins.find_one({"id": conv["closed_by"]}, {"login": 1, "nickname": 1, "_id": 0})
            if closer:
                conv["closed_by_name"] = closer.get("nickname", closer.get("login", ""))
        
        # Get last message
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        conv["last_message"] = last_msg
        
        # Build title
        title = conv.get("title", "")
        if not title:
            if conv_type == "admin_user_chat":
                title = f"Чат с @{conv.get('target_user_name', 'пользователь')}"
            elif conv_type in ["p2p_dispute", "p2p_trade"]:
                title = f"Спор #{conv.get('related_id', '')[:8]}"
            elif conv_type == "merchant_application":
                title = f"Заявка: {conv.get('user_name', 'мерчант')}"
            elif conv_type == "shop_application":
                title = f"Магазин: {conv.get('user_name', '')}"
            else:
                title = conv.get("user_name", "Чат")
        conv["title"] = title
    
    # Also get archived support tickets where user left
    ticket_query = {
        "$or": [
            {"left_by_staff": user_id},
            {"status": "closed"}
        ]
    }
    tickets = await db.support_tickets.find(ticket_query, {"_id": 0}).sort("updated_at", -1).to_list(50)
    
    for ticket in tickets:
        last_msg = await db.ticket_messages.find_one(
            {"ticket_id": ticket["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        convs.append({
            "id": f"ticket_{ticket['id']}",
            "related_id": ticket["id"],
            "type": "support_ticket",
            "title": ticket.get("subject", "Обращение"),
            "subtitle": f"@{ticket.get('user_nickname', '?')}",
            "category_label": "🎫 Поддержка",
            "is_left_by_me": user_id in ticket.get("left_by_staff", []),
            "last_message": last_msg,
            "updated_at": ticket.get("updated_at"),
            "created_at": ticket.get("created_at"),
            "status": ticket.get("status"),
            "data": ticket
        })
    
    # Sort by updated_at
    convs.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    
    return convs


# ==================== ADD/REMOVE STAFF TO CONVERSATION ====================

@router.post("/msg/conversations/{conversation_id}/add-staff")
async def add_staff_to_conversation(
    conversation_id: str, 
    data: dict = Body(...), 
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))
):
    """Add a staff member to a conversation
    
    This allows any staff member to add another staff member to a conversation.
    The added staff member will be able to see and participate in the conversation.
    
    Body:
    - staff_id: ID of the staff member to add
    """
    staff_id = data.get("staff_id")
    if not staff_id:
        raise HTTPException(status_code=400, detail="staff_id обязателен")
    
    # Check if conversation exists
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    # Check if conversation is closed
    if conv.get("status") == "closed":
        raise HTTPException(status_code=400, detail="Невозможно добавить персонал в закрытый чат")
    
    # Check if staff member exists
    staff = await db.admins.find_one({"id": staff_id}, {"_id": 0})
    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    
    # Check if staff is already in participants
    participants = conv.get("participants", [])
    staff_participants = conv.get("staff_participants", [])
    
    if staff_id in participants or staff_id in staff_participants:
        raise HTTPException(status_code=400, detail="Сотрудник уже добавлен в чат")
    
    # Add staff to conversation
    now = datetime.now(timezone.utc).isoformat()
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {
            "$addToSet": {"staff_participants": staff_id},
            "$set": {"updated_at": now}
        }
    )
    
    # Get role label for system message
    role_labels = {
        "owner": "👑 Владелец",
        "admin": "🔴 Администратор",
        "mod_p2p": "🟡 Модератор P2P",
        "mod_market": "🟡 Гарант",
        "support": "🔵 Поддержка"
    }
    role_label = role_labels.get(staff.get("admin_role", ""), staff.get("admin_role", "Персонал"))
    
    # Add system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"🔔 {role_label} @{staff.get('login', 'Сотрудник')} добавлен в чат сотрудником @{user.get('login', 'персонал')}",
        "is_system": True,
        "created_at": now
    }
    await db.unified_messages.insert_one(system_msg)
    
    # Create notification for added staff
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": staff_id,
        "type": "added_to_conversation",
        "title": "Вы добавлены в чат",
        "message": f"Сотрудник @{user.get('login')} добавил вас в чат",
        "conversation_id": conversation_id,
        "is_read": False,
        "created_at": now
    })
    
    # Log action
    await log_admin_action(user["id"], "add_staff_to_conversation", "conversation", conversation_id, {
        "added_staff_id": staff_id,
        "added_staff_login": staff.get("login")
    })
    
    return {"status": "added", "staff_login": staff.get("login"), "staff_role": staff.get("admin_role")}


@router.get("/msg/admin/staff-list")
async def get_staff_for_adding(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get list of staff members that can be added to conversations"""
    staff = await db.admins.find(
        {"id": {"$ne": user["id"]}},  # Exclude current user
        {"_id": 0, "password_hash": 0, "password": 0}
    ).to_list(100)
    
    # Add role labels
    role_labels = {
        "owner": "👑 Владелец",
        "admin": "🔴 Админ",
        "mod_p2p": "🟡 P2P Мод",
        "mod_market": "🟡 Гарант",
        "support": "🔵 Поддержка"
    }
    
    for s in staff:
        s["role_label"] = role_labels.get(s.get("admin_role", ""), s.get("admin_role", ""))
    
    return staff


@router.delete("/msg/conversations/{conversation_id}/staff/{staff_id}")
async def remove_staff_from_conversation(
    conversation_id: str,
    staff_id: str,
    user: dict = Depends(require_role(["admin"]))
):
    """Remove a staff member from a conversation (admin only)"""
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    # Remove staff from conversation
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$pull": {"staff_participants": staff_id}}
    )
    
    # Get staff info for message
    staff = await db.admins.find_one({"id": staff_id}, {"login": 1, "_id": 0})
    staff_login = staff.get("login", "Сотрудник") if staff else "Сотрудник"
    
    # Add system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"❌ Сотрудник @{staff_login} удалён из чата",
        "is_system": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(system_msg)
    
    return {"status": "removed", "staff_login": staff_login}
