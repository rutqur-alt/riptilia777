"""
BITARBITR P2P Platform - Auth Router
Handles registration, login, and user authentication
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import secrets
import logging

router = APIRouter(tags=["Authentication"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

# Глобальные зависимости
_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"
_send_telegram = None
_site_url = "http://localhost:3000"


def init_router(database, jwt_secret: str, jwt_algorithm: str = "HS256",
                telegram_func=None, site_url: str = None):
    """Инициализация роутера"""
    global _db, _jwt_secret, _jwt_algorithm, _send_telegram, _site_url
    _db = database
    _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm
    _send_telegram = telegram_func
    if site_url:
        _site_url = site_url


def generate_id(prefix: str = "") -> str:
    """Генерация уникального ID"""
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{prefix}{date_part}_{secrets.token_hex(3).upper()}"


async def create_referral_chain(db, user_id: str, referrer_id: str):
    """Создаёт цепочку реферальных связей (до 3 уровней)"""
    # Уровень 1 - прямой реферер
    await db.referrals.insert_one({
        "id": generate_id("ref_"),
        "user_id": user_id,
        "referrer_id": referrer_id,
        "level": 1,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Уровень 2 - реферер реферера
    level2_referrer = await db.users.find_one({"id": referrer_id}, {"referrer_id": 1})
    if level2_referrer and level2_referrer.get("referrer_id"):
        await db.referrals.insert_one({
            "id": generate_id("ref_"),
            "user_id": user_id,
            "referrer_id": level2_referrer["referrer_id"],
            "level": 2,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Уровень 3 - реферер реферера реферера
        level3_referrer = await db.users.find_one({"id": level2_referrer["referrer_id"]}, {"referrer_id": 1})
        if level3_referrer and level3_referrer.get("referrer_id"):
            await db.referrals.insert_one({
                "id": generate_id("ref_"),
                "user_id": user_id,
                "referrer_id": level3_referrer["referrer_id"],
                "level": 3,
                "created_at": datetime.now(timezone.utc).isoformat()
            })


# ================== AUTH HELPERS ==================

def create_jwt_token(user_id: str, role: str) -> str:
    """Создание JWT токена"""
    from jose import jwt
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, _jwt_secret, algorithm=_jwt_algorithm)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получение текущего пользователя из JWT"""
    from jose import jwt, JWTError
    
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    token = credentials.credentials
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await _db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# ================== MODELS ==================

class UserCreate(BaseModel):
    login: str
    nickname: str
    password: str
    role: str = "trader"
    referral_code: Optional[str] = None  # Реферальный код пригласившего


class UserLogin(BaseModel):
    login: str
    password: str
    two_factor_code: Optional[str] = None


class TelegramLink(BaseModel):
    telegram_id: int
    telegram_username: Optional[str] = None


# ================== ENDPOINTS ==================

