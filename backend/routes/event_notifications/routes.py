
from fastapi import APIRouter, HTTPException, Depends, Body

from core.database import db
from core.auth import get_current_user

router = APIRouter()

@router.get("/")
async def get_event_notifications(
    user: dict = Depends(get_current_user),
    limit: int = 50,
    include_read: bool = False
):
    """Get user's event notifications from both old and new systems"""
    user_id = user["id"]
    query = {"user_id": user_id}
    if not include_read:
        query["read"] = False
    
    # Get from new event_notifications
    new_notifications = await db.event_notifications.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Also get from old notifications collection
    old_query = {"user_id": user_id}
    if not include_read:
        old_query["read"] = False
    
    old_notifications = await db.notifications.find(
        old_query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Convert old format to new format
    for n in old_notifications:
        n["message"] = n.get("message") or n.get("title", "")
        n["type"] = n.get("type", "notification")
    
    # Combine and sort by created_at
    combined = new_notifications + old_notifications
    combined.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return combined[:limit]


@router.get("/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    """Get count of unread notifications from both systems"""
    user_id = user["id"]
    
    # Count from new system
    new_count = await db.event_notifications.count_documents({
        "user_id": user_id,
        "read": False
    })
    
    # Count from old system  
    old_count = await db.notifications.count_documents({
        "user_id": user_id,
        "read": False
    })
    
    return {"count": new_count + old_count}


@router.post("/mark-read")
async def mark_notification_read(
    user: dict = Depends(get_current_user),
    body: dict = Body(...)
):
    """
    Mark notification(s) as read in both old and new systems.
    
    Body options:
    - {"notification_id": "..."} - mark single notification
    - {"all": true} - mark all as read
    """
    user_id = user["id"]
    
    if body.get("all"):
        # Mark all as read in both systems
        result1 = await db.event_notifications.update_many(
            {"user_id": user_id, "read": False},
            {"$set": {"read": True}}
        )
        result2 = await db.notifications.update_many(
            {"user_id": user_id, "read": False},
            {"$set": {"read": True}}
        )
        return {"marked": result1.modified_count + result2.modified_count}
    
    notification_id = body.get("notification_id")
    if notification_id:
        # Try to mark in new system
        result1 = await db.event_notifications.update_one(
            {"id": notification_id, "user_id": user_id},
            {"$set": {"read": True}}
        )
        # Also try in old system
        result2 = await db.notifications.update_one(
            {"id": notification_id, "user_id": user_id},
            {"$set": {"read": True}}
        )
        return {"marked": result1.modified_count + result2.modified_count}
    
    raise HTTPException(status_code=400, detail="Specify notification_id or all:true")


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a specific notification"""
    result = await db.event_notifications.delete_one({
        "id": notification_id,
        "user_id": user["id"]
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"status": "deleted"}
