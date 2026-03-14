from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone

from core.auth import require_role, get_current_user
from core.database import db

router = APIRouter(tags=["crypto"])

@router.get("/admin/payout-settings")
async def get_payout_settings(user: dict = Depends(require_role(["admin", "owner"]))):
    """Get payout settings (rates, limits)"""
    settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    if not settings:
        settings = {
            "base_rate": 100.0,
            "sell_rate": 110.0,
            "min_successful_trades": 20,
            "rate_source": "manual",
            "rate_updated_at": datetime.now(timezone.utc).isoformat()
        }
    return settings


@router.post("/admin/payout-settings")
async def update_payout_settings(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Update payout settings"""
    update_data = {
        "base_rate": data.get("base_rate"),
        "sell_rate": data.get("sell_rate"),
        "min_successful_trades": data.get("min_successful_trades"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": user["id"]
    }
    
    # Remove None values
    update_data = {k: v for k, v in update_data.items() if v is not None}
    
    await db.settings.update_one(
        {"type": "payout_settings"},
        {"$set": update_data},
        upsert=True
    )
    
    return {"status": "updated", "settings": update_data}


@router.get("/public/payout-settings")
async def get_public_payout_settings():
    """Get public payout settings (rates)"""
    settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    if not settings:
        return {
            "base_rate": 100.0,
            "sell_rate": 110.0,
            "min_successful_trades": 20
        }
    return {
        "base_rate": settings.get("base_rate", 100.0),
        "sell_rate": settings.get("sell_rate", 110.0),
        "min_successful_trades": settings.get("min_successful_trades", 20)
    }


@router.get("/admin/platform-balance")
async def get_platform_balance(user: dict = Depends(require_role(["admin", "owner"]))):
    """Get platform accumulated profit from payouts"""
    balance = await db.settings.find_one({"type": "platform_balance"}, {"_id": 0})
    return {"balance_usdt": balance.get("balance_usdt", 0) if balance else 0}


@router.get("/payout-settings/public")
async def get_public_payout_settings_alias():
    """Alias for /public/payout-settings - used by trader dashboard"""
    settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    if not settings:
        return {
            "rules": "",
            "base_rate": 100.0,
            "sell_rate": 110.0,
            "min_successful_trades": 20
        }
    return {
        "rules": settings.get("rules", ""),
        "base_rate": settings.get("base_rate", 100.0),
        "sell_rate": settings.get("sell_rate", 110.0),
        "min_successful_trades": settings.get("min_successful_trades", 20)
    }
