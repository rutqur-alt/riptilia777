from fastapi import APIRouter, HTTPException, Depends
from core.auth import get_current_user
from core.database import db

router = APIRouter(tags=["broadcast"])

# ==================== USER ENDPOINTS FOR BROADCASTS ====================

@router.get("/notifications/broadcasts")
async def get_user_broadcasts(user: dict = Depends(get_current_user)):
    """Get broadcast notifications for current user"""
    notifications = await db.notifications.find(
        {
            "user_id": user["id"],
            "type": "broadcast"
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return notifications


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: dict = Depends(get_current_user)):
    """Mark a notification as read"""
    result = await db.notifications.update_one(
        {"id": notification_id, "user_id": user["id"]},
        {"$set": {"is_read": True}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    
    return {"status": "read"}


@router.get("/notifications/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await db.notifications.count_documents({
        "user_id": user["id"],
        "is_read": False
    })
    return {"count": count}
