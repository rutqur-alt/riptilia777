
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional
from core.auth import get_current_user, hash_password, verify_password
from core.database import db
from bson import ObjectId
from datetime import datetime, timezone
import logging
import uuid
import secrets

from .models import MerchantUpdate, MerchantResponse
from .utils import get_merchant_stats

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/me", response_model=MerchantResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "merchant":
        raise HTTPException(status_code=403, detail="Only merchants can access this endpoint")
        
    merchant = await db.merchants.find_one({"id": current_user["id"]}, {"_id": 0, "password_hash": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
        
    # Update stats
    stats = await get_merchant_stats(current_user["id"])
    merchant.update(stats)
    
    return merchant

@router.put("/me", response_model=MerchantResponse)
async def update_me(
    data: MerchantUpdate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "merchant":
        raise HTTPException(status_code=403, detail="Only merchants can access this endpoint")
        
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    
    if not update_data:
        merchant = await db.merchants.find_one({"id": current_user["id"]}, {"_id": 0, "password_hash": 0})
        return merchant
            
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.merchants.update_one(
        {"id": current_user["id"]},
        {"$set": update_data}
    )
    
    merchant = await db.merchants.find_one({"id": current_user["id"]}, {"_id": 0, "password_hash": 0})
    
    # Update stats
    stats = await get_merchant_stats(current_user["id"])
    merchant.update(stats)
    
    return merchant

@router.post("/me/change-password")
async def change_password(
    current_password: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "merchant":
        raise HTTPException(status_code=403, detail="Only merchants can access this endpoint")
        
    merchant = await db.merchants.find_one({"id": current_user["id"]})
    
    if not verify_password(current_password, merchant["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect current password")
        
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
    new_hash = hash_password(new_password)
    await db.merchants.update_one(
        {"id": current_user["id"]},
        {"$set": {"password_hash": new_hash, "password_changed_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"status": "success", "message": "Password updated"}

@router.post("/me/regenerate-api-key")
async def regenerate_api_key(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "merchant":
        raise HTTPException(status_code=403, detail="Only merchants can access this endpoint")
        
    new_api_key = secrets.token_urlsafe(32)
    new_api_secret = secrets.token_urlsafe(64)
    
    await db.merchants.update_one(
        {"id": current_user["id"]},
        {"$set": {
            "api_key": new_api_key,
            "api_secret": new_api_secret,
            "api_key_updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {
        "status": "success", 
        "api_key": new_api_key,
        "api_secret": new_api_secret
    }
