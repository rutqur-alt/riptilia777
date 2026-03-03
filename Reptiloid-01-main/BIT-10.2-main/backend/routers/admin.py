"""
BITARBITR P2P Platform - Admin Router
Administrative functions: user management, statistics, settings
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import logging

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

# These will be imported from main server
db = None
require_role = None
_jwt_secret = None
_jwt_algorithm = "HS256"
_fetch_rate_func = None
_notify_withdrawal_completed = None
_send_telegram_message = None


def init_router(database, role_checker, jwt_secret: str = None, jwt_algorithm: str = "HS256", 
                fetch_rate_func=None, notify_withdrawal_completed_func=None, send_telegram_func=None):
    """Initialize router with database and role checker"""
    global db, require_role, _jwt_secret, _jwt_algorithm, _fetch_rate_func, _notify_withdrawal_completed, _send_telegram_message
    db = database
    require_role = role_checker
    if jwt_secret:
        _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm
    if fetch_rate_func:
        _fetch_rate_func = fetch_rate_func
    _notify_withdrawal_completed = notify_withdrawal_completed_func
    _send_telegram_message = send_telegram_func


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получение текущего пользователя из JWT"""
    from jose import jwt, JWTError
    
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Получаем JWT secret из переменных окружения если не передан
    jwt_secret = _jwt_secret
    if not jwt_secret:
        import os
        jwt_secret = os.environ.get('JWT_SECRET', 'default_secret')
    
    token = credentials.credentials
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=[_jwt_algorithm])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


def require_admin_role(allowed_roles: List[str] = ["admin", "support"]):
    """Проверка роли пользователя"""
    async def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        return user
    return role_checker


# ================== MODELS ==================

class CreateStaffUser(BaseModel):
    """Создание сотрудника (админ/саппорт)"""
    login: str
    nickname: str
    password: str
    role: str  # admin или support
    permissions: Optional[Dict[str, bool]] = None


class ManualDepositRequest(BaseModel):
    """Ручное зачисление депозита"""
    user_id: str
    amount_usdt: float
    comment: Optional[str] = None


# Default permissions
DEFAULT_PERMISSIONS = {
    "admin": {
        "approve_traders": True,
        "block_users": True,
        "delete_users": True,
        "view_orders": True,
        "manage_disputes": True,
        "view_accounting": True,
        "manage_rates": True,
        "create_admins": True,
        "manage_tickets": True
    },
    "support": {
        "approve_traders": True,
        "block_users": True,
        "delete_users": False,
        "view_orders": True,
        "manage_disputes": True,
        "view_accounting": False,
        "manage_rates": False,
        "create_admins": False,
        "manage_tickets": True
    }
}


# ================== HELPER FUNCTIONS ==================

def generate_id(prefix: str) -> str:
    """Generate unique ID with prefix"""
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid4().hex[:6].upper()}"


# ================== ADMIN ENDPOINTS ==================

