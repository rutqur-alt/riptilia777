from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from core.database import db
from core.auth import require_admin_level
from .utils import clean_doc

router = APIRouter()

# ==================== ADMIN LOGS ====================

@router.get("/admin/logs")
async def get_admin_logs(
    skip: int = 0, 
    limit: int = 50, 
    action: str = None,
    admin_id: str = None,
    user: dict = Depends(require_admin_level(30))
):
    """Get admin action logs"""
    query = {}
    if action:
        query["action"] = action
    if admin_id:
        query["admin_id"] = admin_id
        
    logs = await db.admin_logs.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.admin_logs.count_documents(query)
    
    return {"logs": logs, "total": total}


# ==================== FORUM MODERATION ====================

@router.get("/admin/forum/messages")
async def get_forum_messages_admin(skip: int = 0, limit: int = 50, user: dict = Depends(require_admin_level(30))):
    """Get forum messages for moderation"""
    messages = await db.forum_messages.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return messages


@router.delete("/admin/forum/messages/{message_id}")
async def delete_forum_message(message_id: str, user: dict = Depends(require_admin_level(50))):
    """Delete forum message"""
    await db.forum_messages.delete_one({"id": message_id})
    await log_admin_action(user["id"], "delete_forum_message", "forum", message_id, {})
    return {"status": "deleted"}


@router.post("/admin/forum/ban/{user_id}")
async def ban_from_forum(user_id: str, data: dict, user: dict = Depends(require_admin_level(50))):
    """Ban user from forum"""
    reason = data.get("reason", "")
    
    # Try traders
    await db.traders.update_one(
        {"id": user_id},
        {"$set": {"forum_banned": True, "forum_ban_reason": reason}}
    )
    
    # Try merchants
    await db.merchants.update_one(
        {"id": user_id},
        {"$set": {"forum_banned": True, "forum_ban_reason": reason}}
    )
    
    await log_admin_action(user["id"], "ban_forum", "user", user_id, {"reason": reason})
    
    return {"status": "banned"}
