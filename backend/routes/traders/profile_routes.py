
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional
from core.auth import get_current_user, hash_password
from core.database import db
from bson import ObjectId
from datetime import datetime, timezone
import logging
import uuid

from .models import TraderUpdate, TraderResponse
from .utils import get_trader_stats

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/me", response_model=TraderResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "trader":
        raise HTTPException(status_code=403, detail="Only traders can access this endpoint")
        
    trader = await db.traders.find_one({"id": current_user["id"]}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
        
    # Update stats
    stats = await get_trader_stats(current_user["id"])
    trader.update(stats)
    
    # Ensure nickname is set
    if not trader.get("nickname"):
        trader["nickname"] = trader["login"]
        
    return trader

@router.put("/me", response_model=TraderResponse)
async def update_me(
    data: TraderUpdate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "trader":
        raise HTTPException(status_code=403, detail="Only traders can access this endpoint")
        
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    
    if not update_data:
        # Return current state if no updates
        trader = await db.traders.find_one({"id": current_user["id"]}, {"_id": 0})
        return trader
        
    # Check nickname uniqueness if changing
    if "nickname" in update_data:
        existing = await db.traders.find_one({
            "nickname": update_data["nickname"], 
            "id": {"$ne": current_user["id"]}
        })
        if existing:
            raise HTTPException(status_code=400, detail="Nickname already taken")
            
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.traders.update_one(
        {"id": current_user["id"]},
        {"$set": update_data}
    )
    
    trader = await db.traders.find_one({"id": current_user["id"]}, {"_id": 0})
    
    # Update stats
    stats = await get_trader_stats(current_user["id"])
    trader.update(stats)
    
    return trader

@router.post("/me/change-password")
async def change_password(
    current_password: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "trader":
        raise HTTPException(status_code=403, detail="Only traders can access this endpoint")
        
    # Verify current password (this logic is usually in auth service, but let's do it here or reuse)
    # Since we don't have verify_password imported here easily without circular deps or duplicating,
    # let's assume we can import it from core.auth
    from core.auth import verify_password
    
    # Get full user doc with password hash
    # Note: get_current_user returns dict without password_hash usually, need to fetch
    user_doc = await db.traders.find_one({"id": current_user["id"]})
    
    if not verify_password(current_password, user_doc["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect current password")
        
    # Update password
    new_hash = hash_password(new_password)
    await db.traders.update_one(
        {"id": current_user["id"]},
        {"$set": {"password_hash": new_hash}}
    )
    
    return {"status": "success", "message": "Password updated"}
