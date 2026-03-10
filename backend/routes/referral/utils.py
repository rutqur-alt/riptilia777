
from datetime import datetime, timezone
import secrets
import uuid

from core.database import db

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
