"""
Staff Admin Routes - Migrated from server.py
Handles staff internal chats, extended admin functions, dispute discussions, and application chats
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone, timedelta
import uuid

from core.auth import require_role, get_current_user, log_admin_action
from server import db

router = APIRouter(tags=["staff_admin"])

# Role info helpers (referenced from unified_messaging)
MSG_ROLE_COLORS = {
    "user": "#FFFFFF", "buyer": "#FFFFFF", "p2p_seller": "#FFFFFF",
    "shop_owner": "#8B5CF6", "merchant": "#F97316",
    "mod_p2p": "#F59E0B", "mod_market": "#F59E0B",
    "support": "#3B82F6", "admin": "#EF4444", "owner": "#EF4444",
    "system": "#6B7280"
}

MSG_ROLE_NAMES = {
    "user": "Пользователь", "buyer": "Покупатель", "p2p_seller": "Продавец",
    "shop_owner": "Магазин", "merchant": "Мерчант",
    "mod_p2p": "Модератор P2P", "mod_market": "Гарант",
    "support": "Поддержка", "admin": "Администратор", "owner": "Владелец",
    "system": "Система"
}

def get_msg_role_info(role: str, name: str) -> dict:
    return {
        "name": name,
        "role": role,
        "role_name": MSG_ROLE_NAMES.get(role, role),
        "color": MSG_ROLE_COLORS.get(role, "#FFFFFF"),
        "icon": ""
    }


# ==================== EXTENDED ADMIN FUNCTIONS ====================

@router.get("/admin/activity-monitor")
async def get_staff_activity_monitor(user: dict = Depends(require_role(["admin"]))):
    """Get staff activity monitoring data (admin only)"""
    now = datetime.now(timezone.utc)
    
    all_staff = await db.admins.find({"is_active": True}, {"_id": 0, "password_hash": 0}).to_list(100)
    
    cutoff = (now - timedelta(seconds=60)).isoformat()
    online_staff = await db.admin_online.find({"last_seen": {"$gte": cutoff}}, {"_id": 0}).to_list(100)
    online_ids = {s.get("admin_id") for s in online_staff}
    
    staff_stats = []
    for staff in all_staff:
        staff_id = staff.get("id")
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        
        decisions_today = await db.decisions.count_documents({
            "decided_by": staff_id,
            "created_at": {"$gte": today_start}
        })
        
        messages_today = await db.unified_messages.count_documents({
            "sender_id": staff_id,
            "created_at": {"$gte": today_start}
        })
        
        last_decision = await db.decisions.find_one(
            {"decided_by": staff_id},
            {"_id": 0, "created_at": 1, "decision_type": 1},
            sort=[("created_at", -1)]
        )
        
        staff_stats.append({
            "id": staff_id,
            "login": staff.get("login"),
            "nickname": staff.get("nickname"),
            "role": staff.get("admin_role"),
            "is_online": staff_id in online_ids,
            "decisions_today": decisions_today,
            "messages_today": messages_today,
            "last_decision": last_decision
        })
    
    return {"staff": staff_stats, "total_online": len(online_ids), "total_staff": len(all_staff)}


@router.post("/admin/decisions/{decision_id}/review")
async def review_moderator_decision(
    decision_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin"]))
):
    """Admin reviews and potentially overturns a moderator's decision"""
    action = data.get("action")
    new_decision = data.get("new_decision")
    reason = data.get("reason", "")
    
    if action not in ["confirm", "overturn"]:
        raise HTTPException(status_code=400, detail="Действие должно быть: confirm или overturn")
    
    original = await db.decisions.find_one({"id": decision_id}, {"_id": 0})
    if not original:
        raise HTTPException(status_code=404, detail="Решение не найдено")
    
    if original.get("reviewed"):
        raise HTTPException(status_code=400, detail="Решение уже пересмотрено")
    
    now = datetime.now(timezone.utc)
    
    await db.decisions.update_one(
        {"id": decision_id},
        {"$set": {
            "reviewed": True,
            "reviewed_by": user["id"],
            "reviewed_at": now.isoformat(),
            "review_action": action,
            "review_reason": reason
        }}
    )
    
    if action == "overturn":
        if not new_decision:
            raise HTTPException(status_code=400, detail="Новое решение обязательно при пересмотре")
        
        new_decision_doc = {
            "id": str(uuid.uuid4()),
            "order_id": original.get("order_id"),
            "conversation_id": original.get("conversation_id"),
            "decision_type": new_decision,
            "is_overturn": True,
            "original_decision_id": decision_id,
            "decided_by": user["id"],
            "decided_by_role": "admin",
            "decided_by_name": user.get("nickname", user.get("login", "")),
            "reason": reason,
            "status": "pending_execution",
            "created_at": now.isoformat()
        }
        await db.decisions.insert_one(new_decision_doc)
        
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": original.get("decided_by"),
            "type": "decision_overturned",
            "title": "Ваше решение пересмотрено",
            "message": f"Администратор пересмотрел ваше решение по заказу {original.get('order_id', '')[:8]}. Причина: {reason}",
            "read": False,
            "created_at": now.isoformat()
        })
        
        return {"status": "overturned", "new_decision_id": new_decision_doc["id"]}
    
    return {"status": "confirmed", "message": "Решение подтверждено"}


