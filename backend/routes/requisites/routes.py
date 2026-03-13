
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from core.auth import get_current_user, require_role
from core.database import db
from bson import ObjectId
from datetime import datetime, timezone
import logging
import uuid

from .models import RequisiteCreate, RequisiteResponse

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[RequisiteResponse])
async def get_my_requisites(current_user: dict = Depends(get_current_user)):
    """Get current user's requisites"""
    if current_user["role"] != "trader":
        raise HTTPException(status_code=403, detail="Only traders can have requisites")
        
    cursor = db.requisites.find({"trader_id": current_user["id"]})
    requisites = await cursor.to_list(length=100)
    
    # Also fetch from payment_details and convert to legacy format if needed
    # But for now let's stick to what was in requisites.py or what is used
    # The original file seemed to use db.requisites collection.
    # However, in offers.py we saw usage of payment_details.
    # Let's check if we need to sync them or if they are separate.
    # Based on previous context, payment_details seems to be the new way, 
    # but requisites might still be used by some frontend parts.
    
    return requisites

@router.post("/", response_model=RequisiteResponse)
async def create_requisite(
    requisite_data: RequisiteCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new requisite"""
    if current_user["role"] != "trader":
        raise HTTPException(status_code=403, detail="Only traders can create requisites")
        
    requisite_dict = requisite_data.dict()
    requisite_dict["id"] = str(uuid.uuid4())
    requisite_dict["trader_id"] = current_user["id"]
    requisite_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.requisites.insert_one(requisite_dict)
    
    # Also save to payment_details for compatibility if needed
    # Mapping logic would go here if we want to keep them in sync
    
    return requisite_dict

@router.delete("/{requisite_id}")
async def delete_requisite(
    requisite_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a requisite"""
    result = await db.requisites.delete_one({
        "id": requisite_id,
        "trader_id": current_user["id"]
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Requisite not found")
        
    return {"status": "success", "message": "Requisite deleted"}
