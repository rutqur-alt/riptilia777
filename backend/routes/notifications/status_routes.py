
from fastapi import APIRouter, Depends
from datetime import datetime, timezone

from core.database import db
from core.auth import get_current_user

router = APIRouter()

@router.post("/users/heartbeat")
async def user_heartbeat(user: dict = Depends(get_current_user)):
    """Update user's last seen timestamp"""
    await db.traders.update_one(
        {"id": user["id"]},
        {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}}
    )
    return {"status": "ok"}


@router.get("/users/{user_id}/online-status")
async def get_user_online_status(user_id: str):
    """Check if user is online (active in last 5 minutes)"""
    user = await db.traders.find_one({"id": user_id}, {"_id": 0, "last_seen": 1})
    if not user or not user.get("last_seen"):
        return {"online": False, "last_seen": None}
    
    last_seen = datetime.fromisoformat(user["last_seen"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    diff_minutes = (now - last_seen).total_seconds() / 60
    
    return {
        "online": diff_minutes < 5,
        "last_seen": user["last_seen"],
        "minutes_ago": int(diff_minutes)
    }
