from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.auth import require_role, get_current_user, log_admin_action
from core.database import db

router = APIRouter()

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


# ==================== ADMIN DELETE CONVERSATION ====================

@router.delete("/msg/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))):
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