@router.post("/admin/user/{user_id}/freeze-funds")
async def freeze_user_funds(
    user_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin"]))
):
    """Freeze user's funds for specified hours (admin only)"""
    reason = data.get("reason", "")
    hours = data.get("hours", 24)
    
    if hours > 168:
        hours = 168
    
    target_user = await db.traders.find_one({"id": user_id}, {"_id": 0})
    collection = "traders"
    if not target_user:
        target_user = await db.merchants.find_one({"id": user_id}, {"_id": 0})
        collection = "merchants"
    
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if target_user.get("funds_frozen"):
        raise HTTPException(status_code=400, detail="Средства уже заморожены")
    
    freeze_until = datetime.now(timezone.utc) + timedelta(hours=hours)
    
    db_collection = db.traders if collection == "traders" else db.merchants
    await db_collection.update_one(
        {"id": user_id},
        {"$set": {
            "funds_frozen": True,
            "freeze_until": freeze_until.isoformat(),
            "freeze_reason": reason,
            "frozen_by": user["id"],
            "frozen_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    await log_admin_action(user["id"], "freeze_funds", collection, user_id, {"hours": hours, "reason": reason})
    
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "funds_frozen",
        "title": "Средства заморожены",
        "message": f"Ваши средства заморожены на {hours} часов. Причина: {reason}. Разморозка: {freeze_until.strftime('%d.%m.%Y %H:%M')}",
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"status": "frozen", "freeze_until": freeze_until.isoformat()}


@router.post("/admin/user/{user_id}/unfreeze-funds")
async def unfreeze_user_funds(user_id: str, user: dict = Depends(require_role(["admin"]))):
    """Unfreeze user's funds (admin only)"""
    target_user = await db.traders.find_one({"id": user_id}, {"_id": 0})
    collection = "traders"
    if not target_user:
        target_user = await db.merchants.find_one({"id": user_id}, {"_id": 0})
        collection = "merchants"
    
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if not target_user.get("funds_frozen"):
        raise HTTPException(status_code=400, detail="Средства не заморожены")
    
    db_collection = db.traders if collection == "traders" else db.merchants
    await db_collection.update_one(
        {"id": user_id},
        {"$unset": {"funds_frozen": "", "freeze_until": "", "freeze_reason": "", "frozen_by": "", "frozen_at": ""}}
    )
    
    await log_admin_action(user["id"], "unfreeze_funds", collection, user_id, {})
    
    return {"status": "unfrozen"}


@router.post("/admin/chat/{conversation_id}/block-user")
async def block_user_from_chat(
    conversation_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Block a user from sending messages in a specific chat"""
    target_user_id = data.get("user_id")
    reason = data.get("reason", "")
    duration_hours = data.get("duration_hours", 24)
    
    if not target_user_id:
        raise HTTPException(status_code=400, detail="user_id обязателен")
    
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    blocked_until = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
    
    blocked_users = conv.get("blocked_users", [])
    blocked_users = [b for b in blocked_users if b.get("user_id") != target_user_id]
    blocked_users.append({
        "user_id": target_user_id,
        "blocked_by": user["id"],
        "blocked_at": datetime.now(timezone.utc).isoformat(),
        "blocked_until": blocked_until.isoformat(),
        "reason": reason
    })
    
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$set": {"blocked_users": blocked_users}}
    )
    
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"🚫 Пользователь заблокирован в этом чате на {duration_hours} часов. Причина: {reason}",
        "is_system": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(msg)
    
    return {"status": "blocked", "blocked_until": blocked_until.isoformat()}


@router.get("/admin/messages/search")
async def global_message_search(q: str, limit: int = 50, user: dict = Depends(require_role(["admin"]))):
    """Global search across all messages (admin only)"""
    if not q or len(q) < 3:
        raise HTTPException(status_code=400, detail="Минимум 3 символа для поиска")
    
    messages = await db.unified_messages.find(
        {"content": {"$regex": q, "$options": "i"}},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    for msg in messages:
        conv = await db.unified_conversations.find_one(
            {"id": msg.get("conversation_id")},
            {"_id": 0, "type": 1, "title": 1, "related_id": 1}
        )
        if conv:
            msg["conversation_type"] = conv.get("type")
            msg["conversation_title"] = conv.get("title")
    
    return {"results": messages, "total": len(messages)}


# ==================== STAFF INTERNAL CHATS ====================

@router.get("/msg/staff/chats")
async def get_staff_chats(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get internal staff chats"""
    user_id = user["id"]
    
    chats = await db.unified_conversations.find(
        {
            "type": {"$in": ["internal_mods_p2p", "internal_mods_market", "internal_support", "internal_admin", "internal_discussion"]},
            "participants.user_id": user_id
        },
        {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    
    for c in chats:
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": c["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        c["last_message"] = last_msg
        c["unread_count"] = c.get("unread_counts", {}).get(user_id, 0)
    
    return chats


@router.post("/msg/staff/chat/create")
async def create_staff_internal_chat(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))
):
    """Create internal discussion chat"""
    title = data.get("title", "Обсуждение")
    participant_ids = data.get("participant_ids", [])
    related_dispute_id = data.get("related_dispute_id")
    
    user_id = user["id"]
    user_name = user.get("login", "Staff")
    user_role = user.get("admin_role", "support")
    
    participants = [{"user_id": user_id, "role": user_role, "name": user_name}]
    unread = {user_id: 0}
    
    for pid in participant_ids:
        if pid != user_id:
            staff = await db.admins.find_one({"id": pid}, {"_id": 0})
            if staff:
                participants.append({
                    "user_id": pid,
                    "role": staff.get("admin_role", "support"),
                    "name": staff.get("login", "Staff")
                })
                unread[pid] = 1
    
    conv = {
        "id": str(uuid.uuid4()),
        "type": "internal_discussion",
        "status": "active",
        "related_id": related_dispute_id,
        "title": title,
        "delete_locked": False,
        "participants": participants,
        "unread_counts": unread,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.unified_conversations.insert_one(conv)
    
    sys_content = f"Создано обсуждение: {title}"
    if related_dispute_id:
        sys_content += f"\nСвязанный спор: {related_dispute_id}"
    
    sys_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": "system",
        "sender_role": "system",
        "sender_name": "Система",
        "content": sys_content,
        "is_system": True,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(sys_msg)
    
    return {"conversation_id": conv["id"]}


# ==================== INTERNAL DISPUTE DISCUSSION ====================

@router.post("/msg/staff/dispute/{dispute_id}/discussion")
async def create_dispute_internal_discussion(
    dispute_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))
):
    """Create internal staff discussion for a specific dispute"""
    title = data.get("title", f"Обсуждение спора {dispute_id[:8]}")
    
    existing = await db.unified_conversations.find_one({"type": "internal_dispute", "dispute_id": dispute_id})
    if existing:
        return {"conversation_id": existing["id"], "message": "Обсуждение уже существует"}
    
    all_staff = await db.admins.find({"is_active": True}, {"_id": 0}).to_list(100)
    participants = [s["id"] for s in all_staff]
    unread = {s["id"]: 0 for s in all_staff}
    
    conv = {
        "id": str(uuid.uuid4()),
        "type": "internal_dispute",
        "dispute_id": dispute_id,
        "title": title,
        "status": "active",
        "participants": participants,
        "unread_counts": unread,
        "votes": {},
        "vote_summary": {"buyer": 0, "seller": 0, "split": 0},
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_conversations.insert_one(conv)
    
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"📋 Создано внутреннее обсуждение спора #{dispute_id[:8]}\n\n👤 Инициатор: {user.get('nickname', user.get('login', ''))}\n\nМодераторы могут голосовать и обсуждать решение.",
        "is_system": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(msg)
    
    return {"conversation_id": conv["id"], "message": "Обсуждение создано"}


@router.post("/msg/staff/dispute/{dispute_id}/vote")
async def vote_on_dispute(
    dispute_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))
):
    """Vote on a dispute decision (internal staff voting)"""
    vote = data.get("vote")
    comment = data.get("comment", "")
    
    if vote not in ["buyer", "seller", "split"]:
        raise HTTPException(status_code=400, detail="Неверный голос. Допустимые: buyer, seller, split")
    
    conv = await db.unified_conversations.find_one({"type": "internal_dispute", "dispute_id": dispute_id})
    if not conv:
        raise HTTPException(status_code=404, detail="Внутреннее обсуждение не найдено. Сначала создайте его.")
    
    old_vote = conv.get("votes", {}).get(user["id"])
    
    update_query = {
        f"votes.{user['id']}": vote,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if old_vote:
        update_query[f"vote_summary.{old_vote}"] = conv.get("vote_summary", {}).get(old_vote, 1) - 1
    update_query[f"vote_summary.{vote}"] = conv.get("vote_summary", {}).get(vote, 0) + 1
    
    await db.unified_conversations.update_one({"id": conv["id"]}, {"$set": update_query})
    
    vote_labels = {"buyer": "в пользу ПОКУПАТЕЛЯ", "seller": "в пользу ПРОДАВЦА", "split": "РАЗДЕЛИТЬ 50/50"}
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": user["id"],
        "sender_nickname": user.get("nickname", user.get("login", "")),
        "sender_role": user.get("admin_role", "admin"),
        "content": f"🗳️ ГОЛОС: {vote_labels.get(vote, vote)}" + (f"\n💬 {comment}" if comment else ""),
        "is_vote": True,
        "vote_value": vote,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(msg)
    
    updated_conv = await db.unified_conversations.find_one({"id": conv["id"]}, {"vote_summary": 1, "votes": 1, "_id": 0})
    
    return {"status": "success", "message": "Голос учтён", "vote_summary": updated_conv.get("vote_summary"), "total_votes": len(updated_conv.get("votes", {}))}


@router.get("/msg/staff/dispute/{dispute_id}/discussion")
async def get_dispute_discussion(
    dispute_id: str,
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))
):
    """Get internal discussion for a dispute"""
    conv = await db.unified_conversations.find_one({"type": "internal_dispute", "dispute_id": dispute_id}, {"_id": 0})
    
    if not conv:
        return {"exists": False, "conversation": None, "messages": []}
    
    messages = await db.unified_messages.find(
        {"conversation_id": conv["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    return {"exists": True, "conversation": conv, "messages": messages}


@router.post("/msg/staff/dispute/{dispute_id}/take")
async def take_dispute(
    dispute_id: str,
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Moderator takes a dispute to work on"""
    conv = await db.unified_conversations.find_one({
        "type": "p2p_trade",
        "status": "dispute",
        "$or": [{"id": dispute_id}, {"related_id": dispute_id}, {"context_id": dispute_id}]
    })
    
    if not conv:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    if conv.get("assigned_to"):
        assignee = await db.admins.find_one({"id": conv["assigned_to"]}, {"nickname": 1, "login": 1, "_id": 0})
        assignee_name = assignee.get("nickname", assignee.get("login", "Модератор")) if assignee else "Модератор"
        raise HTTPException(status_code=400, detail=f"Спор уже взят модератором: {assignee_name}")
    
    await db.unified_conversations.update_one(
        {"id": conv["id"]},
        {"$set": {
            "assigned_to": user["id"],
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"👨‍⚖️ Модератор {user.get('nickname', user.get('login', ''))} взял спор в работу",
        "is_system": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(msg)
    
    return {"status": "success", "message": "Спор взят в работу"}


@router.get("/admin/disputes/stats")
async def get_disputes_statistics(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))):
    """Get statistics for disputes"""
    total_disputes = await db.unified_conversations.count_documents({"type": "p2p_trade", "status": "dispute"})
    total_resolved = await db.unified_conversations.count_documents({"type": "p2p_trade", "status": "resolved"})
    
    resolved_convs = await db.unified_conversations.find(
        {"type": "p2p_trade", "status": "resolved", "resolved_at": {"$exists": True}},
        {"created_at": 1, "resolved_at": 1, "_id": 0}
    ).to_list(100)
    
    avg_resolution_time = 0
    if resolved_convs:
        times = []
        for c in resolved_convs:
            try:
                created = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                resolved = datetime.fromisoformat(c["resolved_at"].replace("Z", "+00:00"))
                times.append((resolved - created).total_seconds() / 3600)
            except (ValueError, KeyError, TypeError):
                pass
        if times:
            avg_resolution_time = sum(times) / len(times)
    
    mod_stats = {}
    decisions = await db.decisions.find({}, {"decided_by": 1, "decision_type": 1, "_id": 0}).to_list(500)
    for d in decisions:
        mod_id = d.get("decided_by")
        if mod_id:
            if mod_id not in mod_stats:
                mod_stats[mod_id] = {"total": 0, "buyer_wins": 0, "seller_wins": 0, "splits": 0}
            mod_stats[mod_id]["total"] += 1
            if d.get("decision_type") in ["refund_full", "refund_partial"]:
                mod_stats[mod_id]["buyer_wins"] += 1
            elif d.get("decision_type") == "release_seller":
                mod_stats[mod_id]["seller_wins"] += 1
            elif d.get("decision_type") == "split":
                mod_stats[mod_id]["splits"] += 1
    
    return {
        "total_active_disputes": total_disputes,
        "total_resolved": total_resolved,
        "average_resolution_hours": round(avg_resolution_time, 1),
        "moderator_stats": mod_stats
    }


# ==================== GENERAL STAFF CHAT ====================

@router.get("/msg/staff/general")
async def get_general_staff_chat(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get or create general staff chat"""
    conv = await db.unified_conversations.find_one({"type": "internal_admin", "title": "Общий чат персонала"}, {"_id": 0})
    
    if not conv:
        all_staff = await db.admins.find({"is_active": True}, {"_id": 0}).to_list(100)
        participants = []
        unread = {}
        for s in all_staff:
            participants.append({"user_id": s["id"], "role": s.get("admin_role", "support"), "name": s.get("login", "Staff")})
            unread[s["id"]] = 0
        
        conv = {
            "id": str(uuid.uuid4()),
            "type": "internal_admin",
            "status": "active",
            "related_id": None,
            "title": "Общий чат персонала",
            "delete_locked": False,
            "participants": participants,
            "unread_counts": unread,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.unified_conversations.insert_one(conv)
    
    messages = await db.unified_messages.find(
        {"conversation_id": conv["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    
    for msg in messages:
        msg["sender_info"] = get_msg_role_info(msg.get("sender_role", "user"), msg.get("sender_name", ""))
    
    return {"conversation": conv, "messages": messages, "role_colors": MSG_ROLE_COLORS}


@router.post("/msg/staff/general")
async def send_to_general_staff_chat(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))
):
    """Send message to general staff chat"""
    content = data.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    conv = await db.unified_conversations.find_one({"type": "internal_admin", "title": "Общий чат персонала"}, {"_id": 0})
    
    if not conv:
        all_staff = await db.admins.find({"is_active": True}, {"_id": 0}).to_list(100)
        participants = []
        unread = {}
        for s in all_staff:
            participants.append({"user_id": s["id"], "role": s.get("admin_role", "support"), "name": s.get("login", "Staff")})
            unread[s["id"]] = 0
        
        conv = {
            "id": str(uuid.uuid4()),
            "type": "internal_admin",
            "status": "active",
            "related_id": None,
            "title": "Общий чат персонала",
            "delete_locked": False,
            "participants": participants,
            "unread_counts": unread,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.unified_conversations.insert_one(conv)
    
    sender_role = user.get("admin_role", "support")
    sender_name = user.get("login", "Staff")
    
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": user["id"],
        "sender_role": sender_role,
        "sender_name": sender_name,
        "content": content,
        "is_system": False,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.unified_messages.insert_one(msg)
    
    update_unread = {f"unread_counts.{p['user_id']}": 1 for p in conv.get("participants", []) if p["user_id"] != user["id"]}
    if update_unread:
        await db.unified_conversations.update_one(
            {"id": conv["id"]},
            {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}, "$inc": update_unread}
        )
    
    msg.pop("_id", None)
    msg["sender_info"] = get_msg_role_info(sender_role, sender_name)
    return msg


# ==================== ADMIN MERCHANT/SHOP APPLICATION CHATS ====================

@router.get("/msg/admin/merchant-applications")
async def get_merchant_application_chats(user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Get all merchant application conversations"""
    user_id = user["id"]
    
    query = {
        "type": "merchant_application",
        "deleted": {"$ne": True},
        "resolved": {"$ne": True},
        "left_staff": {"$ne": user_id}
    }
    
    convs = await db.unified_conversations.find(query, {"_id": 0}).sort("updated_at", -1).to_list(100)
    
    result = []
    for conv in convs:
        app = await db.merchant_applications.find_one({"id": conv.get("related_id")}, {"_id": 0})
        if not app:
            if conv.get("participants"):
                user_id_p = conv["participants"][0] if isinstance(conv["participants"][0], str) else conv["participants"][0].get("user_id")
                app = await db.merchant_applications.find_one({"user_id": user_id_p}, {"_id": 0})
        
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        
        conv["title"] = app.get("merchant_name") if app else "Заявка мерчанта"
        conv["subtitle"] = f"@{app.get('nickname', '')} • {app.get('merchant_type', '')}" if app else ""
        conv["merchant_name"] = app.get("merchant_name") if app else ""
        conv["merchant_type"] = app.get("merchant_type") if app else ""
        conv["nickname"] = app.get("nickname") if app else ""
        conv["last_message"] = last_msg
        conv["data"] = app
        result.append(conv)
    
    return result


@router.get("/msg/admin/shop-applications")
async def get_shop_application_chats(user: dict = Depends(require_role(["admin", "mod_market"]))):
    """Get all shop application conversations"""
    user_id = user["id"]
    
    query = {
        "type": "shop_application",
        "deleted": {"$ne": True},
        "resolved": {"$ne": True},
        "left_staff": {"$ne": user_id}
    }
    
    convs = await db.unified_conversations.find(query, {"_id": 0}).sort("updated_at", -1).to_list(100)
    
    result = []
    for conv in convs:
        app = await db.shop_applications.find_one({"id": conv.get("related_id")}, {"_id": 0})
        
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        
        conv["title"] = app.get("shop_name") if app else "Заявка магазина"
        conv["subtitle"] = f"@{app.get('nickname', '')}" if app else ""
        conv["shop_name"] = app.get("shop_name") if app else ""
        conv["nickname"] = app.get("nickname") if app else ""
        conv["last_message"] = last_msg
        conv["data"] = app
        result.append(conv)
    
    return result
