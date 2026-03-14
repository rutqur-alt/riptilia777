from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional

from core.database import db
from core.auth import require_role, require_admin_level, log_admin_action
from models.schemas import CommissionSettings, UpdateCommissionSettings

router = APIRouter()

# ==================== COMMISSION SETTINGS ====================

@router.get("/commission-settings", response_model=CommissionSettings)
async def get_commission_settings(user: dict = Depends(require_role(["admin"]))):
    """Get platform commission settings"""
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {"trader_commission": 1.0, "minimum_commission": 0.01}
    return settings


@router.put("/commission-settings", response_model=CommissionSettings)
async def update_commission_settings(data: UpdateCommissionSettings, user: dict = Depends(require_role(["admin"]))):
    """Update platform commission settings"""
    update_data = {}
    if data.trader_commission is not None:
        update_data["trader_commission"] = data.trader_commission
    if data.minimum_commission is not None:
        update_data["minimum_commission"] = data.minimum_commission
    if data.gambling_commission is not None:
        update_data["gambling_commission"] = data.gambling_commission
    if data.casino_commission is not None:
        update_data["casino_commission"] = data.casino_commission
    if data.high_risk_commission is not None:
        update_data["high_risk_commission"] = data.high_risk_commission
    if data.default_price_rub is not None:
        update_data["default_price_rub"] = data.default_price_rub
    
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        update_data["updated_by"] = user["id"]
        await db.commission_settings.update_one({}, {"$set": update_data}, upsert=True)
    
    return await db.commission_settings.find_one({}, {"_id": 0})


@router.get("/commission-history")
async def get_commission_history(user: dict = Depends(require_role(["admin"]))):
    """Get commission payment history"""
    history = await db.commission_payments.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return history


# ==================== MERCHANT FEE SETTINGS ====================

@router.get("/admin/settings/merchant-fees")
async def get_merchant_fee_settings(user: dict = Depends(require_admin_level(80))):
    """Get merchant fee settings"""
    settings = await db.settings.find_one({"type": "merchant_fees"}, {"_id": 0})
    if not settings:
        return {
            "default_commission": 3.0,
            "min_commission": 0.5,
            "max_commission": 10.0
        }
    return settings


@router.put("/admin/settings/merchant-fees")
async def update_merchant_fee_settings(data: dict, user: dict = Depends(require_admin_level(100))):
    """Update merchant fee settings"""
    update_data = {
        "type": "merchant_fees",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": user["id"]
    }
    
    if "default_commission" in data:
        update_data["default_commission"] = float(data["default_commission"])
    if "min_commission" in data:
        update_data["min_commission"] = float(data["min_commission"])
    if "max_commission" in data:
        update_data["max_commission"] = float(data["max_commission"])
        
    await db.settings.update_one(
        {"type": "merchant_fees"},
        {"$set": update_data},
        upsert=True
    )
    
    await log_admin_action(user["id"], "update_merchant_fees", "settings", "merchant_fees", update_data)
    
    return {"status": "success", "settings": update_data}


@router.get("/admin/settings/merchant-methods")
async def get_merchant_method_commissions(user: dict = Depends(require_admin_level(80))):
    """Get commission rates for different payment methods"""
    settings = await db.settings.find_one({"type": "merchant_method_commissions"}, {"_id": 0})
    if not settings:
        return {"methods": {}}
    return settings


@router.put("/admin/settings/merchant-methods")
async def update_merchant_method_commissions(data: dict, user: dict = Depends(require_admin_level(100))):
    """Update commission rates for payment methods"""
    methods = data.get("methods", {})
    
    update_data = {
        "type": "merchant_method_commissions",
        "methods": methods,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": user["id"]
    }
    
    await db.settings.update_one(
        {"type": "merchant_method_commissions"},
        {"$set": update_data},
        upsert=True
    )
    
    await log_admin_action(user["id"], "update_method_commissions", "settings", "merchant_methods", {"methods": methods})
    
    return {"status": "success", "settings": update_data}
