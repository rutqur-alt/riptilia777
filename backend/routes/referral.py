"""
Referral System - Реферальная система
Адаптировано из BIT-9-DOK-main для интеграции в REP01-main

Функции:
- 3 уровня рефералов: 5%, 3%, 1% от заработка трейдера
- Реферальный баланс в USDT
- Вывод бонусов на основной баланс
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional
import secrets
import uuid

from core.database import db
from core.auth import get_current_user

router = APIRouter(tags=["referral"])

# Default referral settings
DEFAULT_REFERRAL_LEVELS = [
    {"level": 1, "percent": 5},
    {"level": 2, "percent": 3},
    {"level": 3, "percent": 1}
]


def generate_referral_code() -> str:
    """Генерация уникального реферального кода"""
    return secrets.token_hex(4).upper()


async def create_referral_chain(user_id: str, referrer_id: str):
    """Создаёт цепочку реферальных связей (до 3 уровней)"""
    now = datetime.now(timezone.utc).isoformat()
    
    # Level 1 - direct referrer
    await db.referrals.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "referrer_id": referrer_id,
        "level": 1,
        "created_at": now
    })
    
    # Level 2 - referrer's referrer
    level1_user = await db.traders.find_one({"id": referrer_id}, {"referrer_id": 1})
    if not level1_user:
        level1_user = await db.merchants.find_one({"id": referrer_id}, {"referrer_id": 1})
    
    if level1_user and level1_user.get("referrer_id"):
        await db.referrals.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "referrer_id": level1_user["referrer_id"],
            "level": 2,
            "created_at": now
        })
        
        # Level 3
        level2_user = await db.traders.find_one({"id": level1_user["referrer_id"]}, {"referrer_id": 1})
        if not level2_user:
            level2_user = await db.merchants.find_one({"id": level1_user["referrer_id"]}, {"referrer_id": 1})
        
        if level2_user and level2_user.get("referrer_id"):
            await db.referrals.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "referrer_id": level2_user["referrer_id"],
                "level": 3,
                "created_at": now
            })


async def process_referral_bonus(trader_id: str, commission_usdt: float):
    """
    Начисляет реферальные бонусы при завершении сделки.
    Вызывается когда трейдер получает комиссию от сделки.
    
    Args:
        trader_id: ID трейдера, получившего комиссию
        commission_usdt: Сумма комиссии трейдера в USDT
    """
    if commission_usdt <= 0:
        return
    
    # Get referral settings
    settings = await db.referral_settings.find_one({}, {"_id": 0})
    levels = settings.get("levels", DEFAULT_REFERRAL_LEVELS) if settings else DEFAULT_REFERRAL_LEVELS
    
    # Find all referrers for this trader
    referrals = await db.referrals.find({"user_id": trader_id}, {"_id": 0}).to_list(10)
    
    now = datetime.now(timezone.utc).isoformat()
    
    for ref in referrals:
        referrer_id = ref["referrer_id"]
        level = ref["level"]
        
        # Get percent for this level
        level_config = next((l for l in levels if l["level"] == level), None)
        if not level_config:
            continue
        
        percent = level_config["percent"]
        bonus_usdt = round(commission_usdt * percent / 100, 6)
        
        if bonus_usdt <= 0:
            continue
        
        # Find referrer (can be trader or merchant)
        referrer = await db.traders.find_one({"id": referrer_id}, {"_id": 0})
        if not referrer:
            referrer = await db.merchants.find_one({"id": referrer_id}, {"_id": 0})
        
        if not referrer:
            continue
        
        # Update referral balance
        collection = "traders" if await db.traders.find_one({"id": referrer_id}) else "merchants"
        
        await db[collection].update_one(
            {"id": referrer_id},
            {"$inc": {"referral_balance_usdt": bonus_usdt}}
        )
        
        # Save to referral history
        trader = await db.traders.find_one({"id": trader_id}, {"_id": 0, "nickname": 1, "login": 1})
        
        await db.referral_history.insert_one({
            "id": str(uuid.uuid4()),
            "referrer_id": referrer_id,
            "from_user_id": trader_id,
            "from_nickname": trader.get("nickname") or trader.get("login", "Unknown"),
            "level": level,
            "percent": percent,
            "original_commission_usdt": commission_usdt,
            "bonus_usdt": bonus_usdt,
            "created_at": now
        })


# ================== API ENDPOINTS ==================

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


# ================== ADMIN ENDPOINTS ==================

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