@router.get("/stats")
async def get_admin_stats(user: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить общую статистику платформы"""
    # Counts
    total_users = await db.users.count_documents({})
    total_traders = await db.users.count_documents({"role": "trader"})
    total_merchants = await db.users.count_documents({"role": "merchant"})
    total_orders = await db.orders.count_documents({})
    
    # Active today
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_iso = today.isoformat()
    
    orders_today = await db.orders.count_documents({
        "created_at": {"$gte": today_iso}
    })
    
    # Completed orders
    completed_orders = await db.orders.count_documents({"status": "completed"})
    
    # Volume (sum of completed orders)
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$group": {"_id": None, "total_rub": {"$sum": "$amount_rub"}, "total_usdt": {"$sum": "$amount_usdt"}}}
    ]
    volume_result = await db.orders.aggregate(pipeline).to_list(1)
    total_volume_rub = volume_result[0]["total_rub"] if volume_result else 0
    total_volume_usdt = volume_result[0]["total_usdt"] if volume_result else 0
    
    # TODAY's completed orders stats
    today_completed = await db.orders.find({
        "status": "completed",
        "completed_at": {"$gte": today_iso}
    }, {"_id": 0}).to_list(10000)
    
    today_deals_count = len(today_completed)
    today_volume_rub = sum(o.get("amount_rub", 0) or 0 for o in today_completed)
    today_volume_usdt = sum(o.get("amount_usdt", 0) or 0 for o in today_completed)
    today_platform_commission = sum(o.get("platform_commission_usdt", 0) or 0 for o in today_completed)
    
    # Pending withdrawals
    pending_withdrawals = await db.usdt_withdrawals.count_documents({"status": "pending"})
    
    # Open disputes
    open_disputes = await db.disputes.count_documents({"status": {"$in": ["open", "under_review"]}})
    
    # Unread tickets
    unread_tickets = await db.tickets.count_documents({"status": "open"})
    
    # Get current exchange rate
    exchange_rate = 0
    try:
        if _fetch_rate_func:
            rate_result = await _fetch_rate_func()
            # Function may return just rate or (rate, source) tuple
            if isinstance(rate_result, tuple):
                exchange_rate = rate_result[0]
            else:
                exchange_rate = rate_result
    except Exception as e:
        logger.warning(f"Failed to fetch exchange rate: {e}")
    
    return {
        "users": {
            "total": total_users,
            "traders": total_traders,
            "merchants": total_merchants
        },
        "orders": {
            "total": total_orders,
            "today": orders_today,
            "completed": completed_orders
        },
        "volume": {
            "total_rub": total_volume_rub,
            "total_usdt": total_volume_usdt
        },
        "today": {
            "deals_count": today_deals_count,
            "volume_rub": today_volume_rub,
            "volume_usdt": today_volume_usdt,
            "platform_commission_usdt": today_platform_commission
        },
        "pending": {
            "withdrawals": pending_withdrawals,
            "disputes": open_disputes,
            "tickets": unread_tickets
        },
        "exchange_rate": exchange_rate
    }


@router.get("/users")
async def get_admin_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    user: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить список пользователей с фильтрацией"""
    query = {}
    
    if role:
        query["role"] = role
    
    if status == "active":
        query["is_active"] = True
    elif status == "blocked":
        query["is_active"] = False
    elif status == "pending":
        query["approval_status"] = "pending"
    
    if search:
        query["$or"] = [
            {"login": {"$regex": search, "$options": "i"}},
            {"nickname": {"$regex": search, "$options": "i"}},
            {"id": {"$regex": search, "$options": "i"}}
        ]
    
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    total = await db.users.count_documents(query)
    
    # Enrich with additional data
    for user_data in users:
        user_id_val = user_data["id"]
        
        # Get wallet balance
        wallet = await db.wallets.find_one({"user_id": user_id_val}, {"_id": 0})
        usdt_wallet = await db.usdt_wallets.find_one({"user_id": user_id_val}, {"_id": 0})
        
        user_data["balance_usdt"] = 0
        if wallet:
            user_data["balance_usdt"] += wallet.get("available_balance_usdt", 0)
            user_data["locked_balance_usdt"] = wallet.get("locked_balance_usdt", 0)
        if usdt_wallet:
            user_data["balance_usdt"] += usdt_wallet.get("balance_usdt", 0)
        
        # Get trader/merchant ID for orders lookup
        trader_id = None
        merchant_id = None
        
        if user_data.get("role") == "trader":
            trader = await db.traders.find_one({"user_id": user_id_val}, {"_id": 0})
            if trader:
                trader_id = trader.get("id")
                user_data["rating"] = trader.get("rating", 5.0)
                user_data["is_available"] = trader.get("is_available", False)
                user_data["total_deals"] = trader.get("total_deals", 0)
                user_data["successful_deals"] = trader.get("successful_deals", 0)
        
        if user_data.get("role") == "merchant":
            merchant = await db.merchants.find_one({"user_id": user_id_val}, {"_id": 0})
            if merchant:
                merchant_id = merchant.get("id")
        
        # Count orders using correct IDs (trader_id or merchant_id, not user_id)
        order_query = {"$or": []}
        if trader_id:
            order_query["$or"].append({"trader_id": trader_id})
        if merchant_id:
            order_query["$or"].append({"merchant_id": merchant_id})
        order_query["$or"].append({"user_id": user_id_val})  # Fallback
        
        if order_query["$or"]:
            orders_count = await db.orders.count_documents(order_query)
            completed_orders = await db.orders.count_documents({
                **order_query,
                "status": "completed"
            })
        else:
            orders_count = 0
            completed_orders = 0
        
        user_data["orders_count"] = orders_count
        user_data["completed_orders"] = completed_orders
        
        # Count disputes
        dispute_query = {"$or": [
            {"user_id": user_id_val},
            {"initiator_id": user_id_val}
        ]}
        if trader_id:
            dispute_query["$or"].append({"trader_id": trader_id})
        if merchant_id:
            dispute_query["$or"].append({"merchant_id": merchant_id})
        
        disputes_count = await db.disputes.count_documents(dispute_query)
        open_disputes = await db.disputes.count_documents({
            **dispute_query,
            "status": {"$in": ["open", "pending", "in_progress"]}
        })
        user_data["disputes_count"] = disputes_count
        user_data["open_disputes"] = open_disputes
    
    return {
        "users": users,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.post("/users/{user_id}/toggle-active")
async def toggle_user_active(user_id: str, admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Заблокировать/разблокировать пользователя"""
    # Check permissions
    if admin["role"] == "support" and not admin.get("permissions", {}).get("block_users"):
        raise HTTPException(status_code=403, detail="Нет прав на блокировку пользователей")
    
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Can't block admins if not full admin
    if target["role"] == "admin" and admin["role"] != "admin":
        raise HTTPException(status_code=403, detail="Нельзя блокировать администратора")
    
    # Support can't block merchants
    if admin["role"] == "support" and target["role"] == "merchant":
        raise HTTPException(status_code=403, detail="Саппорт не может блокировать мерчантов")
    
    new_status = not target.get("is_active", True)
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_active": new_status}}
    )
    
    logger.info(f"User {user_id} {'unblocked' if new_status else 'blocked'} by {admin['id']}")
    
    return {"success": True, "is_active": new_status}


class ResetPasswordData(BaseModel):
    new_password: str


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str, 
    data: ResetPasswordData,
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Сброс пароля пользователя (только для админа)"""
    import bcrypt
    
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Проверяем что пользователь существует
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Нельзя сбросить пароль себе
    if target["id"] == admin["id"]:
        raise HTTPException(status_code=400, detail="Используйте настройки профиля для смены своего пароля")
    
    # Хэшируем новый пароль
    new_password_hash = bcrypt.hashpw(
        data.new_password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')
    
    # Обновляем пароль
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"password_hash": new_password_hash}}
    )
    
    logger.info(f"Password reset for user {user_id} by admin {admin['id']}")
    
    return {"success": True, "message": f"Пароль пользователя {target.get('login', user_id)} успешно сброшен"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Удалить пользователя"""
    # Check permissions
    if admin["role"] == "support" and not admin.get("permissions", {}).get("delete_users"):
        raise HTTPException(status_code=403, detail="Нет прав на удаление пользователей")
    
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Can't delete admins
    if target["role"] == "admin":
        raise HTTPException(status_code=403, detail="Нельзя удалить администратора")
    
    # Support can't delete merchants
    if admin["role"] == "support" and target["role"] == "merchant":
        raise HTTPException(status_code=403, detail="Саппорт не может удалять мерчантов")
    
    # Can't delete yourself
    if target["id"] == admin["id"]:
        raise HTTPException(status_code=400, detail="Нельзя удалить себя")
    
    # Delete related data
    await db.wallets.delete_many({"user_id": user_id})
    await db.usdt_wallets.delete_many({"user_id": user_id})
    await db.traders.delete_many({"user_id": user_id})
    await db.merchants.delete_many({"user_id": user_id})
    await db.payment_details.delete_many({"trader_id": {"$regex": user_id}})
    await db.tickets.delete_many({"user_id": user_id})
    await db.users.delete_one({"id": user_id})
    
    logger.info(f"User {user_id} deleted by {admin['id']}")
    
    return {"success": True, "message": "Пользователь удалён"}


@router.get("/entities")
async def get_deletable_entities(admin: dict = Depends(require_admin_role(["admin"]))):
    """Получить список типов сущностей для универсального удаления"""
    return {
        "entities": [
            {"type": "user", "label": "Пользователи"},
            {"type": "trader", "label": "Трейдеры"},
            {"type": "merchant", "label": "Мерчанты"},
            {"type": "order", "label": "Заказы"},
            {"type": "ticket", "label": "Тикеты"},
            {"type": "dispute", "label": "Споры"},
            {"type": "withdrawal", "label": "Выводы USDT"},
            {"type": "deposit", "label": "Депозиты USDT"},
            {"type": "deposit_request", "label": "Заявки на депозит"},
            {"type": "wallet", "label": "Кошельки"},
            {"type": "payment_detail", "label": "Реквизиты"},
            {"type": "notification", "label": "Уведомления"},
            {"type": "transaction", "label": "Транзакции"},
            {"type": "unidentified_deposit", "label": "Неопознанные депозиты"}
        ]
    }


@router.delete("/universal/{entity_type}/{entity_id}")
async def universal_delete(
    entity_type: str,
    entity_id: str,
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Универсальное удаление любой сущности"""
    entity_collections = {
        "user": "users",
        "trader": "traders",
        "merchant": "merchants",
        "order": "orders",
        "ticket": "tickets",
        "dispute": "disputes",
        "withdrawal": "usdt_withdrawals",
        "deposit": "usdt_deposits",
        "deposit_request": "deposit_requests",
        "wallet": "wallets",
        "usdt_wallet": "usdt_wallets",
        "payment_detail": "payment_details",
        "notification": "admin_notifications",
        "transaction": "transactions",
        "unidentified_deposit": "usdt_unidentified_deposits"
    }
    
    if entity_type not in entity_collections:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестный тип: {entity_type}. Доступные: {', '.join(entity_collections.keys())}"
        )
    
    collection_name = entity_collections[entity_type]
    collection = db[collection_name]
    
    entity = await collection.find_one({"id": entity_id})
    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_type} {entity_id} не найден")
    
    # Special checks
    if entity_type == "user" and entity["id"] == admin["id"]:
        raise HTTPException(status_code=400, detail="Нельзя удалить себя")
    
    result = await collection.delete_one({"id": entity_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=500, detail="Не удалось удалить")
    
    logger.info(f"Universal delete: {entity_type} {entity_id} by {admin['id']}")
    
    return {
        "success": True,
        "message": f"{entity_type} удалён",
        "deleted_id": entity_id,
        "entity_type": entity_type
    }


@router.post("/staff")
async def create_staff_user(data: CreateStaffUser, admin: dict = Depends(require_admin_role(["admin"]))):
    """Создать нового админа или саппорта"""
    import bcrypt
    
    # Check permissions
    if not admin.get("permissions", {}).get("create_admins", admin["role"] == "admin"):
        raise HTTPException(status_code=403, detail="Нет прав на создание администраторов")
    
    if data.role not in ["admin", "support"]:
        raise HTTPException(status_code=400, detail="Роль должна быть admin или support")
    
    # Check if login exists
    existing = await db.users.find_one({"login": data.login})
    if existing:
        raise HTTPException(status_code=400, detail="Логин уже занят")
    
    # Create user
    user_id = generate_id("usr")
    password_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    
    permissions = data.permissions or DEFAULT_PERMISSIONS.get(data.role, {})
    
    user = {
        "id": user_id,
        "login": data.login,
        "nickname": data.nickname,
        "password_hash": password_hash,
        "role": data.role,
        "permissions": permissions,
        "is_active": True,
        "is_verified": True,
        "approval_status": "approved",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": admin["id"]
    }
    
    await db.users.insert_one(user)
    
    logger.info(f"Staff user {user_id} ({data.role}) created by {admin['id']}")
    
    return {
        "success": True,
        "user_id": user_id,
        "message": f"Пользователь {data.nickname} ({data.role}) создан"
    }


@router.get("/staff")
async def get_staff_users(admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить список админов и саппортов"""
    staff = await db.users.find(
        {"role": {"$in": ["admin", "support"]}},
        {"_id": 0, "password_hash": 0}
    ).to_list(100)
    
    return {"staff": staff}


@router.put("/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: str,
    permissions: Dict[str, bool] = Body(...),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Обновить права пользователя (админа/саппорта)"""
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if target["role"] not in ["admin", "support"]:
        raise HTTPException(status_code=400, detail="Права можно менять только админам и саппортам")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"permissions": permissions}}
    )
    
    logger.info(f"Permissions updated for {user_id} by {admin['id']}")
    
    return {"success": True, "message": "Права обновлены"}


