
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone

from core.database import db
from core.auth import get_current_user
from .utils import DEFAULT_REFERRAL_LEVELS

router = APIRouter()

@router.get("/admin/referral/settings")
async def get_referral_settings(user: dict = Depends(get_current_user)):
    """Получить настройки реферальной программы (admin only)"""
    if user.get("role") not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    settings = await db.referral_settings.find_one({}, {"_id": 0})
    
    if not settings:
        settings = {
            "levels": DEFAULT_REFERRAL_LEVELS,
            "min_withdrawal_usdt": 1.0,
            "enabled": True
        }
    
    return settings


@router.put("/admin/referral/settings")
async def update_referral_settings(
    data: dict,
    user: dict = Depends(get_current_user)
):
    """Обновить настройки реферальной программы (admin only)"""
    if user.get("role") not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    levels = data.get("levels", DEFAULT_REFERRAL_LEVELS)
    min_withdrawal = data.get("min_withdrawal_usdt", 1.0)
    enabled = data.get("enabled", True)
    
    await db.referral_settings.update_one(
        {},
        {"$set": {
            "levels": levels,
            "min_withdrawal_usdt": min_withdrawal,
            "enabled": enabled,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": user["id"]
        }},
        upsert=True
    )
    
    return {"status": "success", "message": "Настройки обновлены"}


@router.get("/admin/referral/stats")
async def get_referral_stats(user: dict = Depends(get_current_user)):
    """Статистика реферальной программы (admin only)"""
    if user.get("role") not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    # Total referrals
    total_referrals = await db.referrals.count_documents({})
    
    # By level
    level1_count = await db.referrals.count_documents({"level": 1})
    level2_count = await db.referrals.count_documents({"level": 2})
    level3_count = await db.referrals.count_documents({"level": 3})
    
    # Total bonuses paid
    pipeline = [
        {"$group": {"_id": None, "total": {"$sum": "$bonus_usdt"}}}
    ]
    total_paid_result = await db.referral_history.aggregate(pipeline).to_list(1)
    total_paid = total_paid_result[0]["total"] if total_paid_result else 0
    
    # Total withdrawn
    pipeline = [
        {"$group": {"_id": None, "total": {"$sum": "$amount_usdt"}}}
    ]
    total_withdrawn_result = await db.referral_withdrawals.aggregate(pipeline).to_list(1)
    total_withdrawn = total_withdrawn_result[0]["total"] if total_withdrawn_result else 0
    
    return {
        "total_referrals": total_referrals,
        "by_level": {
            "level1": level1_count,
            "level2": level2_count,
            "level3": level3_count
        },
        "total_bonuses_paid_usdt": round(total_paid, 4),
        "total_withdrawn_usdt": round(total_withdrawn, 4),
        "pending_balance_usdt": round(total_paid - total_withdrawn, 4)
    }