@router.post("/auth/register")
async def register(data: UserCreate, background_tasks: BackgroundTasks):
    """Регистрация нового пользователя"""
    import bcrypt
    
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Проверка существования
    existing = await _db.users.find_one({"login": data.login})
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
    
    # Хеш пароля
    password_hash = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    user_id = generate_id("usr_")
    referral_code = secrets.token_hex(4).upper()  # Уникальный реферальный код
    now = datetime.now(timezone.utc).isoformat()
    
    # Обработка реферальной ссылки
    referrer_id = None
    if data.referral_code:
        referrer = await _db.users.find_one({"referral_code": data.referral_code.upper()}, {"_id": 0})
        if referrer:
            referrer_id = referrer["id"]
    
    user = {
        "id": user_id,
        "login": data.login,
        "nickname": data.nickname,
        "password_hash": password_hash,
        "role": data.role,
        "is_active": True,
        "is_verified": False,
        "two_factor_enabled": False,
        "referral_code": referral_code,  # Реферальный код этого пользователя
        "referrer_id": referrer_id,  # Кто пригласил (если есть)
        "referral_balance_rub": 0.0,  # Баланс реферальных бонусов
        "created_at": now,
        "approval_status": "pending" if data.role in ["trader", "merchant"] else "approved"
    }
    
    await _db.users.insert_one(user)
    
    # Создаём реферальную связь если есть пригласитель
    if referrer_id:
        await create_referral_chain(_db, user_id, referrer_id)
    
    # Создаём кошелёк
    wallet = {
        "id": generate_id("wal_"),
        "user_id": user_id,
        "available_balance_usdt": 0.0,
        "locked_balance_usdt": 0.0,
        "pending_balance_usdt": 0.0,
        "total_deposited_usdt": 0.0,
        "total_withdrawn_usdt": 0.0,
        "created_at": now
    }
    await _db.wallets.insert_one(wallet)
    
    # Роль-специфичные записи
    if data.role == "trader":
        trader = {
            "id": generate_id("trd_"),
            "user_id": user_id,
            "rating": 5.0,
            "total_deals": 0,
            "successful_deals": 0,
            "total_volume_rub": 0.0,
            "total_commission_usdt": 0.0,
            "is_available": False,
            "auto_mode": True,
            "min_deal_amount_rub": 100.0,
            "max_deal_amount_rub": 500000.0,
            "created_at": now
        }
        await _db.traders.insert_one(trader)
    elif data.role == "merchant":
        merchant = {
            "id": generate_id("merch_"),
            "user_id": user_id,
            "company_name": data.nickname,
            "api_key": f"sk_live_{secrets.token_hex(24)}",
            "total_orders": 0,
            "total_volume_usdt": 0.0,
            "fee_model": "merchant_pays",
            "total_fee_percent": 3.0,
            "created_at": now
        }
        await _db.merchants.insert_one(merchant)
    
    # Создаём тикет на одобрение для трейдеров/мерчантов
    if data.role in ["trader", "merchant"]:
        ticket_type = "trader_approval" if data.role == "trader" else "merchant_approval"
        ticket = {
            "id": generate_id("tkt_"),
            "user_id": user_id,
            "user_role": data.role,
            "subject": "",  # Пустой заголовок для заявок
            "status": "open",
            "type": ticket_type,
            "messages": [{
                "id": generate_id("msg_"),
                "sender_id": user_id,
                "sender_role": data.role,
                "sender_name": data.nickname,
                "message": f"Прошу одобрить регистрацию в качестве {data.role}",
                "created_at": now
            }],
            "unread_by_admin": 1,
            "unread_by_user": 0,
            "assigned_staff": [],
            "created_at": now,
            "updated_at": now
        }
        await _db.tickets.insert_one(ticket)
        
        # Уведомление для всех админов о новой заявке
        role_name = "Трейдер" if data.role == "trader" else "Мерчант"
        await _db.admin_notifications.insert_one({
            "id": generate_id("notif_"),
            "type": "new_user_request",
            "title": f"Новая заявка: {role_name}",
            "message": f"{data.nickname} подал заявку на регистрацию как {role_name.lower()}",
            "data": {"user_id": user_id, "role": data.role, "nickname": data.nickname},
            "link": "/admin/users",
            "is_read": False,
            "created_at": now
        })
    
    token = create_jwt_token(user_id, data.role)
    
    return {
        "success": True,
        "token": token,
        "user_id": user_id,
        "role": data.role,
        "approval_status": user["approval_status"],
        "message": "Регистрация успешна" if user["approval_status"] == "approved" else "Ожидайте одобрения администратора"
    }


