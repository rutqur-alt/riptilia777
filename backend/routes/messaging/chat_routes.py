from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.auth import get_current_user
from core.database import db
from .utils import (
    get_staff_display_name, 
    get_role_display_info, 
    check_delete_permission,
    create_message
)
from .models import SendMessageRequest

try:
    from routes.ws_routes import ws_manager
except ImportError:
    ws_manager = None

router = APIRouter()

async def _ws_broadcast(channel: str, data: dict):
    if ws_manager:
        await ws_manager.broadcast(channel, data)

async def _create_message_notification(user_id: str, sender_name: str, conv_type: str, conv_id: str):
    """Create event notification for new message"""
    # Determine link based on conversation type
    link = "/trader/messages"
    if conv_type == "shop_chat":
        link = "/trader/shop-chats"
    elif conv_type == "marketplace_guarantor":
        link = "/trader/my-purchases"
    
    await db.event_notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "new_message",
        "title": "Новое сообщение",
        "message": f"Сообщение от {sender_name}",
        "link": link,
        "reference_id": conv_id,
        "reference_type": "message",
        "extra_data": {"conv_type": conv_type},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

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
    
    # Also add crypto_orders for this user (as buyer or trader)
    crypto_orders = await db.crypto_orders.find(
        {"$or": [{"buyer_id": user_id}, {"trader_id": user_id}]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    
    for order in crypto_orders:
        # Get conversation for this order
        conv = await db.unified_conversations.find_one(
            {"related_id": order["id"], "type": "crypto_order"},
            {"_id": 0}
        )
        
        if conv:
            # Check unread messages
            last_msg = await db.unified_messages.find_one(
                {"conversation_id": conv["id"], "is_deleted": {"$ne": True}},
                {"_id": 0},
                sort=[("created_at", -1)]
            )
            unread_count = conv.get("unread_counts", {}).get(user_id, 0)
            
            conv_entry = {
                "id": conv["id"],
                "related_id": order["id"],
                "type": "crypto_order",
                "title": f"Покупка {order.get('amount_usdt', '?')} USDT",
                "status": order.get("status"),
                "amount_usdt": order.get("amount_usdt"),
                "amount_rub": order.get("amount_rub"),
                "last_message": last_msg,
                "unread_count": unread_count,
                "updated_at": conv.get("updated_at") or order.get("updated_at") or order.get("created_at"),
                "created_at": order.get("created_at")
            }
            conversations.append(conv_entry)
    
    # Sort all conversations: unread first, then by updated_at (newest first)
    def sort_key(x):
        # Unread priority (higher = first)
        unread = x.get("unread_count") or 0
        # Date timestamp
        date_str = x.get("updated_at") or x.get("created_at") or "1970-01-01"
        try:
            if isinstance(date_str, str):
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                date = date_str
            timestamp = date.timestamp()
        except:
            timestamp = 0
        # Sort: unread DESC, then timestamp DESC
        return (-unread, -timestamp)
    
    conversations.sort(key=sort_key)
    
    # Remove duplicates (same id)
    seen_ids = set()
    unique_conversations = []
    for conv in conversations:
        if conv["id"] not in seen_ids:
            seen_ids.add(conv["id"])
            unique_conversations.append(conv)
    
    return unique_conversations


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
        msg["sender_info"] = get_role_display_info(msg.get("sender_role", "user"), msg.get("sender_name", ""))
    
    from .utils import ROLE_COLORS, ROLE_DISPLAY_NAMES
    return {
        "conversation": conv,
        "messages": messages,
        "role_colors": ROLE_COLORS,
        "role_names": ROLE_DISPLAY_NAMES
    }


@router.post("/msg/conversations/{conv_id}/send")
async def send_message_to_conv(
    conv_id: str,
    data: SendMessageRequest,
    user: dict = Depends(get_current_user)
):
    """Send message to conversation"""
    user_id = user["id"]
    content = data.content.strip()
    attachments = data.attachments or []
    
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
        sender_name = get_staff_display_name(user)
    
    msg = create_message(
        conversation_id=conv_id,
        sender_id=user_id,
        sender_role=sender_role,
        sender_name=sender_name,
        content=content,
        attachments=attachments
    )
    
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
    msg["sender_info"] = get_role_display_info(sender_role, sender_name)
    await _ws_broadcast(f"conv_{conv_id}", {"type": "message", **msg})
    
    # Also broadcast to trade channel if this is a trade-related conversation
    if conv.get("type") in ["p2p_trade", "p2p_dispute"] and conv.get("related_id"):
        await _ws_broadcast(f"trade_{conv['related_id']}", {"type": "message", **msg})
    
    # Create event notifications for other participants
    conv_type = conv.get("type", "private")
    for p in all_participants:
        p_id = p if isinstance(p, str) else p.get("user_id", "")
        if p_id and p_id != user_id:
            await _create_message_notification(p_id, sender_name, conv_type, conv_id)
    
    return msg


@router.post("/msg/conversations/{conv_id}/read")
async def mark_conversation_read(conv_id: str, user: dict = Depends(get_current_user)):
    """Mark all messages in conversation as read for current user"""
    user_id = user["id"]
    
    conv = await db.unified_conversations.find_one({"id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    # Mark all unread messages as read
    await db.unified_messages.update_many(
        {"conversation_id": conv_id, "sender_id": {"$ne": user_id}, "read_by": {"$ne": user_id}},
        {"$addToSet": {"read_by": user_id}}
    )
    
    # Update conversation unread count for this user
    await db.unified_conversations.update_one(
        {"id": conv_id},
        {"$set": {f"read_status.{user_id}": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"status": "ok", "message": "Сообщения отмечены как прочитанные"}


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
    
    can_delete, reason = check_delete_permission(
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
            "denied": "Нет прав на удаление",
            "p2p_no_delete": "В P2P чатах удаление запрещено",
            "marketplace_no_delete": "В Marketplace чатах удаление запрещено",
            "dispute_locked": "В споре удаление сообщений заблокировано",
            "time_expired": "Время для удаления истекло",
            "not_sender": "Вы не являетесь отправителем"
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
