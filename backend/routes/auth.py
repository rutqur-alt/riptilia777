"""
Auth routes - registration, login, profile
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
import uuid
import random

from core.database import db
from core.auth import (
    hash_password, verify_password, create_token, 
    get_current_user
)
from models.schemas import (
    TraderCreate, MerchantCreate, LoginRequest, TokenResponse
)

router = APIRouter(tags=["auth"])


async def generate_unique_deposit_code():
    """Generate unique 6-digit deposit code"""
    for _ in range(100):  # Max attempts
        code = str(random.randint(100000, 999999))
        # Check uniqueness
        existing = await db.traders.find_one({"deposit_code": code})
        if not existing:
            existing = await db.merchants.find_one({"deposit_code": code})
        if not existing:
            return code
    raise Exception("Could not generate unique deposit code")


@router.post("/auth/trader/register", response_model=TokenResponse)
async def register_trader(data: TraderCreate):
    existing = await db.traders.find_one({"login": data.login}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Логин уже занят")
    
    existing_nickname = await db.traders.find_one({"nickname": data.nickname}, {"_id": 0})
    if not existing_nickname:
        existing_nickname = await db.merchants.find_one({"nickname": data.nickname}, {"_id": 0})
    if existing_nickname:
        raise HTTPException(status_code=400, detail="Никнейм уже занят")
    
    if len(data.nickname) < 3 or len(data.nickname) > 20:
        raise HTTPException(status_code=400, detail="Никнейм должен быть от 3 до 20 символов")
    
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    
    ref_code = f"T{uuid.uuid4().hex[:6].upper()}"
    recovery_key = f"RK-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
    deposit_code = await generate_unique_deposit_code()
    
    referred_by = None
    if data.referral_code:
        referrer = await db.traders.find_one({"referral_code": data.referral_code}, {"_id": 0})
        if not referrer:
            referrer = await db.merchants.find_one({"referral_code": data.referral_code}, {"_id": 0})
        if referrer:
            referred_by = referrer["id"]
    
    trader_doc = {
        "id": str(uuid.uuid4()),
        "login": data.login,
        "nickname": data.nickname,
        "password_hash": hash_password(data.password),
        "role": "trader",
        "balance_usdt": 0.0,
        "frozen_usdt": 0.0,
        "deposit_code": deposit_code,
        "commission_rate": settings.get("trader_commission", 1.0) if settings else 1.0,
        "accepted_merchant_types": ["casino", "shop", "stream", "other"],
        "referral_code": ref_code,
        "referred_by": referred_by,
        "referral_earnings": 0.0,
        "recovery_key": recovery_key,
        "is_blocked": False,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.traders.insert_one(trader_doc)
    
    # Create referral chain if referred by someone
    if referred_by:
        from routes.referral import create_referral_chain
        await create_referral_chain(trader_doc["id"], referred_by)
    
    created_trader = await db.traders.find_one({"id": trader_doc["id"]}, {"_id": 0})
    
    token = create_token(trader_doc["id"], "trader")
    user_response = {k: v for k, v in created_trader.items() if k != "password_hash"}
    user_response["recovery_key"] = recovery_key
    
    return {"token": token, "user": user_response}


@router.post("/auth/merchant/register", response_model=TokenResponse)
async def register_merchant(data: MerchantCreate):
    existing = await db.merchants.find_one({"login": data.login}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Логин уже занят")
    
    existing_nickname = await db.traders.find_one({"nickname": data.nickname}, {"_id": 0})
    if not existing_nickname:
        existing_nickname = await db.merchants.find_one({"nickname": data.nickname}, {"_id": 0})
    if existing_nickname:
        raise HTTPException(status_code=400, detail="Никнейм уже занят")
    
    if len(data.nickname) < 3 or len(data.nickname) > 20:
        raise HTTPException(status_code=400, detail="Никнейм должен быть от 3 до 20 символов")
    
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    commission_key = f"{data.merchant_type}_commission"
    commission_rate = settings.get(commission_key, 0.5) if settings else 0.5
    
    ref_code = f"M{uuid.uuid4().hex[:6].upper()}"
    recovery_key = f"RK-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
    deposit_code = await generate_unique_deposit_code()
    
    referred_by = None
    if data.referral_code:
        referrer = await db.traders.find_one({"referral_code": data.referral_code}, {"_id": 0})
        if not referrer:
            referrer = await db.merchants.find_one({"referral_code": data.referral_code}, {"_id": 0})
        if referrer:
            referred_by = referrer["id"]
    
    merchant_id = str(uuid.uuid4())
    merchant_doc = {
        "id": merchant_id,
        "login": data.login,
        "nickname": data.nickname,
        "password_hash": hash_password(data.password),
        "role": "merchant",
        "merchant_name": data.merchant_name,
        "merchant_type": data.merchant_type,
        "telegram": data.telegram,
        "status": "pending",
        "balance_usdt": 0.0,
        "frozen_usdt": 0.0,
        "deposit_code": deposit_code,
        "commission_rate": commission_rate,
        "total_commission_paid": 0.0,
        "api_key": None,
        "webhook_url": "",
        "approved_at": None,
        "approved_by": None,
        "rejection_reason": None,
        "referral_code": ref_code,
        "referred_by": referred_by,
        "referral_earnings": 0.0,
        "recovery_key": recovery_key,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.merchants.insert_one(merchant_doc)
    
    # Create referral chain if referred by someone
    if referred_by:
        from routes.referral import create_referral_chain
        await create_referral_chain(merchant_id, referred_by)
    
    # Create merchant application
    app_doc = {
        "id": str(uuid.uuid4()),
        "user_id": merchant_id,
        "nickname": data.nickname,
        "merchant_name": data.merchant_name,
        "merchant_type": data.merchant_type,
        "website": data.telegram or "",
        "description": f"Тип: {data.merchant_type}. Telegram: {data.telegram or 'не указан'}",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.merchant_applications.insert_one(app_doc)
    
    # Create unified_conversation for chat
    conv_id = str(uuid.uuid4())
    conv_doc = {
        "id": conv_id,
        "type": "merchant_application",
        "status": "pending",
        "related_id": app_doc["id"],
        "participants": [merchant_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_conversations.insert_one(conv_doc)
    
    welcome_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"🎰 Заявка на регистрацию мерчанта: {data.merchant_name}\n\nТип: {data.merchant_type}\nTelegram: {data.telegram or 'не указан'}\n\nДобро пожаловать! Расскажите о вашей площадке и планируемых объемах.",
        "is_system": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(welcome_msg)
    
    created_merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    
    token = create_token(merchant_doc["id"], "merchant")
    user_response = {k: v for k, v in created_merchant.items() if k != "password_hash"}
    user_response["recovery_key"] = recovery_key
    
    return {"token": token, "user": user_response}


@router.post("/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request):
    user = await db.traders.find_one({"login": data.login}, {"_id": 0})
    role = "trader"
    
    if not user:
        user = await db.merchants.find_one({"login": data.login}, {"_id": 0})
        role = "merchant"
    
    if not user:
        user = await db.admins.find_one({"login": data.login}, {"_id": 0})
        role = "admin"
    
    if not user:
        user = await db.qr_providers.find_one({"login": data.login}, {"_id": 0})
        role = "qr_provider"
    
    if not user:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    
    password_field = user.get("password_hash") or user.get("password")
    if not password_field or not verify_password(data.password, password_field):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    
    if user.get("is_blocked") or user.get("status") == "blocked":
        raise HTTPException(
            status_code=403, 
            detail={
                "message": "Ваш аккаунт заблокирован",
                "blocked": True,
                "recovery_hint": "Для восстановления доступа создайте тикет с ключом восстановления"
            }
        )
    
    token = create_token(user["id"], role)
    user_response = {k: v for k, v in user.items() if k not in ["password_hash", "password", "recovery_key"]}
    user_response["role"] = role
    
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    await db.login_history.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "role": role,
        "ip": client_ip,
        "user_agent": user_agent[:200],
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    collection = db.traders if role == "trader" else db.merchants if role == "merchant" else db.qr_providers if role == "qr_provider" else db.admins
    await collection.update_one(
        {"id": user["id"]},
        {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"token": token, "user": user_response}


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    # Strip sensitive fields
    safe_user = {k: v for k, v in user.items() if k not in ["password_hash", "password", "recovery_key"]}
    return {"user": safe_user}