@router.post("/auth/login")
async def login(data: UserLogin):
    """Авторизация пользователя"""
    import bcrypt
    
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    user = await _db.users.find_one({"login": data.login})
    if not user:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    
    # Проверка пароля
    if not bcrypt.checkpw(data.password.encode('utf-8'), user["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    
    # Проверка активности
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
    
    # Проверка pending статуса
    if user.get("approval_status") == "pending" and user["role"] in ["trader", "merchant"]:
        raise HTTPException(
            status_code=403, 
            detail="Ваша заявка на регистрацию ожидает рассмотрения администратором"
        )
    
    # 2FA проверка
    if user.get("two_factor_enabled"):
        if not data.two_factor_code:
            return {
                "success": False,
                "requires_2fa": True,
                "message": "Введите код двухфакторной аутентификации"
            }
        # TODO: Проверка 2FA кода
    
    # Обновляем last_login
    await _db.users.update_one(
        {"id": user["id"]},
        {"$set": {"last_login_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    token = create_jwt_token(user["id"], user["role"])
    
    return {
        "success": True,
        "token": token,
        "user_id": user["id"],
        "role": user["role"],
        "nickname": user.get("nickname", user["login"]),
        "approval_status": user.get("approval_status", "approved"),
        "two_factor_enabled": user.get("two_factor_enabled", False)
    }


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Получить информацию о текущем пользователе"""
    # Добавляем данные кошелька
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    if wallet:
        user["wallet"] = wallet
    
    # Для трейдера - данные трейдера
    if user["role"] == "trader":
        trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
        if trader:
            user["trader"] = trader
    
    # Для мерчанта - данные мерчанта
    if user["role"] == "merchant":
        merchant = await _db.merchants.find_one({"user_id": user["id"]}, {"_id": 0})
        if merchant:
            user["merchant"] = merchant
    
    return user


@router.post("/auth/link-telegram")
async def link_telegram(data: TelegramLink, user: dict = Depends(get_current_user)):
    """Привязать Telegram аккаунт"""
    await _db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "telegram_id": data.telegram_id,
            "telegram_username": data.telegram_username,
            "telegram_notifications": True
        }}
    )
    return {"success": True, "message": "Telegram привязан"}


@router.get("/auth/2fa/status")
async def get_2fa_status(user: dict = Depends(get_current_user)):
    """Получить статус 2FA"""
    return {
        "enabled": user.get("two_factor_enabled", False),
        "type": user.get("two_factor_type", None)
    }


class Setup2FAData(BaseModel):
    password: str

@router.post("/auth/2fa/setup")
async def setup_2fa(data: Setup2FAData, user: dict = Depends(get_current_user)):
    """Настройка 2FA"""
    import pyotp
    import bcrypt
    
    # Проверяем пароль
    db_user = await _db.users.find_one({"id": user["id"]})
    if not bcrypt.checkpw(data.password.encode('utf-8'), db_user["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=400, detail="Неверный пароль")
    
    # Генерируем секрет
    secret = pyotp.random_base32()
    
    # Сохраняем временно
    await _db.users.update_one(
        {"id": user["id"]},
        {"$set": {"two_factor_temp_secret": secret}}
    )
    
    # Генерируем URI для QR-кода
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.get("login"),
        issuer_name="BITARBITR"
    )
    
    return {
        "secret": secret,
        "qr_uri": provisioning_uri
    }


class Verify2FACode(BaseModel):
    code: str

@router.post("/auth/2fa/verify-setup")
async def verify_2fa_setup(data: Verify2FACode, user: dict = Depends(get_current_user)):
    """Подтверждение настройки 2FA"""
    import pyotp
    
    db_user = await _db.users.find_one({"id": user["id"]})
    
    # Проверяем оба возможных названия поля (для совместимости)
    secret = db_user.get("two_factor_temp_secret") or db_user.get("pending_2fa_secret")
    
    if not secret:
        raise HTTPException(status_code=400, detail="2FA не настроена. Сначала вызовите setup")
    
    totp = pyotp.TOTP(secret)
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Неверный код")
    
    # Активируем 2FA
    await _db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {
                "two_factor_enabled": True,
                "two_factor_secret": secret,
                "two_factor_type": "totp"
            },
            "$unset": {"two_factor_temp_secret": 1, "pending_2fa_secret": 1}
        }
    )
    
    return {"success": True, "message": "2FA включена"}


class Disable2FAData(BaseModel):
    password: str

@router.post("/auth/2fa/disable")
async def disable_2fa(data: Disable2FAData, user: dict = Depends(get_current_user)):
    """Отключение 2FA"""
    import bcrypt
    
    db_user = await _db.users.find_one({"id": user["id"]})
    
    if not bcrypt.checkpw(data.password.encode('utf-8'), db_user["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Неверный пароль")
    
    await _db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {"two_factor_enabled": False},
            "$unset": {"two_factor_secret": 1, "two_factor_type": 1}
        }
    )
    
    return {"success": True, "message": "2FA отключена"}


@router.post("/auth/refresh-token")
async def refresh_token(user: dict = Depends(get_current_user)):
    """Refresh JWT token - extends session by 7 days"""
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Ваш аккаунт заблокирован")
    
    new_token = create_jwt_token(user["id"], user["role"])
    return {"token": new_token, "message": "Token refreshed"}


class VerifyCredentialsRequest(BaseModel):
    password: str
    two_factor_code: Optional[str] = None


@router.post("/auth/verify-credentials")
async def verify_credentials(data: VerifyCredentialsRequest, user: dict = Depends(get_current_user)):
    """Verify user credentials for sensitive operations."""
    import bcrypt
    import pyotp
    import uuid
    
    stored_user = await _db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not stored_user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    
    # Verify password
    if not bcrypt.checkpw(data.password.encode(), stored_user["password_hash"].encode()):
        await _db.security_logs.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "action": "verify_credentials_failed",
            "reason": "invalid_password",
            "ip": "unknown",
            "timestamp": datetime.now(timezone.utc)
        })
        raise HTTPException(status_code=401, detail="Неверный пароль")
    
    # Verify 2FA if enabled
    if stored_user.get("two_factor_enabled"):
        if not data.two_factor_code:
            raise HTTPException(status_code=400, detail="Требуется код 2FA")
        
        secret = stored_user.get("two_factor_secret")
        if secret:
            totp = pyotp.TOTP(secret)
            if not totp.verify(data.two_factor_code, valid_window=1):
                await _db.security_logs.insert_one({
                    "id": str(uuid.uuid4()),
                    "user_id": user["id"],
                    "action": "verify_credentials_failed",
                    "reason": "invalid_2fa",
                    "ip": "unknown",
                    "timestamp": datetime.now(timezone.utc)
                })
                raise HTTPException(status_code=401, detail="Неверный код 2FA")
    
    # Generate short-lived verification token (5 minutes)
    verification_token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    await _db.verification_tokens.insert_one({
        "token": verification_token,
        "user_id": user["id"],
        "expires_at": expiry,
        "used": False
    })
    
    await _db.security_logs.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "action": "credentials_verified",
        "ip": "unknown",
        "timestamp": datetime.now(timezone.utc)
    })
    
    return {
        "success": True,
        "verification_token": verification_token,
        "expires_in": 300
    }


# ================== ACCOUNT ENDPOINTS ==================

@router.get("/account/settings")
async def get_account_settings(user: dict = Depends(get_current_user)):
    """Get account settings"""
    return {
        "id": user["id"],
        "login": user["login"],
        "nickname": user.get("nickname"),
        "role": user["role"],
        "two_factor_enabled": user.get("two_factor_enabled", False),
        "telegram_id": user.get("telegram_id"),
        "created_at": user.get("created_at")
    }


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/account/change-password")
async def change_account_password(data: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Change user password"""
    import bcrypt
    
    # Get user with password hash
    db_user = await _db.users.find_one({"id": user["id"]})
    
    # Verify current password
    if not bcrypt.checkpw(data.current_password.encode('utf-8'), db_user["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не менее 6 символов")
    
    # Hash new password
    new_hash = bcrypt.hashpw(data.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    await _db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": new_hash}}
    )
    
    return {"success": True, "message": "Пароль успешно изменён"}


# ================== USER SETTINGS ENDPOINTS ==================

@router.get("/user/settings")
async def get_user_settings(user: dict = Depends(get_current_user)):
    """Get user settings"""
    return {
        "two_factor_enabled": user.get("two_factor_enabled", False),
        "telegram_id": user.get("telegram_id"),
        "email": user.get("email")
    }


class TelegramConnect(BaseModel):
    telegram_id: str


@router.post("/user/telegram/connect")
async def connect_telegram(data: TelegramConnect, user: dict = Depends(get_current_user)):
    """Connect Telegram"""
    await _db.users.update_one(
        {"id": user["id"]},
        {"$set": {"telegram_id": data.telegram_id}}
    )
    return {"success": True, "message": "Telegram connected"}


@router.post("/user/telegram/disconnect")
async def disconnect_telegram(user: dict = Depends(get_current_user)):
    """Disconnect Telegram"""
    await _db.users.update_one(
        {"id": user["id"]},
        {"$unset": {"telegram_id": ""}}
    )
    return {"success": True, "message": "Telegram disconnected"}


@router.post("/user/telegram/generate-code")
async def generate_telegram_code(user: dict = Depends(get_current_user)):
    """Generate code for Telegram connection"""
    code = secrets.token_hex(4).upper()
    
    await _db.telegram_codes.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "code": code,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        }},
        upsert=True
    )
    
    return {"success": True, "code": code, "expires_in": 600}
