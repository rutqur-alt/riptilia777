
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter()

@router.get("/violations")
async def get_forum_violations(user: dict = Depends(get_current_user)):
    """Get forum violations log (admin only)"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для администраторов")
    
    violations = await db.forum_violations.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return violations


@router.post("/unban/{user_id}")
async def unban_forum_user(user_id: str, user: dict = Depends(get_current_user)):
    """Unban user from forum (admin only)"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для администраторов")
    
    await db.traders.update_one(
        {"id": user_id},
        {"$unset": {"forum_ban_until": ""}}
    )
    
    return {"status": "unbanned"}
