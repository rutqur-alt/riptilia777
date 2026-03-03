"""
Requisites routes - manage trader payment requisites (cards, SBP, QR codes)
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List
import uuid

from core.database import db
from core.auth import require_role
from models.schemas import RequisiteCreate, RequisiteResponse

router = APIRouter(tags=["requisites"])

# Limits per requisite type
REQUISITE_TYPE_LIMITS = {
    "card": 5,
    "sbp": 5,
    "qr": 5,
    "sim": 5,
    "cis": 5
}


@router.get("/requisites", response_model=List[RequisiteResponse])
async def get_requisites(user: dict = Depends(require_role(["trader"]))):
    """Get all requisites for current trader"""
    requisites = await db.requisites.find({"trader_id": user["id"]}, {"_id": 0}).to_list(100)
    return requisites


@router.post("/requisites", response_model=RequisiteResponse)
async def create_requisite(data: RequisiteCreate, user: dict = Depends(require_role(["trader"]))):
    """Create a new requisite (max 5 per type)"""
    if data.type not in REQUISITE_TYPE_LIMITS:
        raise HTTPException(status_code=400, detail="Invalid requisite type")
    
    # Check limit
    count = await db.requisites.count_documents({"trader_id": user["id"], "type": data.type})
    if count >= REQUISITE_TYPE_LIMITS[data.type]:
        raise HTTPException(status_code=400, detail=f"Maximum {REQUISITE_TYPE_LIMITS[data.type]} requisites of type '{data.type}' allowed")
    
    # Check if this is the first of this type - make it primary
    is_primary = count == 0
    if data.data.get("is_primary"):
        is_primary = True
        # Remove primary from others of this type
        await db.requisites.update_many(
            {"trader_id": user["id"], "type": data.type},
            {"$set": {"data.is_primary": False}}
        )
    
    requisite_doc = {
        "id": str(uuid.uuid4()),
        "trader_id": user["id"],
        "type": data.type,
        "data": {**data.data, "is_primary": is_primary},
        "is_primary": is_primary,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.requisites.insert_one(requisite_doc)
    return requisite_doc


@router.put("/requisites/{requisite_id}", response_model=RequisiteResponse)
async def update_requisite(requisite_id: str, data: RequisiteCreate, user: dict = Depends(require_role(["trader"]))):
    """Update a requisite"""
    requisite = await db.requisites.find_one({"id": requisite_id, "trader_id": user["id"]})
    if not requisite:
        raise HTTPException(status_code=404, detail="Requisite not found")
    
    is_primary = data.data.get("is_primary", False)
    if is_primary:
        # Remove primary from others of this type
        await db.requisites.update_many(
            {"trader_id": user["id"], "type": requisite["type"], "id": {"$ne": requisite_id}},
            {"$set": {"data.is_primary": False, "is_primary": False}}
        )
    
    await db.requisites.update_one(
        {"id": requisite_id},
        {"$set": {
            "data": {**data.data, "is_primary": is_primary},
            "is_primary": is_primary
        }}
    )
    
    updated = await db.requisites.find_one({"id": requisite_id}, {"_id": 0})
    return updated


@router.delete("/requisites/{requisite_id}")
async def delete_requisite(requisite_id: str, user: dict = Depends(require_role(["trader"]))):
    """Delete a requisite"""
    requisite = await db.requisites.find_one({"id": requisite_id, "trader_id": user["id"]})
    if not requisite:
        raise HTTPException(status_code=404, detail="Requisite not found")
    
    await db.requisites.delete_one({"id": requisite_id})
    
    # If deleted was primary, make another one primary
    if requisite.get("is_primary"):
        next_requisite = await db.requisites.find_one({"trader_id": user["id"], "type": requisite["type"]})
        if next_requisite:
            await db.requisites.update_one(
                {"id": next_requisite["id"]},
                {"$set": {"is_primary": True, "data.is_primary": True}}
            )
    
    return {"status": "deleted"}


@router.post("/requisites/{requisite_id}/set-primary")
async def set_requisite_primary(requisite_id: str, user: dict = Depends(require_role(["trader"]))):
    """Set a requisite as primary"""
    requisite = await db.requisites.find_one({"id": requisite_id, "trader_id": user["id"]})
    if not requisite:
        raise HTTPException(status_code=404, detail="Requisite not found")
    
    # Remove primary from all of this type
    await db.requisites.update_many(
        {"trader_id": user["id"], "type": requisite["type"]},
        {"$set": {"is_primary": False, "data.is_primary": False}}
    )
    
    # Set this one as primary
    await db.requisites.update_one(
        {"id": requisite_id},
        {"$set": {"is_primary": True, "data.is_primary": True}}
    )
    
    return {"status": "ok"}
