
from fastapi import APIRouter, Depends

from core.database import db
from core.auth import get_current_user

router = APIRouter()

@router.get("/security/login-history")
async def get_login_history(user: dict = Depends(get_current_user)):
    """Get user's login history"""
    history = await db.login_history.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    return history
