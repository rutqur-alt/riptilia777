
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import get_current_user
from .utils import generate_referral_code, DEFAULT_REFERRAL_LEVELS

router = APIRouter()

@router.get("/referral")
async def get_referral_data(user: dict = Depends(get_current_user)):
    """Получить данные реферальной программы для пользователя"""
    user_id = user["id"]
    role = user.get("role", "trader")
    
    # Get user data with referral info
    if role == "trader":
        user_data = await db.traders.find_one({"id": user_id}, {"_id": 0})
    else:
        user_data = await db.merchants.find_one({"id": user_id}, {"_id": 0})
    
    if not user_data:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Generate referral code if not exists
    referral_code = user_data.get("referral_code")
    if not referral_code:
        referral_code = generate_referral_code()
        collection = "traders" if role == "trader" else "merchants"
        await db[collection].update_one(
            {"id": user_id},
            {"$set": {"referral_code": referral_code}}
        )
    
    # Get referral settings
    settings = await db.referral_settings.find_one({}, {"_id": 0})
    levels = settings.get("levels", DEFAULT_REFERRAL_LEVELS) if settings else DEFAULT_REFERRAL_LEVELS
    min_withdrawal = settings.get("min_withdrawal_usdt", 1.0) if settings else 1.0
    
    # Count referrals by level
    level_stats = []
    total_referrals = 0
    
    for level_config in levels:
        level = level_config["level"]
        count = await db.referrals.count_documents({
            "referrer_id": user_id,
            "level": level
        })
        level_stats.append({
            "level": level,
            "percent": level_config["percent"],
            "count": count
        })
        if level == 1:
            total_referrals = count
    
    # Get referral balance
    referral_balance = user_data.get("referral_balance_usdt", 0)
    
    # Get total earned
    pipeline = [
        {"$match": {"referrer_id": user_id}},
        {"$group": {"_id": None, "total": {"$sum": "$bonus_usdt"}}}
    ]
    total_earned_result = await db.referral_history.aggregate(pipeline).to_list(1)
    total_earned = total_earned_result[0]["total"] if total_earned_result else 0
    
    # Get history (last 50)
    history = await db.referral_history.find(
        {"referrer_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    return {
        "referral_code": referral_code,
        "referral_balance_usdt": referral_balance,
        "total_earned_usdt": total_earned,
        "total_referrals": total_referrals,
        "level_stats": level_stats,
        "history": history,
        "settings": {
            "levels": levels,
            "min_withdrawal_usdt": min_withdrawal,
            "level1_percent": levels[0]["percent"] if levels else 5,
            "level2_percent": levels[1]["percent"] if len(levels) > 1 else 3,
            "level3_percent": levels[2]["percent"] if len(levels) > 2 else 1
        }
    }


@router.post("/referral/withdraw")
async def withdraw_referral_bonus(user: dict = Depends(get_current_user)):
    """Вывести реферальный бонус на основной баланс"""
    user_id = user["id"]
    role = user.get("role", "trader")
    
    collection = "traders" if role == "trader" else "merchants"
    user_data = await db[collection].find_one({"id": user_id}, {"_id": 0})
    
    if not user_data:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    referral_balance = user_data.get("referral_balance_usdt", 0)
    
    # Get minimum withdrawal
    settings = await db.referral_settings.find_one({}, {"_id": 0})
    min_withdrawal = settings.get("min_withdrawal_usdt", 1.0) if settings else 1.0
    
    if referral_balance < min_withdrawal:
        raise HTTPException(
            status_code=400,
            detail=f"Минимальная сумма для вывода: {min_withdrawal} USDT"
        )
    
    # Transfer to main balance
    await db[collection].update_one(
        {"id": user_id},
        {
            "$inc": {"balance_usdt": referral_balance},
            "$set": {"referral_balance_usdt": 0}
        }
    )
    
    # Log withdrawal
    await db.referral_withdrawals.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "amount_usdt": referral_balance,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {
        "status": "success",
        "message": f"Переведено {referral_balance:.4f} USDT на основной баланс",
        "amount": referral_balance
    }
