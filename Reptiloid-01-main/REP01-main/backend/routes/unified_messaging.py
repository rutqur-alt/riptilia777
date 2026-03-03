"""
Unified Messaging Routes - Migrated from server.py
Handles the unified messaging system, staff chat, and message management
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone, timedelta
import uuid

from core.auth import require_role, get_current_user
from server import db

router = APIRouter(tags=["messaging"])


# ==================== MESSAGE ROLE CONFIGURATION ====================

MSG_ROLE_COLORS = {
    "user": "#FFFFFF", "buyer": "#FFFFFF", "p2p_seller": "#FFFFFF",
    "shop_owner": "#8B5CF6", "merchant": "#F97316",
    "mod_p2p": "#F59E0B", "mod_market": "#F59E0B",
    "support": "#3B82F6", "admin": "#EF4444", "owner": "#EF4444",
    "system": "#6B7280"
}

MSG_ROLE_ICONS = {"p2p_seller": "💱", "mod_market": "⚖️", "shop_owner": "🏪", "merchant": "🏢"}

MSG_ROLE_NAMES = {
    "user": "Пользователь", "buyer": "Покупатель", "p2p_seller": "Продавец",
    "shop_owner": "Магазин", "merchant": "Мерчант",
    "mod_p2p": "Модератор P2P", "mod_market": "Гарант",
    "support": "Поддержка", "admin": "Администратор", "owner": "Владелец",
    "system": "Система"
}


def get_msg_role_info(role: str, name: str) -> dict:
    """Get display info for message sender"""
    return {
        "name": name,
        "role": role,
        "role_name": MSG_ROLE_NAMES.get(role, role),
        "color": MSG_ROLE_COLORS.get(role, "#FFFFFF"),
        "icon": MSG_ROLE_ICONS.get(role, "")
    }


def can_user_delete_msg(conv_type: str, conv_status: str, user_role: str, is_sender: bool, msg_age_sec: int) -> tuple:
    """Check if user can delete message according to spec"""
    FIVE_MIN = 300
    
    # Admin can delete ALL messages everywhere
    if user_role in ["admin", "owner"]:
        return True, "admin"
    
    # Moderators
    if user_role in ["mod_p2p", "mod_market"]:
        if conv_status == "dispute":
            if is_sender and msg_age_sec <= FIVE_MIN:
                return True, "mod_own"
            if not is_sender:
                return False, "mod_cannot_delete_others_in_dispute"
            return False, "expired"
        if conv_type in ["forum_topic", "support_ticket"]:
            if not is_sender:
                return True, "mod_delete_others"
            if msg_age_sec <= FIVE_MIN:
                return True, "mod_own"
            return False, "expired"
        if conv_type in ["internal_discussion", "staff_chat"]:
            if is_sender and msg_age_sec <= FIVE_MIN:
                return True, "mod_own"
            return False, "denied"
        return False, "mod_no_access"
    
    # Support
    if user_role == "support":
        if conv_type == "support_ticket":
            if not is_sender:
                return True, "support_delete_others"
            if is_sender and msg_age_sec <= FIVE_MIN:
                return True, "support_own"
            return False, "expired"
        if conv_type == "forum_topic":
            if not is_sender:
                return True, "support_delete_others"
            if msg_age_sec <= FIVE_MIN:
                return True, "support_own"
            return False, "expired"
        return False, "denied"
    
    # Regular users
    if conv_status == "dispute":
        return False, "dispute_locked"
    
    if conv_type == "p2p_trade":
        if is_sender and msg_age_sec <= FIVE_MIN:
            return True, "own"
        return False, "p2p_locked_or_expired"
    
    if conv_type == "p2p_merchant":
        if is_sender and msg_age_sec <= FIVE_MIN:
            return True, "own"
        return False, "p2p_merchant_locked_or_expired"
    
    if conv_type in ["marketplace", "marketplace_guarantor"]:
        return False, "marketplace_locked"
    
    if conv_type == "merchant_application":
        return False, "application_locked"
    
    if conv_type == "shop_application":
        return False, "application_locked"
    
    if conv_type == "forum_topic":
        if is_sender and msg_age_sec <= FIVE_MIN:
            return True, "own"
        return False, "expired"
    
    if conv_type == "support_ticket":
        if is_sender and msg_age_sec <= FIVE_MIN:
            return True, "own"
        return False, "expired"
    
    return False, "denied"


# ==================== UNIFIED CONVERSATIONS ====================

@router.get("/msg/conversations")
async def get_user_conversations(user: dict = Depends(get_current_user)):
    """Get all conversations for current user"""
    user_id = user["id"]
    admin_role = user.get("admin_role")
    
    if admin_role:
        query = {
            "$or": [
                {"participants.user_id": user_id},
                {"participants": user_id},
                {"staff_participants": user_id}
            ]
        }
    else:
        query = {
            "$or": [
                {"participants.user_id": user_id},
                {"participants": user_id},
                {"target_user_id": user_id}
            ]
        }
    
    conversations = await db.unified_conversations.find(query, {"_id": 0}).sort("updated_at", -1).to_list(100)
    
    for conv in conversations:
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"], "is_deleted": {"$ne": True}},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        conv["last_message"] = last_msg
        conv["unread_count"] = conv.get("unread_counts", {}).get(user_id, 0)
    
    return conversations


@router.get("/msg/conversations/{conv_id}")
async def get_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    """Get conversation details with messages"""
    user_id = user["id"]
    
    conv = await db.unified_conversations.find_one({"id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    participants = conv.get("participants", [])
    participant_ids = []
    for p in participants:
        if isinstance(p, str):
            participant_ids.append(p)
        elif isinstance(p, dict):
            participant_ids.append(p.get("user_id", ""))
    
    if user_id not in participant_ids and user.get("admin_role") not in ["owner", "admin", "mod_p2p", "mod_market", "support"]:
        raise HTTPException(status_code=403, detail="Нет доступа к чату")
    
    messages = await db.unified_messages.find(
        {"conversation_id": conv_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    await db.unified_conversations.update_one(
        {"id": conv_id},
        {"$set": {f"unread_counts.{user_id}": 0}}
    )
    
    for msg in messages:
        msg["sender_info"] = get_msg_role_info(msg.get("sender_role", "user"), msg.get("sender_name", ""))
    
    return {
        "conversation": conv,
        "messages": messages,
        "role_colors": MSG_ROLE_COLORS,
        "role_names": MSG_ROLE_NAMES
    }


@router.post("/msg/conversations/{conv_id}/send")
async def send_message_to_conv(
    conv_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """Send message to conversation"""
    user_id = user["id"]
    content = data.get("content", "").strip()
    attachments = data.get("attachments", [])
    
    if not content and not attachments:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    conv = await db.unified_conversations.find_one({"id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    participants = conv.get("participants", []) or conv.get("staff_participants", [])
    participant_ids = []
    for p in participants:
        if isinstance(p, str):
            participant_ids.append(p)
        elif isinstance(p, dict):
            participant_ids.append(p.get("user_id", ""))
    
    is_admin = user.get("admin_role") in ["owner", "admin", "mod_p2p", "mod_market", "support"]
    if user_id not in participant_ids and not is_admin:
        raise HTTPException(status_code=403, detail="Вы не участник этого чата")
    
    sender_role = "user"
    sender_name = user.get("nickname", user.get("login", "User"))
    
    if user.get("admin_role"):
        sender_role = user["admin_role"]
        sender_name = user.get("login", "Admin")
    
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "sender_id": user_id,
        "sender_role": sender_role,
        "sender_name": sender_name,
        "content": content,
        "attachments": attachments,
        "is_system": False,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.unified_messages.insert_one(msg)
    
    all_participants = conv.get("participants", []) or conv.get("staff_participants", [])
    update_unread = {}
    for p in all_participants:
        p_id = p if isinstance(p, str) else p.get("user_id", "")
        if p_id and p_id != user_id:
            update_unread[f"unread_counts.{p_id}"] = 1
    
    await db.unified_conversations.update_one(
        {"id": conv_id},
        {
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat(), "last_message_at": msg["created_at"]},
            "$inc": update_unread
        }
    )
    
    msg.pop("_id", None)
    msg["sender_info"] = get_msg_role_info(sender_role, sender_name)
    return msg


@router.delete("/msg/messages/{msg_id}")
async def delete_message(msg_id: str, user: dict = Depends(get_current_user)):
    """Delete a message (with permission check)"""
    user_id = user["id"]
    user_role = user.get("admin_role", "user")
    
    msg = await db.unified_messages.find_one({"id": msg_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    
    if msg.get("is_deleted"):
        raise HTTPException(status_code=400, detail="Сообщение уже удалено")
    
    if msg.get("is_system"):
        raise HTTPException(status_code=400, detail="Системные сообщения нельзя удалить")
    
    conv = await db.unified_conversations.find_one({"id": msg["conversation_id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    created = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))
    age_sec = (datetime.now(timezone.utc) - created).total_seconds()
    is_sender = msg["sender_id"] == user_id
    
    can_delete, reason = can_user_delete_msg(
        conv.get("type", ""),
        conv.get("status", "active"),
        user_role,
        is_sender,
        age_sec
    )
    
    if not can_delete:
        error_msgs = {
            "locked": "В P2P и Marketplace чатах удаление запрещено",
            "dispute": "В споре удаление сообщений заблокировано",
            "expired": "Можно удалить только в течение 5 минут",
            "denied": "Нет прав на удаление"
        }
        raise HTTPException(status_code=403, detail=error_msgs.get(reason, "Нельзя удалить"))
    
    await db.unified_messages.update_one(
        {"id": msg_id},
        {"$set": {
            "is_deleted": True,
            "deleted_by": user_id,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "delete_reason": reason
        }}
    )
    
    return {"status": "deleted", "reason": reason}


# ==================== STAFF CHAT ROUTES ====================

@router.get("/admin/staff-chat")
async def get_staff_chat(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get staff chat messages"""
    messages = await db.staff_chat.find({}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return list(reversed(messages))


@router.post("/admin/staff-chat")
async def send_staff_message(data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Send message to staff chat"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    msg = {
        "id": str(uuid.uuid4()),
        "sender_id": user["id"],
        "sender_login": user.get("login", "Unknown"),
        "sender_role": user.get("admin_role", "admin"),
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.staff_chat.insert_one(msg)
    
    await db.admin_online.update_one(
        {"admin_id": user["id"]},
        {"$set": {
            "login": user.get("login"),
            "role": user.get("admin_role", "admin"),
            "last_seen": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    return {"status": "sent", "id": msg["id"]}


@router.get("/admin/staff-chat/online")
async def get_online_staff(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get currently online staff"""
    await db.admin_online.update_one(
        {"admin_id": user["id"]},
        {"$set": {
            "login": user.get("login"),
            "role": user.get("admin_role", "admin"),
            "last_seen": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    online = await db.admin_online.find(
        {"last_seen": {"$gte": cutoff}},
        {"_id": 0, "admin_id": 0}
    ).to_list(100)
    
    return online


# ==================== ADMIN MESSAGES TO STAFF ====================

@router.get("/admin/staff-messages/{staff_id}")
async def get_staff_messages(staff_id: str, user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get private messages between staff members"""
    my_id = user["id"]
    messages = await db.staff_private_messages.find(
        {"$or": [
            {"sender_id": my_id, "recipient_id": staff_id},
            {"sender_id": staff_id, "recipient_id": my_id}
        ]}, 
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return messages


@router.post("/admin/staff-messages/{staff_id}")
async def send_staff_private_message(staff_id: str, data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Send private message to another staff member"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    msg = {
        "id": str(uuid.uuid4()),
        "sender_id": user["id"],
        "sender_login": user.get("login", "Unknown"),
        "sender_role": user.get("admin_role", "admin"),
        "recipient_id": staff_id,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.staff_private_messages.insert_one(msg)
    return {"status": "sent"}
