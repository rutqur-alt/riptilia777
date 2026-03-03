"""
Broadcast Routes - Migrated from server.py
Handles admin broadcast messages to users/merchants/all
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.auth import require_role, log_admin_action
from core.database import db

router = APIRouter(tags=["broadcast"])


# ==================== BROADCAST (РАССЫЛКА) ====================

@router.post("/admin/broadcast")
async def send_broadcast(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Send broadcast message to users
    
    Body:
    - target: "all" | "merchants" | "traders" | "users"
    - title: Message title
    - content: Message content
    - priority: "normal" | "high" | "urgent"
    """
    target = data.get("target", "all")
    title = data.get("title", "")
    content = data.get("content", "")
    priority = data.get("priority", "normal")
    
    if not content:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    now = datetime.now(timezone.utc).isoformat()
    recipients = []
    
    # Get recipients based on target
    if target == "all":
        traders = await db.traders.find({"is_active": {"$ne": False}}, {"id": 1, "nickname": 1, "_id": 0}).to_list(10000)
        merchants = await db.merchants.find({"is_active": {"$ne": False}}, {"id": 1, "nickname": 1, "merchant_name": 1, "_id": 0}).to_list(1000)
        recipients = [{"id": t["id"], "name": t.get("nickname", ""), "type": "trader"} for t in traders]
        recipients += [{"id": m["id"], "name": m.get("nickname") or m.get("merchant_name", ""), "type": "merchant"} for m in merchants]
    elif target == "merchants":
        merchants = await db.merchants.find({"is_active": {"$ne": False}}, {"id": 1, "nickname": 1, "merchant_name": 1, "_id": 0}).to_list(1000)
        recipients = [{"id": m["id"], "name": m.get("nickname") or m.get("merchant_name", ""), "type": "merchant"} for m in merchants]
    elif target == "traders" or target == "users":
        traders = await db.traders.find({"is_active": {"$ne": False}}, {"id": 1, "nickname": 1, "_id": 0}).to_list(10000)
        recipients = [{"id": t["id"], "name": t.get("nickname", ""), "type": "trader"} for t in traders]
    
    if not recipients:
        raise HTTPException(status_code=400, detail="Нет получателей для выбранной группы")
    
    # Create broadcast record
    broadcast_id = str(uuid.uuid4())
    broadcast = {
        "id": broadcast_id,
        "sender_id": user["id"],
        "sender_name": user.get("nickname", user.get("login", "Admin")),
        "target": target,
        "title": title,
        "content": content,
        "priority": priority,
        "recipients_count": len(recipients),
        "created_at": now,
        "status": "sent"
    }
    await db.broadcasts.insert_one(broadcast)
    
    # Create notifications for all recipients
    notifications = []
    for r in recipients:
        notifications.append({
            "id": str(uuid.uuid4()),
            "user_id": r["id"],
            "user_type": r["type"],
            "type": "broadcast",
            "broadcast_id": broadcast_id,
            "title": title or "Рассылка от администрации",
            "message": content,
            "priority": priority,
            "is_read": False,
            "created_at": now
        })
    
    if notifications:
        await db.notifications.insert_many(notifications)
    
    # Log action
    await log_admin_action(user["id"], "broadcast_sent", "broadcast", broadcast_id, {
        "target": target,
        "recipients_count": len(recipients),
        "title": title
    })
    
    return {
        "status": "sent",
        "broadcast_id": broadcast_id,
        "recipients_count": len(recipients),
        "target": target
    }


@router.get("/admin/broadcasts")
async def get_broadcasts(user: dict = Depends(require_role(["admin", "owner"]))):
    """Get list of all broadcasts"""
    broadcasts = await db.broadcasts.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return broadcasts


@router.get("/admin/broadcasts/{broadcast_id}")
async def get_broadcast_details(broadcast_id: str, user: dict = Depends(require_role(["admin", "owner"]))):
    """Get detailed info about a broadcast"""
    broadcast = await db.broadcasts.find_one({"id": broadcast_id}, {"_id": 0})
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    
    # Get read stats
    total_notifications = await db.notifications.count_documents({"broadcast_id": broadcast_id})
    read_notifications = await db.notifications.count_documents({"broadcast_id": broadcast_id, "is_read": True})
    
    broadcast["read_count"] = read_notifications
    broadcast["total_count"] = total_notifications
    broadcast["read_percentage"] = round((read_notifications / total_notifications * 100), 1) if total_notifications > 0 else 0
    
    return broadcast


@router.delete("/admin/broadcasts/{broadcast_id}")
async def delete_broadcast(broadcast_id: str, user: dict = Depends(require_role(["admin", "owner"]))):
    """Delete a broadcast and all its notifications"""
    broadcast = await db.broadcasts.find_one({"id": broadcast_id}, {"_id": 0})
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    
    # Delete broadcast
    await db.broadcasts.delete_one({"id": broadcast_id})
    
    # Delete related notifications
    deleted = await db.notifications.delete_many({"broadcast_id": broadcast_id})
    
    await log_admin_action(user["id"], "broadcast_deleted", "broadcast", broadcast_id, {
        "notifications_deleted": deleted.deleted_count
    })
    
    return {"status": "deleted", "notifications_removed": deleted.deleted_count}
