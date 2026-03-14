"""
Payment details routes for traders - CRUD operations on payment requisites
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
from core.auth import get_current_user
from core.database import db
from datetime import datetime, timezone
import uuid
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def require_role(roles):
    async def _require(user=Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _require

class PaymentDetailCreate(BaseModel):
    payment_type: Optional[str] = "card"
    bank_name: Optional[str] = None
    card_number: Optional[str] = None
    holder_name: Optional[str] = None
    phone_number: Optional[str] = None
    operator_name: Optional[str] = None
    qr_link: Optional[str] = None
    qr_data: Optional[str] = None
    comment: Optional[str] = None
    is_active: Optional[bool] = True
    min_amount_rub: Optional[float] = 100
    max_amount_rub: Optional[float] = 500000
    daily_limit_rub: Optional[float] = 1500000
    priority: Optional[int] = 10

class PaymentDetailUpdate(BaseModel):
    payment_type: Optional[str] = None
    bank_name: Optional[str] = None
    card_number: Optional[str] = None
    holder_name: Optional[str] = None
    phone_number: Optional[str] = None
    operator_name: Optional[str] = None
    qr_link: Optional[str] = None
    qr_data: Optional[str] = None
    comment: Optional[str] = None
    is_active: Optional[bool] = None
    min_amount_rub: Optional[float] = None
    max_amount_rub: Optional[float] = None
    daily_limit_rub: Optional[float] = None
    priority: Optional[int] = None

@router.get("/trader/payment-details")
async def get_payment_details(user: dict = Depends(require_role(["trader"]))):
    trader_id = user["id"]
    details = await db.payment_details.find(
        {"trader_id": trader_id},
        {"_id": 0}
    ).to_list(50)
    return details

@router.post("/trader/payment-details")
async def create_payment_detail(
    data: PaymentDetailCreate,
    user: dict = Depends(require_role(["trader"]))
):
    trader_id = user["id"]
    detail = {
        "id": f"pd_{uuid.uuid4().hex[:12]}",
        "trader_id": trader_id,
        "payment_type": data.payment_type or "card",
        "bank_name": data.bank_name,
        "card_number": data.card_number,
        "holder_name": data.holder_name,
        "phone_number": data.phone_number,
        "operator_name": data.operator_name,
        "qr_link": data.qr_link or data.qr_data,
        "qr_data": data.qr_data or data.qr_link,
        "comment": data.comment,
        "is_active": data.is_active if data.is_active is not None else True,
        "min_amount_rub": data.min_amount_rub or 100,
        "max_amount_rub": data.max_amount_rub or 500000,
        "daily_limit_rub": data.daily_limit_rub or 1500000,
        "used_today_rub": 0,
        "priority": data.priority or 10,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payment_details.insert_one(detail)
    detail.pop("_id", None)
    return {"success": True, "detail": detail}

@router.put("/trader/payment-details/{detail_id}")
async def update_payment_detail(
    detail_id: str,
    data: PaymentDetailUpdate,
    user: dict = Depends(require_role(["trader"]))
):
    trader_id = user["id"]
    existing = await db.payment_details.find_one({
        "id": detail_id,
        "trader_id": trader_id
    })
    if not existing:
        raise HTTPException(status_code=404, detail="Requisite not found")
    update_data = {
        "payment_type": data.payment_type or existing.get("payment_type"),
        "bank_name": data.bank_name,
        "card_number": data.card_number,
        "holder_name": data.holder_name,
        "phone_number": data.phone_number,
        "operator_name": data.operator_name,
        "qr_link": data.qr_link or data.qr_data,
        "qr_data": data.qr_data or data.qr_link,
        "comment": data.comment,
        "is_active": data.is_active if data.is_active is not None else existing.get("is_active", True),
        "min_amount_rub": data.min_amount_rub or existing.get("min_amount_rub", 100),
        "max_amount_rub": data.max_amount_rub or existing.get("max_amount_rub", 500000),
        "daily_limit_rub": data.daily_limit_rub or existing.get("daily_limit_rub", 1500000),
        "priority": data.priority or existing.get("priority", 10),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payment_details.update_one(
        {"id": detail_id, "trader_id": trader_id},
        {"$set": update_data}
    )
    return {"success": True, "message": "Requisite updated"}

@router.delete("/trader/payment-details/{detail_id}")
async def delete_payment_detail(
    detail_id: str,
    user: dict = Depends(require_role(["trader"]))
):
    trader_id = user["id"]
    result = await db.payment_details.delete_one({
        "id": detail_id,
        "trader_id": trader_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Requisite not found")
    return {"success": True, "message": "Requisite deleted"}