@router.get("/traders")
async def get_admin_traders(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить список трейдеров"""
    query = {"role": "trader"}
    
    if status == "pending":
        query["approval_status"] = "pending"
    elif status == "approved":
        query["approval_status"] = "approved"
    elif status == "active":
        query["is_active"] = True
    elif status == "blocked":
        query["is_active"] = False
    
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Build traders list with trader data at top level for frontend compatibility
    traders_list = []
    for user_data in users:
        trader = await db.traders.find_one({"user_id": user_data["id"]}, {"_id": 0})
        if trader:
            # Merge trader data with user_id at top level
            trader_entry = {**trader}
            trader_entry["user"] = user_data
            
            # Get wallet balance
            wallet = await db.wallets.find_one({"user_id": user_data["id"]}, {"_id": 0})
            if wallet:
                trader_entry["balance_usdt"] = wallet.get("available_balance_usdt", 0)
            
            traders_list.append(trader_entry)
        else:
            # If no trader record, create minimal entry
            traders_list.append({
                "id": f"trd_{user_data['id']}",
                "user_id": user_data["id"],
                "user": user_data
            })
    
    return {"traders": traders_list, "total": len(traders_list)}


@router.get("/traders/pending")
async def get_pending_traders(admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить трейдеров ожидающих одобрения"""
    users = await db.users.find(
        {"role": "trader", "approval_status": "pending"},
        {"_id": 0, "password_hash": 0}
    ).to_list(100)
    
    return {"traders": users, "total": len(users)}


@router.get("/orders")
async def get_admin_orders(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить список заказов"""
    query = {}
    if status:
        query["status"] = status
    
    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"orders": orders, "total": len(orders)}


@router.get("/disputes")
async def get_admin_disputes(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить список споров"""
    query = {}
    if status:
        query["status"] = status
    
    disputes = await db.disputes.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"disputes": disputes, "total": len(disputes)}


@router.get("/merchants")
async def get_admin_merchants(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить список мерчантов"""
    query = {"role": "merchant"}
    
    if status == "pending":
        query["approval_status"] = "pending"
    elif status == "approved":
        query["approval_status"] = "approved"
    
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Build merchants list with merchant data at top level
    merchants_list = []
    for user_data in users:
        merchant = await db.merchants.find_one({"user_id": user_data["id"]}, {"_id": 0})
        if merchant:
            # Merge merchant data with user_id at top level for frontend compatibility
            merchant_entry = {**merchant}
            merchant_entry["user"] = user_data
            merchants_list.append(merchant_entry)
        else:
            # If no merchant record, create minimal entry
            merchants_list.append({
                "id": f"mrc_{user_data['id']}",
                "user_id": user_data["id"],
                "user": user_data
            })
    
    return {"merchants": merchants_list, "total": len(merchants_list)}


@router.get("/merchants/pending")
async def get_pending_merchants(admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить мерчантов ожидающих одобрения"""
    users = await db.users.find(
        {"role": "merchant", "approval_status": "pending"},
        {"_id": 0, "password_hash": 0}
    ).to_list(100)
    
    return {"merchants": users, "total": len(users)}


@router.get("/maintenance")
async def get_maintenance_status(admin: dict = Depends(require_admin_role(["admin"]))):
    """Получить статус технического обслуживания"""
    settings = await db.platform_settings.find_one({"key": "maintenance"}, {"_id": 0})
    
    return {
        "enabled": settings.get("enabled", False) if settings else False,
        "message": settings.get("message", "") if settings else ""
    }


@router.post("/maintenance/enable")
async def enable_maintenance(
    message: str = Body("", embed=True),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Включить режим технического обслуживания"""
    await db.platform_settings.update_one(
        {"key": "maintenance"},
        {"$set": {"enabled": True, "message": message}},
        upsert=True
    )
    
    return {"success": True, "message": "Maintenance enabled"}


@router.post("/maintenance/disable")
async def disable_maintenance(admin: dict = Depends(require_admin_role(["admin"]))):
    """Отключить режим технического обслуживания"""
    await db.platform_settings.update_one(
        {"key": "maintenance"},
        {"$set": {"enabled": False}},
        upsert=True
    )
    
    return {"success": True, "message": "Maintenance disabled"}


# ================== MERCHANT FEE SETTINGS ==================

class MerchantFeeSettingsUpdate(BaseModel):
    """Настройки финансовой модели мерчанта"""
    fee_model: str  # "merchant_pays" (Тип 1) или "customer_pays" (Тип 2)
    total_fee_percent: float = 30.0  # Общая накрутка


@router.get("/merchants/{merchant_id}/fee-settings")
async def get_merchant_fee_settings(
    merchant_id: str,
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить настройки финансовой модели мерчанта"""
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    return {
        "fee_model": merchant.get("fee_model", "customer_pays"),
        "total_fee_percent": merchant.get("total_fee_percent", 30.0),
        "merchant_id": merchant_id,
        "company_name": merchant.get("company_name", "")
    }


@router.put("/merchants/{merchant_id}/fee-settings")
async def update_merchant_fee_settings(
    merchant_id: str,
    data: MerchantFeeSettingsUpdate,
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """
    Обновить настройки финансовой модели мерчанта
    
    fee_model:
    - "merchant_pays" (Тип 1): Мерчант платит комиссию, клиент платит original + маркер
    - "customer_pays" (Тип 2): Покупатель платит комиссию, клиент платит original + накрутка + маркер
    """
    merchant = await db.merchants.find_one({"id": merchant_id})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    if data.fee_model not in ["merchant_pays", "customer_pays"]:
        raise HTTPException(status_code=400, detail="fee_model должен быть 'merchant_pays' или 'customer_pays'")
    
    if data.total_fee_percent < 0 or data.total_fee_percent > 100:
        raise HTTPException(status_code=400, detail="total_fee_percent должен быть от 0 до 100")
    
    await db.merchants.update_one(
        {"id": merchant_id},
        {"$set": {
            "fee_model": data.fee_model,
            "total_fee_percent": data.total_fee_percent
        }}
    )
    
    logger.info(f"Merchant {merchant_id} fee settings updated by {admin['id']}: model={data.fee_model}, fee={data.total_fee_percent}%")
    
    return {
        "success": True,
        "fee_model": data.fee_model,
        "total_fee_percent": data.total_fee_percent
    }


# ================== TRADER FEE SETTINGS ==================

class TraderFeeInterval(BaseModel):
    """Интервал комиссии трейдера"""
    min_amount: float
    max_amount: float
    percent: float


class TraderFeeSettingsUpdate(BaseModel):
    """Настройки комиссии трейдера"""
    default_percent: float = 10.0  # Процент по умолчанию
    intervals: Optional[List[TraderFeeInterval]] = None  # Гибкие интервалы (опционально)


@router.get("/traders/{trader_id}/fee-settings")
async def get_trader_fee_settings(
    trader_id: str,
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить настройки комиссии трейдера"""
    trader = await db.traders.find_one({"id": trader_id}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    user = await db.users.find_one({"id": trader.get("user_id")}, {"_id": 0, "password_hash": 0})
    
    return {
        "trader_id": trader_id,
        "trader_name": user.get("nickname") if user else "",
        "default_percent": trader.get("fee_percent", trader.get("default_fee_percent", 10.0)),
        "intervals": trader.get("fee_intervals", [])
    }


@router.put("/traders/{trader_id}/fee-settings")
async def update_trader_fee_settings(
    trader_id: str,
    data: TraderFeeSettingsUpdate,
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """
    Обновить настройки комиссии трейдера
    
    default_percent: Процент комиссии от original суммы (по умолчанию 10%)
    intervals: Опционально - гибкие интервалы комиссии по сумме заказа
    """
    trader = await db.traders.find_one({"id": trader_id})
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    if data.default_percent < 0 or data.default_percent > 50:
        raise HTTPException(status_code=400, detail="default_percent должен быть от 0 до 50")
    
    update_data = {
        "fee_percent": data.default_percent,
        "default_fee_percent": data.default_percent
    }
    
    # Валидация и сохранение интервалов
    if data.intervals:
        for interval in data.intervals:
            if interval.min_amount >= interval.max_amount:
                raise HTTPException(status_code=400, detail="min_amount должен быть меньше max_amount")
            if interval.percent < 0 or interval.percent > 50:
                raise HTTPException(status_code=400, detail="percent в интервалах должен быть от 0 до 50")
        
        update_data["fee_intervals"] = [
            {"min_amount": i.min_amount, "max_amount": i.max_amount, "percent": i.percent}
            for i in data.intervals
        ]
    
    await db.traders.update_one({"id": trader_id}, {"$set": update_data})
    
    logger.info(f"Trader {trader_id} fee settings updated by {admin['id']}: default={data.default_percent}%")
    
    return {
        "success": True,
        "default_percent": data.default_percent,
        "intervals": data.intervals or []
    }


# ================== MERCHANT METHOD COMMISSIONS ==================
# Гибкие комиссии по методам оплаты для Типа 1 (merchant_pays)

class PaymentMethodInterval(BaseModel):
    """Интервал комиссии для метода оплаты"""
    min_amount: float
    max_amount: float
    percent: float


class PaymentMethodCommission(BaseModel):
    """Комиссия для метода оплаты с интервалами"""
    payment_method: str  # card, sbp, sim и т.д.
    intervals: List[PaymentMethodInterval]


class MethodCommissionsUpdate(BaseModel):
    """Обновление комиссий по методам оплаты"""
    methods: List[PaymentMethodCommission]


@router.get("/merchants/{merchant_id}/method-commissions")
async def get_merchant_method_commissions(
    merchant_id: str,
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить гибкие комиссии по методам оплаты для мерчанта (Тип 1)"""
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    return {
        "merchant_id": merchant_id,
        "methods": merchant.get("payment_method_commissions", [])
    }


# ================== MERCHANT & TRADER APPROVAL ==================

@router.post("/merchants/{user_id}/approve")
async def approve_merchant(
    user_id: str,
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Одобрить заявку мерчанта"""
    # Ищем мерчанта по user_id
    merchant = await db.merchants.find_one({"user_id": user_id}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    # Обновляем статус мерчанта
    await db.merchants.update_one(
        {"user_id": user_id},
        {"$set": {
            "approved": True,
            "approval_status": "approved",
            "approved_by": admin["id"],
            "approved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Обновляем роль пользователя
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"role": "merchant", "approval_status": "approved"}}
    )
    
    logger.info(f"Merchant {user_id} approved by admin {admin['id']}")
    
    return {"success": True, "message": "Мерчант одобрен"}


@router.post("/merchants/{user_id}/reject")
async def reject_merchant(
    user_id: str,
    data: dict = Body(default={}),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Отклонить заявку мерчанта"""
    reason = data.get("reason", "Не указана")
    
    merchant = await db.merchants.find_one({"user_id": user_id}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    await db.merchants.update_one(
        {"user_id": user_id},
        {"$set": {
            "approved": False,
            "approval_status": "rejected",
            "rejected_by": admin["id"],
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "rejection_reason": reason
        }}
    )
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"approval_status": "rejected"}}
    )
    
    logger.info(f"Merchant {user_id} rejected by admin {admin['id']}: {reason}")
    
    return {"success": True, "message": "Заявка отклонена"}


@router.post("/traders/{user_id}/approve")
async def approve_trader(
    user_id: str,
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Одобрить заявку трейдера"""
    # Ищем трейдера по user_id
    trader = await db.traders.find_one({"user_id": user_id}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    # Обновляем статус трейдера
    await db.traders.update_one(
        {"user_id": user_id},
        {"$set": {
            "approved": True,
            "approval_status": "approved",
            "approved_by": admin["id"],
            "approved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Обновляем роль пользователя
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"role": "trader", "approval_status": "approved"}}
    )
    
    logger.info(f"Trader {user_id} approved by admin {admin['id']}")
    
    return {"success": True, "message": "Трейдер одобрен"}


@router.post("/traders/{user_id}/reject")
async def reject_trader(
    user_id: str,
    data: dict = Body(default={}),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Отклонить заявку трейдера"""
    reason = data.get("reason", "Не указана")
    
    trader = await db.traders.find_one({"user_id": user_id}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    await db.traders.update_one(
        {"user_id": user_id},
        {"$set": {
            "approved": False,
            "approval_status": "rejected",
            "rejected_by": admin["id"],
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "rejection_reason": reason
        }}
    )
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"approval_status": "rejected"}}
    )
    
    logger.info(f"Trader {user_id} rejected by admin {admin['id']}: {reason}")
    
    return {"success": True, "message": "Заявка отклонена"}


@router.put("/merchants/{merchant_id}/method-commissions")
async def update_merchant_method_commissions(
    merchant_id: str,
    data: MethodCommissionsUpdate,
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """
    Обновить гибкие комиссии по методам оплаты для мерчанта
    
    Используется для fee_model = "merchant_pays" (Тип 1)
    Позволяет задать разные комиссии для card, sbp, sim и т.д.
    с интервалами по сумме заказа.
    
    Пример:
    {
        "methods": [
            {
                "payment_method": "card",
                "intervals": [
                    {"min_amount": 100, "max_amount": 999, "percent": 15},
                    {"min_amount": 1000, "max_amount": 5999, "percent": 14.5},
                    {"min_amount": 6000, "max_amount": 10999, "percent": 14}
                ]
            },
            {
                "payment_method": "sbp",
                "intervals": [
                    {"min_amount": 100, "max_amount": 5000, "percent": 12},
                    {"min_amount": 5001, "max_amount": 50000, "percent": 10}
                ]
            }
        ]
    }
    """
    merchant = await db.merchants.find_one({"id": merchant_id})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    # Валидация методов оплаты
    valid_payment_methods = ['card', 'sbp', 'sim', 'mono_bank', 'sng_sbp', 'sng_card', 'qr_code']
    
    methods_data = []
    for method in data.methods:
        if method.payment_method not in valid_payment_methods:
            raise HTTPException(
                status_code=400, 
                detail=f"Неизвестный метод оплаты: {method.payment_method}. Доступны: {', '.join(valid_payment_methods)}"
            )
        
        # Валидация интервалов
        for interval in method.intervals:
            if interval.min_amount >= interval.max_amount:
                raise HTTPException(
                    status_code=400, 
                    detail=f"min_amount должен быть меньше max_amount для метода {method.payment_method}"
                )
            if interval.percent < 0 or interval.percent > 100:
                raise HTTPException(
                    status_code=400, 
                    detail=f"percent должен быть от 0 до 100 для метода {method.payment_method}"
                )
        
        methods_data.append({
            "payment_method": method.payment_method,
            "intervals": [
                {"min_amount": i.min_amount, "max_amount": i.max_amount, "percent": i.percent}
                for i in method.intervals
            ]
        })
    
    await db.merchants.update_one(
        {"id": merchant_id},
        {"$set": {"payment_method_commissions": methods_data}}
    )
    
    logger.info(f"Merchant {merchant_id} method commissions updated by {admin['id']}: {len(methods_data)} methods")
    
    return {
        "success": True,
        "methods": methods_data
    }



@router.get("/analytics")
async def get_admin_analytics(
    period: str = "week",
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить аналитику платформы за период"""
    now = datetime.now(timezone.utc)
    
    if period == "week":
        days = 7
    elif period == "month":
        days = 30
    elif period == "year":
        days = 365
    else:
        days = 7
    
    start_date = (now - timedelta(days=days)).isoformat()
    
    # Получаем заказы за период
    orders = await db.orders.find({
        "created_at": {"$gte": start_date}
    }, {"_id": 0}).to_list(100000)
    
    # Фильтруем по статусу
    completed_orders = [o for o in orders if o.get("status") == "completed"]
    disputed_orders = [o for o in orders if o.get("status") == "disputed"]
    cancelled_orders = [o for o in orders if o.get("status") in ["cancelled", "expired"]]
    
    # Считаем статистику
    total_volume_rub = sum(o.get("amount_rub", 0) or 0 for o in completed_orders)
    platform_commission = sum(o.get("platform_commission_usdt", 0) or 0 for o in completed_orders)
    traders_commission = sum(o.get("trader_commission_usdt", 0) or 0 for o in completed_orders)
    
    # Данные по дням
    daily_data = {}
    for o in completed_orders:
        date = o.get("completed_at", o.get("created_at", ""))[:10]
        if date:
            if date not in daily_data:
                daily_data[date] = {"volume_rub": 0, "platform_usdt": 0, "count": 0}
            daily_data[date]["volume_rub"] += o.get("amount_rub", 0) or 0
            daily_data[date]["platform_usdt"] += o.get("platform_commission_usdt", 0) or 0
            daily_data[date]["count"] += 1
    
    daily_stats = [
        {"date": d, "volume_rub": v["volume_rub"], "platform_usdt": v["platform_usdt"], "count": v["count"]}
        for d, v in sorted(daily_data.items())
    ]
    
    # По мерчантам
    merchant_stats = {}
    for o in completed_orders:
        m_id = o.get("merchant_id", "unknown")
        if m_id not in merchant_stats:
            merchant_stats[m_id] = {"count": 0, "volume_rub": 0}
        merchant_stats[m_id]["count"] += 1
        merchant_stats[m_id]["volume_rub"] += o.get("amount_rub", 0) or 0
    
    # По методам оплаты
    payment_methods = {}
    for o in completed_orders:
        method = o.get("payment_method", "unknown")
        if method not in payment_methods:
            payment_methods[method] = {"count": 0, "volume_rub": 0}
        payment_methods[method]["count"] += 1
        payment_methods[method]["volume_rub"] += o.get("amount_rub", 0) or 0
    
    return {
        "volume": {
            "total_rub": total_volume_rub
        },
        "orders": {
            "total": len(orders),
            "completed": len(completed_orders),
            "disputed": len(disputed_orders),
            "cancelled": len(cancelled_orders)
        },
        "commission": {
            "platform_usdt": platform_commission,
            "traders_usdt": traders_commission,
            "total_usdt": platform_commission + traders_commission
        },
        "daily_stats": daily_stats,
        "merchant_stats": merchant_stats,
        "payment_methods": payment_methods,
        "period": period
    }



@router.get("/accounting")
async def get_admin_accounting(admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить бухгалтерскую статистику платформы"""
    now = datetime.now(timezone.utc)
    
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_start = (now - timedelta(days=7)).isoformat()
    month_start = (now - timedelta(days=30)).isoformat()
    
    # Все завершённые заказы
    all_completed = await db.orders.find(
        {"status": "completed"},
        {"_id": 0}
    ).to_list(100000)
    
    # Заказы за периоды
    today_completed = [o for o in all_completed if o.get("completed_at", "") >= today_start]
    week_completed = [o for o in all_completed if o.get("completed_at", "") >= week_start]
    month_completed = [o for o in all_completed if o.get("completed_at", "") >= month_start]
    
    # Подсчёт комиссий
    def calc_stats(orders):
        volume_rub = sum(o.get("amount_rub", 0) or 0 for o in orders)
        platform_usdt = sum(o.get("platform_commission_usdt", 0) or 0 for o in orders)
        traders_usdt = sum(o.get("trader_commission_usdt", 0) or 0 for o in orders)
        merchant_usdt = sum(o.get("merchant_amount_usdt", 0) or 0 for o in orders)
        return {
            "orders_count": len(orders),
            "volume_rub": volume_rub,
            "volume_usdt": merchant_usdt + platform_usdt + traders_usdt,
            "platform_commission_usdt": platform_usdt,
            "traders_commission_usdt": traders_usdt,
            "total_commission_usdt": platform_usdt + traders_usdt
        }
    
    # Подсчёт балансов всех кошельков
    wallets = await db.wallets.find({}, {"_id": 0}).to_list(10000)
    total_available_usdt = sum(w.get("available_balance_usdt", 0) or 0 for w in wallets)
    total_locked_usdt = sum(w.get("locked_balance_usdt", 0) or 0 for w in wallets)
    
    # Кошельки мерчантов vs трейдеров
    users = await db.users.find({}, {"_id": 0, "id": 1, "role": 1}).to_list(10000)
    user_roles = {u["id"]: u.get("role", "") for u in users}
    
    merchants_balance = sum(
        w.get("available_balance_usdt", 0) or 0 
        for w in wallets 
        if user_roles.get(w.get("user_id"), "") == "merchant"
    )
    traders_balance = sum(
        w.get("available_balance_usdt", 0) or 0 
        for w in wallets 
        if user_roles.get(w.get("user_id"), "") == "trader"
    )
    
    # Итоговая статистика для summary
    all_stats = calc_stats(all_completed)
    
    return {
        "summary": {
            "total_orders": all_stats["orders_count"],
            "total_volume_rub": all_stats["volume_rub"],
            "total_volume_usdt": all_stats["volume_usdt"],
            "platform_commission_usdt": all_stats["platform_commission_usdt"],
            "trader_commission_usdt": all_stats["traders_commission_usdt"]
        },
        "today": calc_stats(today_completed),
        "week": calc_stats(week_completed),
        "month": calc_stats(month_completed),
        "all_time": all_stats,
        "balances": {
            "total_available_usdt": total_available_usdt,
            "total_locked_usdt": total_locked_usdt,
            "merchants_usdt": merchants_balance,
            "traders_usdt": traders_balance
        }
    }



# ================== REFERRAL SETTINGS ==================

@router.get("/referral/settings")
async def get_referral_settings(admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить настройки реферальной программы"""
    settings = await db.platform_settings.find_one({"key": "referral"})
    
    if not settings:
        # Дефолтные настройки
        default_settings = {
            "key": "referral",
            "enabled": True,
            "levels": [
                {"level": 1, "percent": 5},
                {"level": 2, "percent": 3},
                {"level": 3, "percent": 1}
            ],
            "min_withdrawal_usdt": 1,
            "description": "Приглашайте друзей и получайте процент с их комиссий"
        }
        await db.platform_settings.insert_one(default_settings)
        settings = default_settings
    
    # Возвращаем в формате который ожидает фронтенд
    levels = settings.get("levels", [])
    return {
        "enabled": settings.get("enabled", True),
        "level1_percent": levels[0]["percent"] if len(levels) > 0 else 5,
        "level2_percent": levels[1]["percent"] if len(levels) > 1 else 3,
        "level3_percent": levels[2]["percent"] if len(levels) > 2 else 1,
        "min_withdrawal_usdt": settings.get("min_withdrawal_usdt", settings.get("min_withdrawal", 100) / 77),  # Конвертация из старого формата
        "description": settings.get("description", "")
    }


@router.put("/referral/settings")
async def update_referral_settings(
    data: dict = Body(...),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Обновить настройки реферальной программы"""
    levels = [
        {"level": 1, "percent": data.get("level1_percent", 5)},
        {"level": 2, "percent": data.get("level2_percent", 3)},
        {"level": 3, "percent": data.get("level3_percent", 1)}
    ]
    
    await db.platform_settings.update_one(
        {"key": "referral"},
        {"$set": {
            "enabled": data.get("enabled", True),
            "levels": levels,
            "min_withdrawal_usdt": data.get("min_withdrawal_usdt", 1)
        }},
        upsert=True
    )
    
    return {"success": True, "message": "Настройки реферальной программы обновлены"}


# ================== USDT WITHDRAWAL MANAGEMENT ==================

@router.get("/usdt/withdrawals")
async def get_usdt_withdrawals(
    status: Optional[str] = None,
    limit: int = Query(100, le=500),
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить список заявок на вывод USDT для админа"""
    query = {}
    if status and status != "all":
        query["status"] = status
    
    withdrawals = await db.usdt_withdrawals.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Enrich with user data
    result = []
    for w in withdrawals:
        user = await db.users.find_one({"id": w.get("user_id")}, {"_id": 0, "password_hash": 0})
        wallet = await db.wallets.find_one({"user_id": w.get("user_id")}, {"_id": 0})
        
        result.append({
            **w,
            "username": user.get("nickname") if user else w.get("user_id"),
            "user_login": user.get("login") if user else None,
            "user_role": user.get("role") if user else None,
            "user_trusted": user.get("is_trusted", False) if user else False,
            "to_address": w.get("address") or w.get("to_address") or w.get("ton_address"),
            "user_balance": wallet.get("available_balance_usdt", 0) if wallet else 0
        })
    
    return {"withdrawals": result, "total": len(result)}


@router.post("/usdt/withdrawal/{withdrawal_id}/process")
async def process_withdrawal(
    withdrawal_id: str,
    tx_hash: Optional[str] = Query(None),
    skip_send: bool = Query(False, description="Пропустить отправку (только пометить как выполненный)"),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Одобрить и обработать вывод USDT - отправить реальные средства"""
    from server import send_usdt_withdrawal, get_hot_wallet_balance
    
    withdrawal = await db.usdt_withdrawals.find_one({"id": withdrawal_id}, {"_id": 0})
    
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    if withdrawal["status"] != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже обработана")
    
    amount_usdt = withdrawal["amount_usdt"]
    to_address = withdrawal.get("address") or withdrawal.get("to_address") or withdrawal.get("ton_address")
    
    if not to_address:
        raise HTTPException(status_code=400, detail="Адрес получателя не указан")
    
    # Check hot wallet balance first
    hot_balance = await get_hot_wallet_balance()
    
    if hot_balance < amount_usdt and not skip_send:
        raise HTTPException(
            status_code=400, 
            detail=f"Недостаточно средств на горячем кошельке. Баланс: {hot_balance:.2f} USDT, требуется: {amount_usdt:.2f} USDT. Средства разблокированы для пользователя.",
            headers={"X-Hot-Balance": str(hot_balance), "X-Required": str(amount_usdt)}
        )
    
    # If skip_send=True or we have tx_hash, just mark as completed
    if skip_send or tx_hash:
        final_tx_hash = tx_hash or f"manual_{generate_id('tx')}"
    else:
        # Send real USDT
        result = await send_usdt_withdrawal(to_address, amount_usdt, withdrawal_id)
        
        if not result.get("success"):
            error_msg = result.get("error", "Неизвестная ошибка")
            
            # If insufficient balance, return funds to user
            if "Недостаточно средств" in error_msg:
                # Return funds from pending_withdrawal back to available
                await db.wallets.update_one(
                    {"user_id": withdrawal["user_id"]},
                    {"$inc": {
                        "pending_withdrawal_usdt": -amount_usdt,
                        "available_balance_usdt": amount_usdt
                    }}
                )
                
                # Mark withdrawal as failed
                await db.usdt_withdrawals.update_one(
                    {"id": withdrawal_id},
                    {"$set": {
                        "status": "failed",
                        "error": error_msg,
                        "failed_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                raise HTTPException(
                    status_code=400,
                    detail=f"{error_msg}. Средства возвращены на баланс пользователя."
                )
            
            raise HTTPException(status_code=500, detail=f"Ошибка отправки: {error_msg}")
        
        final_tx_hash = result.get("tx_hash")
    
    # Update withdrawal status
    update_data = {
        "status": "completed",
        "processed_by": admin["id"],
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "tx_hash": final_tx_hash
    }
    
    await db.usdt_withdrawals.update_one(
        {"id": withdrawal_id},
        {"$set": update_data}
    )
    
    # Update user wallet - move from pending_withdrawal to withdrawn
    await db.wallets.update_one(
        {"user_id": withdrawal["user_id"]},
        {"$inc": {
            "pending_withdrawal_usdt": -amount_usdt,
            "total_withdrawn_usdt": amount_usdt
        }}
    )
    
    logger.info(f"Withdrawal {withdrawal_id} processed by admin {admin['id']}, amount: {amount_usdt} USDT, tx: {final_tx_hash}")
    
    # Уведомляем пользователя о завершении вывода
    if _notify_withdrawal_completed:
        import asyncio
        asyncio.create_task(_notify_withdrawal_completed(withdrawal["user_id"], {
            "amount": amount_usdt,
            "address": to_address,
            "tx_hash": final_tx_hash
        }))
    
    return {
        "success": True,
        "withdrawal_id": withdrawal_id,
        "tx_hash": final_tx_hash,
        "amount_usdt": amount_usdt,
        "to_address": to_address,
        "message": "Вывод успешно обработан"
    }


@router.post("/usdt/withdrawal/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: str,
    reason: Optional[str] = Query(None),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Отклонить заявку на вывод USDT"""
    withdrawal = await db.usdt_withdrawals.find_one({"id": withdrawal_id}, {"_id": 0})
    
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    if withdrawal["status"] != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже обработана")
    
    # Update withdrawal status
    await db.usdt_withdrawals.update_one(
        {"id": withdrawal_id},
        {"$set": {
            "status": "rejected",
            "rejected_by": admin["id"],
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "reject_reason": reason or "Отклонено администратором"
        }}
    )
    
    # Return funds from pending_withdrawal back to available
    await db.wallets.update_one(
        {"user_id": withdrawal["user_id"]},
        {"$inc": {
            "pending_withdrawal_usdt": -withdrawal["amount_usdt"],
            "available_balance_usdt": withdrawal["amount_usdt"]
        }}
    )
    
    logger.info(f"Withdrawal {withdrawal_id} rejected by admin {admin['id']}, amount: {withdrawal['amount_usdt']} USDT")
    
    return {
        "success": True,
        "withdrawal_id": withdrawal_id,
        "message": "Заявка отклонена, средства возвращены на баланс"
    }


@router.get("/usdt/deposit-requests")
async def get_deposit_requests(
    status: Optional[str] = None,
    limit: int = Query(100, le=500),
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить список заявок на депозит"""
    query = {}
    if status and status != "all":
        query["status"] = status
    
    requests = await db.deposit_requests.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Enrich with user data
    result = []
    for r in requests:
        user = await db.users.find_one({"id": r.get("user_id")}, {"_id": 0, "password_hash": 0})
        result.append({
            **r,
            "user_nickname": user.get("nickname") if user else None,
            "user_login": user.get("login") if user else None
        })
    
    return {"requests": result, "total": len(result)}


@router.post("/usdt/manual-deposit")
async def manual_deposit(
    user_id: str = Query(...),
    amount_usdt: float = Query(...),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Ручное зачисление USDT пользователю"""
    if amount_usdt <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")
    
    # Check user exists
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Update wallet
    result = await db.wallets.update_one(
        {"user_id": user_id},
        {"$inc": {
            "available_balance_usdt": amount_usdt,
            "total_deposited_usdt": amount_usdt
        }}
    )
    
    if result.modified_count == 0:
        # Create wallet if not exists
        await db.wallets.insert_one({
            "id": f"wal_{user_id}",
            "user_id": user_id,
            "available_balance_usdt": amount_usdt,
            "locked_balance_usdt": 0,
            "total_deposited_usdt": amount_usdt,
            "total_withdrawn_usdt": 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Create deposit record
    deposit = {
        "id": generate_id("dep_"),
        "user_id": user_id,
        "amount_usdt": amount_usdt,
        "type": "manual",
        "created_by": admin["id"],
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.usdt_deposits.insert_one(deposit)
    
    logger.info(f"Manual deposit by admin {admin['id']}: {amount_usdt} USDT to user {user_id}")
    
    return {
        "success": True,
        "deposit_id": deposit["id"],
        "message": f"Зачислено {amount_usdt} USDT пользователю {user.get('nickname', user_id)}"
    }


@router.get("/usdt/unidentified-deposits")
async def get_unidentified_deposits(admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить неопознанные депозиты"""
    deposits = await db.usdt_unidentified_deposits.find({}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return {"deposits": deposits}


@router.post("/usdt/unidentified-deposit/{deposit_id}/assign")
async def assign_unidentified_deposit(
    deposit_id: str,
    user_id: str = Query(...),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Привязать неопознанный депозит к пользователю"""
    deposit = await db.usdt_unidentified_deposits.find_one({"id": deposit_id})
    if not deposit:
        raise HTTPException(status_code=404, detail="Депозит не найден")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    amount = deposit.get("amount_usdt", 0)
    
    # Credit to user wallet
    await db.wallets.update_one(
        {"user_id": user_id},
        {"$inc": {
            "available_balance_usdt": amount,
            "total_deposited_usdt": amount
        }}
    )
    
    # Update deposit status
    await db.usdt_unidentified_deposits.update_one(
        {"id": deposit_id},
        {"$set": {
            "status": "assigned",
            "assigned_to": user_id,
            "assigned_by": admin["id"],
            "assigned_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    logger.info(f"Unidentified deposit {deposit_id} assigned to {user_id} by admin {admin['id']}")
    
    return {"success": True, "message": f"Депозит {amount} USDT привязан к {user.get('nickname', user_id)}"}


@router.get("/usdt/unidentified-withdrawals")
async def get_unidentified_withdrawals(admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить неопознанные выводы"""
    withdrawals = await db.usdt_unidentified_withdrawals.find({}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return {"withdrawals": withdrawals}


@router.get("/usdt/settings")
async def get_usdt_settings(admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить настройки USDT системы"""
    settings = await db.platform_settings.find_one({"type": "usdt_ton"}, {"_id": 0})
    if not settings:
        settings = {
            "platform_ton_address": "",
            "withdrawal_fee_percent": 0,
            "network_fee": 0,
            "min_deposit": 0,
            "min_withdrawal": 0
        }
    return {"settings": settings}


@router.put("/usdt/settings")
async def update_usdt_settings(
    settings: dict = Body(...),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Обновить настройки USDT системы"""
    await db.platform_settings.update_one(
        {"type": "usdt_ton"},
        {"$set": settings},
        upsert=True
    )
    return {"success": True, "message": "Настройки обновлены"}


# ================== USER TRUSTED STATUS ==================

@router.post("/users/{user_id}/toggle-trusted")
async def toggle_user_trusted(
    user_id: str,
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Переключить статус доверия пользователя"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    new_status = not user.get("is_trusted", False)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_trusted": new_status, "withdrawal_auto_approve": new_status}}
    )
    
    logger.info(f"User {user_id} trusted status changed to {new_status} by {admin['id']}")
    
    return {"success": True, "is_trusted": new_status}


@router.put("/users/{user_id}/trust")
async def set_user_trust(
    user_id: str,
    trusted: bool = Query(...),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Установить статус доверия пользователя"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_trusted": trusted, "withdrawal_auto_approve": trusted}}
    )
    
    logger.info(f"User {user_id} trust set to {trusted} by {admin['id']}")
    
    return {"success": True, "is_trusted": trusted, "withdrawal_auto_approve": trusted}


@router.get("/users/{user_id}/stats")
async def get_user_stats(
    user_id: str,
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """Получить статистику пользователя"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Wallet
    wallet = await db.wallets.find_one({"user_id": user_id}, {"_id": 0})
    
    # Get trader/merchant ID for correct lookups
    trader_id = None
    merchant_id = None
    trader_data = None
    
    if user.get("role") == "trader":
        trader = await db.traders.find_one({"user_id": user_id}, {"_id": 0})
        if trader:
            trader_id = trader.get("id")
            trader_data = trader
    
    if user.get("role") == "merchant":
        merchant = await db.merchants.find_one({"user_id": user_id}, {"_id": 0})
        if merchant:
            merchant_id = merchant.get("id")
    
    # Build order query with correct IDs
    order_conditions = [{"user_id": user_id}]
    if trader_id:
        order_conditions.append({"trader_id": trader_id})
    if merchant_id:
        order_conditions.append({"merchant_id": merchant_id})
    
    order_query = {"$or": order_conditions}
    
    # Orders count
    orders_count = await db.orders.count_documents(order_query)
    completed_orders = await db.orders.count_documents({
        **order_query,
        "status": "completed"
    })
    
    # Volume
    pipeline = [
        {"$match": {
            **order_query,
            "status": "completed"
        }},
        {"$group": {
            "_id": None, 
            "total_rub": {"$sum": {"$ifNull": ["$amount_rub", 0]}}, 
            "total_usdt": {"$sum": {"$ifNull": ["$amount_usdt", 0]}}
        }}
    ]
    volume_result = await db.orders.aggregate(pipeline).to_list(1)
    
    # Disputes query with correct IDs
    dispute_conditions = [{"user_id": user_id}, {"initiator_id": user_id}]
    if trader_id:
        dispute_conditions.append({"trader_id": trader_id})
    if merchant_id:
        dispute_conditions.append({"merchant_id": merchant_id})
    
    dispute_query = {"$or": dispute_conditions}
    
    disputes = await db.disputes.count_documents(dispute_query)
    open_disputes = await db.disputes.count_documents({
        **dispute_query,
        "status": {"$in": ["open", "pending", "in_progress"]}
    })
    resolved_disputes = await db.disputes.count_documents({
        **dispute_query,
        "status": {"$in": ["resolved", "closed"]}
    })
    
    # Withdrawals
    total_withdrawn = await db.usdt_withdrawals.aggregate([
        {"$match": {"user_id": user_id, "status": "completed"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount_usdt"}}}
    ]).to_list(1)
    
    # Deposits
    total_deposited = await db.usdt_deposits.aggregate([
        {"$match": {"user_id": user_id, "status": {"$in": ["completed", "credited"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount_usdt"}}}
    ]).to_list(1)
    
    # Format response for frontend compatibility
    response = {
        "user": user,
        "wallet": wallet,
        # Flat fields for frontend
        "balance_usdt": wallet.get("available_balance_usdt", 0) if wallet else 0,
        "locked_balance_usdt": wallet.get("locked_balance_usdt", 0) if wallet else 0,
        "total_orders": orders_count,
        "completed_orders": completed_orders,
        "volume_rub": volume_result[0]["total_rub"] if volume_result else 0,
        "volume_usdt": volume_result[0]["total_usdt"] if volume_result else 0,
        "total_disputes": disputes,
        "open_disputes": open_disputes,
        "resolved_disputes": resolved_disputes,
        # Original nested format
        "orders": {
            "total": orders_count,
            "completed": completed_orders
        },
        "volume": {
            "total_rub": volume_result[0]["total_rub"] if volume_result else 0,
            "total_usdt": volume_result[0]["total_usdt"] if volume_result else 0
        },
        "total_withdrawn_usdt": total_withdrawn[0]["total"] if total_withdrawn else 0,
        "total_deposited_usdt": total_deposited[0]["total"] if total_deposited else 0
    }
    
    # Add trader-specific data
    if trader_data:
        response["trader_total_deals"] = trader_data.get("total_deals", 0)
        response["trader_successful_deals"] = trader_data.get("successful_deals", 0)
        response["trader_rating"] = trader_data.get("rating", 5.0)
    
    return response


# ================== AUTO-WITHDRAW ENDPOINTS ==================

class AutoWithdrawSetup(BaseModel):
    """Настройка автовывода USDT"""
    wallet_address: str
    seed_phrase: str
    usdt_contract: str
    toncenter_api_key: str
    encryption_password: str
    max_auto_withdraw: float = 50.0
    min_balance_stop: float = 20.0


@router.get("/auto-withdraw/status")
async def get_auto_withdraw_status(admin: dict = Depends(require_admin_role(["admin"]))):
    """Получить статус автовывода с реальным балансом кошелька"""
    from server import get_hot_wallet_balance
    
    config = await db.platform_settings.find_one({"type": "auto_withdraw"}, {"_id": 0})
    full_config = await db.auto_withdraw_config.find_one({"active": True}, {"_id": 0})
    
    # Count pending withdrawals
    pending_count = await db.usdt_withdrawals.count_documents({"status": "pending"})
    
    # Calculate pending amount
    pending_amount_result = await db.usdt_withdrawals.aggregate([
        {"$match": {"status": "pending"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount_usdt"}}}
    ]).to_list(1)
    pending_amount = pending_amount_result[0]["total"] if pending_amount_result else 0
    
    # Get real hot wallet balance
    hot_balance = await get_hot_wallet_balance()
    
    # Get total withdrawn
    total_withdrawn_result = await db.usdt_withdrawals.aggregate([
        {"$match": {"status": "completed"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount_usdt"}}}
    ]).to_list(1)
    total_withdrawn = total_withdrawn_result[0]["total"] if total_withdrawn_result else 0
    
    wallet_address = None
    is_running = False
    
    if full_config:
        wallet_address = full_config.get("wallet_address")
        is_running = full_config.get("is_running", False)
    elif config:
        wallet_address = config.get("wallet_address")
        is_running = config.get("is_running", False)
    
    return {
        "is_running": is_running,
        "wallet_address": wallet_address,
        "balance": hot_balance,
        "pending_withdrawals": pending_count,
        "pending_amount": pending_amount,
        "total_withdrawn": total_withdrawn,
        "can_process_all": hot_balance >= pending_amount,
        "last_transaction": config.get("last_transaction") if config else None,
        "last_transaction_time": config.get("last_transaction_time") if config else None
    }


@router.get("/auto-withdraw/balance")
async def get_hot_wallet_balance_endpoint(admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить текущий баланс горячего кошелька"""
    from server import get_hot_wallet_balance
    
    balance = await get_hot_wallet_balance()
    config = await db.auto_withdraw_config.find_one({"active": True}, {"_id": 0})
    
    return {
        "balance_usdt": balance,
        "wallet_address": config.get("wallet_address") if config else None
    }


@router.get("/auto-withdraw/config")
async def get_auto_withdraw_config(admin: dict = Depends(require_admin_role(["admin"]))):
    """Получить конфигурацию автовывода"""
    config = await db.platform_settings.find_one({"type": "auto_withdraw"}, {"_id": 0})
    
    if not config:
        return {
            "configured": False,
            "wallet_address": None,
            "usdt_contract": "EQDcBkGHmC4pTf34x3Gm05XvepO5w60DNxZ-XT4I6-UGG5L5"
        }
    
    return {
        "configured": True,
        "wallet_address": config.get("wallet_address"),
        "usdt_contract": config.get("usdt_contract", "EQDcBkGHmC4pTf34x3Gm05XvepO5w60DNxZ-XT4I6-UGG5L5"),
        "max_auto_withdraw": config.get("max_auto_withdraw", 50.0),
        "min_balance_stop": config.get("min_balance_stop", 20.0)
    }


@router.post("/auto-withdraw/setup")
async def setup_auto_withdraw(
    data: AutoWithdrawSetup,
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Настроить автовывод USDT"""
    # Store public config in platform_settings
    config = {
        "type": "auto_withdraw",
        "wallet_address": data.wallet_address,
        "usdt_contract": data.usdt_contract,
        "max_auto_withdraw": data.max_auto_withdraw,
        "min_balance_stop": data.min_balance_stop,
        "is_running": False,
        "configured": True,
        "configured_at": datetime.now(timezone.utc).isoformat(),
        "configured_by": admin["id"]
    }
    
    await db.platform_settings.update_one(
        {"type": "auto_withdraw"},
        {"$set": config},
        upsert=True
    )
    
    # Store sensitive config (with seed phrase) in separate collection
    # In production, seed_phrase should be encrypted
    sensitive_config = {
        "wallet_address": data.wallet_address,
        "seed_phrase": data.seed_phrase,  # TODO: Encrypt in production!
        "usdt_contract": data.usdt_contract,
        "toncenter_api_key": data.toncenter_api_key,
        "encryption_password": data.encryption_password,
        "max_auto_withdraw": data.max_auto_withdraw,
        "min_balance_stop": data.min_balance_stop,
        "active": True,
        "is_running": False,
        "configured_at": datetime.now(timezone.utc).isoformat(),
        "configured_by": admin["id"]
    }
    
    # Deactivate old configs
    await db.auto_withdraw_config.update_many({}, {"$set": {"active": False}})
    
    # Insert new config
    await db.auto_withdraw_config.insert_one(sensitive_config)
    
    logger.info(f"Auto-withdraw configured by admin {admin['id']} for wallet {data.wallet_address[:20]}...")
    
    return {"success": True, "message": "Автовывод настроен", "wallet_address": data.wallet_address}


@router.post("/auto-withdraw/start")
async def start_auto_withdraw(admin: dict = Depends(require_admin_role(["admin"]))):
    """Запустить автовывод"""
    config = await db.auto_withdraw_config.find_one({"active": True})
    
    if not config:
        raise HTTPException(status_code=400, detail="Автовывод не настроен")
    
    await db.auto_withdraw_config.update_one(
        {"active": True},
        {"$set": {"is_running": True, "started_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    await db.platform_settings.update_one(
        {"type": "auto_withdraw"},
        {"$set": {"is_running": True, "started_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    logger.info(f"Auto-withdraw started by admin {admin['id']}")
    
    return {"success": True, "message": "Автовывод запущен"}


@router.post("/auto-withdraw/stop")
async def stop_auto_withdraw(admin: dict = Depends(require_admin_role(["admin"]))):
    """Остановить автовывод"""
    await db.auto_withdraw_config.update_one(
        {"active": True},
        {"$set": {"is_running": False, "stopped_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    await db.platform_settings.update_one(
        {"type": "auto_withdraw"},
        {"$set": {"is_running": False, "stopped_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    logger.info(f"Auto-withdraw stopped by admin {admin['id']}")
    
    return {"success": True, "message": "Автовывод остановлен"}


@router.post("/auto-withdraw/test")
async def test_auto_withdraw(
    to_address: str = Body(..., embed=True),
    amount: float = Body(0.001, embed=True),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Тестовый вывод USDT - отправляет реальную транзакцию"""
    if amount > 1.0:
        raise HTTPException(status_code=400, detail="Максимальная тестовая сумма 1 USDT")
    
    from server import send_usdt_withdrawal, get_hot_wallet_balance
    
    # Check balance first
    balance = await get_hot_wallet_balance()
    if balance < amount:
        raise HTTPException(
            status_code=400, 
            detail=f"Недостаточно средств на горячем кошельке. Баланс: {balance:.4f} USDT"
        )
    
    # Send real test transaction
    result = await send_usdt_withdrawal(to_address, amount, f"test_{generate_id('')}")
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Ошибка отправки"))
    
    logger.info(f"Test withdrawal of {amount} USDT to {to_address} by admin {admin['id']}, tx: {result.get('tx_hash')}")
    
    return {
        "success": True,
        "message": f"Тестовая транзакция отправлена: {amount} USDT → {to_address[:20]}...",
        "tx_hash": result.get("tx_hash")
    }


# ================== TELEGRAM SETTINGS ==================

@router.get("/telegram/settings")
async def get_telegram_settings(admin: dict = Depends(require_admin_role(["admin", "support"]))):
    """Получить настройки Telegram бота"""
    settings = await db.platform_settings.find_one({"type": "telegram"}, {"_id": 0})
    
    if not settings:
        return {"enabled": False, "bot_token": None}
    
    return {
        "enabled": settings.get("enabled", False),
        "bot_token": "********" if settings.get("bot_token") else None
    }


@router.put("/telegram/settings")
async def update_telegram_settings(
    data: dict = Body(...),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Обновить настройки Telegram бота"""
    update_data = {"type": "telegram"}
    
    if "enabled" in data:
        update_data["enabled"] = data["enabled"]
    
    if "bot_token" in data and data["bot_token"] and data["bot_token"] != "********":
        update_data["bot_token"] = data["bot_token"]
    
    await db.platform_settings.update_one(
        {"type": "telegram"},
        {"$set": update_data},
        upsert=True
    )
    
    return {"success": True, "message": "Настройки Telegram сохранены"}


@router.post("/telegram/broadcast")
async def send_telegram_broadcast(
    data: dict = Body(...),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """Отправить рассылку через Telegram"""
    message = data.get("message", "")
    target = data.get("target", "all")
    
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    # Get telegram settings
    settings = await db.platform_settings.find_one({"type": "telegram"}, {"_id": 0})
    if not settings or not settings.get("enabled") or not settings.get("bot_token"):
        raise HTTPException(status_code=400, detail="Telegram бот не настроен или отключён")
    
    bot_token = settings["bot_token"]
    
    # Get users with telegram_id
    query = {"telegram_id": {"$exists": True, "$ne": None}}
    
    if target == "traders":
        query["role"] = "trader"
    elif target == "merchants":
        query["role"] = "merchant"
    elif target == "staff":
        query["role"] = {"$in": ["admin", "support"]}
    
    users = await db.users.find(query, {"_id": 0, "telegram_id": 1}).to_list(10000)
    
    # Send messages
    sent_count = 0
    if _send_telegram_message:
        import asyncio
        broadcast_msg = f"📢 <b>Рассылка от BITARBITR</b>\n\n{message}"
        for user in users:
            if user.get("telegram_id"):
                try:
                    success = await _send_telegram_message(user["telegram_id"], broadcast_msg, bot_token)
                    if success:
                        sent_count += 1
                except Exception as e:
                    logger.warning(f"Failed to send broadcast to {user['telegram_id']}: {e}")
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.05)
    
    logger.info(f"Broadcast sent to {sent_count}/{len(users)} users by admin {admin['id']}")
    
    return {
        "success": True,
        "message": f"Рассылка отправлена {sent_count} из {len(users)} пользователей"
    }


# ================== SYNC WALLETS ==================

@router.post("/sync-wallets")
async def sync_wallets(admin: dict = Depends(require_admin_role(["admin"]))):
    """Синхронизировать балансы кошельков"""
    # Get all users
    users = await db.users.find({}, {"_id": 0, "id": 1}).to_list(10000)
    synced = 0
    
    for user in users:
        user_id = user["id"]
        
        # Check if wallet exists
        wallet = await db.wallets.find_one({"user_id": user_id})
        
        if not wallet:
            # Create wallet
            await db.wallets.insert_one({
                "id": f"wal_{user_id}",
                "user_id": user_id,
                "available_balance_usdt": 0,
                "locked_balance_usdt": 0,
                "total_deposited_usdt": 0,
                "total_withdrawn_usdt": 0,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            synced += 1
    
    logger.info(f"Synced {synced} wallets by admin {admin['id']}")
    
    return {"success": True, "synced_count": synced}


# ================== DATABASE BACKUP ==================

@router.get("/backup-database")
async def backup_database(admin: dict = Depends(require_admin_role(["admin"]))):
    """Экспорт базы данных в JSON"""
    import json
    from fastapi.responses import Response
    
    backup = {}
    
    # Export main collections
    collections = ["users", "wallets", "orders", "merchants", "traders", 
                   "disputes", "tickets", "usdt_withdrawals", "usdt_deposits",
                   "deposit_requests", "platform_settings", "transactions"]
    
    for coll_name in collections:
        try:
            docs = await db[coll_name].find({}, {"_id": 0}).to_list(100000)
            backup[coll_name] = docs
        except Exception as e:
            backup[coll_name] = {"error": str(e)}
    
    backup["exported_at"] = datetime.now(timezone.utc).isoformat()
    backup["exported_by"] = admin["id"]
    
    json_data = json.dumps(backup, ensure_ascii=False, indent=2, default=str)
    
    return Response(
        content=json_data.encode(),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=bitarbitr_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        }
    )



# ================== FULL DATABASE RESET ==================

RESET_PASSWORD = "RESET_ALL_DATA_2024"  # Пароль для сброса

@router.post("/reset-database")
async def reset_database(
    data: dict = Body(...),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """
    Полная очистка базы данных.
    Удаляет всех пользователей (кроме текущего админа), все заказы, споры, транзакции и т.д.
    Требует специальный пароль для подтверждения.
    """
    password = data.get("password", "")
    
    if password != RESET_PASSWORD:
        raise HTTPException(status_code=403, detail="Неверный пароль для сброса")
    
    results = {}
    
    try:
        # 1. Удаляем все заказы
        r = await db.orders.delete_many({})
        results["orders"] = r.deleted_count
        
        # 2. Удаляем все инвойсы
        r = await db.merchant_invoices.delete_many({})
        results["merchant_invoices"] = r.deleted_count
        
        # 3. Удаляем все споры
        r = await db.disputes.delete_many({})
        results["disputes"] = r.deleted_count
        
        r = await db.dispute_messages.delete_many({})
        results["dispute_messages"] = r.deleted_count
        
        # 4. Удаляем все транзакции
        r = await db.usdt_deposits.delete_many({})
        results["usdt_deposits"] = r.deleted_count
        
        r = await db.usdt_withdrawals.delete_many({})
        results["usdt_withdrawals"] = r.deleted_count
        
        r = await db.usdt_withdrawal_requests.delete_many({})
        results["usdt_withdrawal_requests"] = r.deleted_count
        
        r = await db.deposit_requests.delete_many({})
        results["deposit_requests"] = r.deleted_count
        
        r = await db.usdt_unidentified_deposits.delete_many({})
        results["usdt_unidentified_deposits"] = r.deleted_count
        
        r = await db.usdt_unidentified_withdrawals.delete_many({})
        results["usdt_unidentified_withdrawals"] = r.deleted_count
        
        # 5. Удаляем все уведомления
        r = await db.user_notifications.delete_many({})
        results["user_notifications"] = r.deleted_count
        
        r = await db.admin_notifications.delete_many({})
        results["admin_notifications"] = r.deleted_count
        
        # 6. Удаляем тикеты
        r = await db.tickets.delete_many({})
        results["tickets"] = r.deleted_count
        
        r = await db.ticket_messages.delete_many({})
        results["ticket_messages"] = r.deleted_count
        
        # 7. Удаляем реферальные данные
        r = await db.referral_earnings.delete_many({})
        results["referral_earnings"] = r.deleted_count
        
        # 8. Удаляем всех пользователей КРОМЕ текущего админа
        r = await db.users.delete_many({"id": {"$ne": admin["id"]}})
        results["users"] = r.deleted_count
        
        # 9. Удаляем трейдеров
        r = await db.traders.delete_many({})
        results["traders"] = r.deleted_count
        
        # 10. Удаляем мерчантов
        r = await db.merchants.delete_many({})
        results["merchants"] = r.deleted_count
        
        # 11. Удаляем кошельки (кроме админа)
        r = await db.wallets.delete_many({"user_id": {"$ne": admin["id"]}})
        results["wallets"] = r.deleted_count
        
        # 12. Удаляем реквизиты
        r = await db.payment_details.delete_many({})
        results["payment_details"] = r.deleted_count
        
        # 13. Удаляем usdt_wallets
        r = await db.usdt_wallets.delete_many({"user_id": {"$ne": admin["id"]}})
        results["usdt_wallets"] = r.deleted_count
        
        # 14. Сбрасываем баланс админа
        await db.users.update_one(
            {"id": admin["id"]},
            {"$set": {"referral_balance": 0}}
        )
        
        # 15. Сбрасываем кошелёк админа если есть
        await db.wallets.update_one(
            {"user_id": admin["id"]},
            {"$set": {
                "available_balance_usdt": 0,
                "locked_balance_usdt": 0,
                "earned_balance_usdt": 0,
                "pending_withdrawal_usdt": 0
            }}
        )
        
        logger.warning(f"DATABASE RESET performed by admin {admin['id']}. Results: {results}")
        
        total_deleted = sum(results.values())
        
        return {
            "success": True,
            "message": f"База данных очищена. Удалено {total_deleted} записей.",
            "details": results
        }
        
    except Exception as e:
        logger.error(f"Database reset error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при очистке: {str(e)}")



# ========================================
# TRADER BALANCE MANAGEMENT
# ========================================

@router.get("/traders/{trader_id}/locked-check")
async def check_trader_locked_balance(
    trader_id: str,
    admin: dict = Depends(require_admin_role(["admin", "support"]))
):
    """
    Проверить замороженный баланс трейдера и его активные заказы.
    Показывает есть ли несоответствие.
    """
    trader = await db.traders.find_one({"id": trader_id}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    wallet = await db.wallets.find_one({"user_id": trader["user_id"]}, {"_id": 0})
    if not wallet:
        raise HTTPException(status_code=404, detail="Кошелёк не найден")
    
    locked_amount = wallet.get("locked_balance_usdt", 0)
    available_amount = wallet.get("available_balance_usdt", 0)
    
    # Активные статусы (включая dispute/disputed - спор тоже держит средства замороженными)
    active_statuses = ["pending", "waiting_buyer_confirmation", "waiting_trader_confirmation", "waiting_requisites", "dispute", "disputed"]
    
    active_orders = await db.orders.find(
        {"trader_id": trader_id, "status": {"$in": active_statuses}},
        {"_id": 0, "id": 1, "status": 1, "amount_usdt": 1, "amount_rub": 1, "created_at": 1, "accepted_at": 1}
    ).to_list(100)
    
    total_active_usdt = sum(o.get("amount_usdt", 0) for o in active_orders)
    
    has_mismatch = False
    mismatch_type = None
    
    if len(active_orders) == 0 and locked_amount > 0.01:
        has_mismatch = True
        mismatch_type = "locked_without_orders"
    elif locked_amount > total_active_usdt + 0.5:
        has_mismatch = True
        mismatch_type = "locked_exceeds_orders"
    
    return {
        "trader_id": trader_id,
        "user_id": trader["user_id"],
        "locked_balance_usdt": round(locked_amount, 4),
        "available_balance_usdt": round(available_amount, 4),
        "active_orders_count": len(active_orders),
        "active_orders_total_usdt": round(total_active_usdt, 4),
        "active_orders": active_orders,
        "has_mismatch": has_mismatch,
        "mismatch_type": mismatch_type,
        "difference": round(locked_amount - total_active_usdt, 4) if has_mismatch else 0
    }


@router.post("/traders/{trader_id}/unfreeze")
async def manual_unfreeze_trader_balance(
    trader_id: str,
    amount: float = Query(..., description="Сумма для разморозки в USDT"),
    reason: str = Query(..., description="Причина разморозки"),
    admin: dict = Depends(require_admin_role(["admin"]))
):
    """
    Вручную разморозить средства трейдера.
    ИСПОЛЬЗОВАТЬ ТОЛЬКО после проверки через /locked-check!
    """
    trader = await db.traders.find_one({"id": trader_id}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    wallet = await db.wallets.find_one({"user_id": trader["user_id"]}, {"_id": 0})
    if not wallet:
        raise HTTPException(status_code=404, detail="Кошелёк не найден")
    
    locked_amount = wallet.get("locked_balance_usdt", 0)
    
    if amount > locked_amount:
        raise HTTPException(status_code=400, detail=f"Нельзя разморозить {amount} USDT - замороженно только {locked_amount}")
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть положительной")
    
    # Выполняем разморозку
    await db.wallets.update_one(
        {"user_id": trader["user_id"]},
        {
            "$inc": {
                "locked_balance_usdt": -round(amount, 4),
                "available_balance_usdt": round(amount, 4)
            }
        }
    )
    
    # Исправляем микро-остатки
    wallet_check = await db.wallets.find_one({"user_id": trader["user_id"]}, {"_id": 0, "locked_balance_usdt": 1})
    if wallet_check:
        locked_val = wallet_check.get("locked_balance_usdt", 0)
        if locked_val < 0 or (0 < locked_val < 0.01):
            await db.wallets.update_one({"user_id": trader["user_id"]}, {"$set": {"locked_balance_usdt": 0}})
    
    # Логируем действие
    await db.admin_actions.insert_one({
        "id": f"action_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
        "type": "manual_unfreeze",
        "admin_id": admin["id"],
        "trader_id": trader_id,
        "amount_usdt": amount,
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    logger.warning(f"🔓 MANUAL UNFREEZE: Admin {admin['id']} unfroze {amount} USDT for trader {trader_id}. Reason: {reason}")
    
    return {
        "success": True,
        "message": f"Разморожено {amount} USDT для трейдера {trader_id}",
        "trader_id": trader_id,
        "unfrozen_amount": amount,
        "reason": reason,
        "admin_id": admin["id"]
    }
