"""
BITARBITR P2P Platform - Merchant Router
Операции мерчанта
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import secrets
import logging
import os

router = APIRouter(tags=["Merchant"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

# Глобальные зависимости
_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"
_site_url = os.environ.get("SITE_URL", "https://bitarbitr.org")


def init_router(database, jwt_secret: str, jwt_algorithm: str = "HS256", site_url: str = None):
    """Инициализация роутера"""
    global _db, _jwt_secret, _jwt_algorithm, _site_url
    _db = database
    _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm
    if site_url:
        _site_url = site_url

def generate_id(prefix: str = "") -> str:
    """Генерация уникального ID"""
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{prefix}{date_part}_{secrets.token_hex(3).upper()}"


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


def require_merchant():
    """Проверка роли мерчанта"""
    async def checker(user: dict = Depends(get_current_user)):
        if user["role"] != "merchant":
            raise HTTPException(status_code=403, detail="Доступ только для мерчантов")
        return user
    return checker


async def get_merchant_by_api_key(api_key: str):
    """Получение мерчанта по API ключу"""
    merchant = await _db.merchants.find_one({"api_key": api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return merchant


# ================== ENDPOINTS ==================

@router.get("/merchant/profile")
async def get_merchant_profile(user: dict = Depends(require_merchant())):
    """Получить профиль мерчанта"""
    merchant = await _db.merchants.find_one({"user_id": user["id"]}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Профиль мерчанта не найден")
    
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    return {
        **merchant,
        "wallet": wallet,
        "user": {
            "id": user["id"],
            "login": user["login"],
            "nickname": user.get("nickname"),
            "approval_status": user.get("approval_status")
        }
    }


@router.get("/merchant/balance")
async def get_merchant_balance(user: dict = Depends(require_merchant())):
    """Получить баланс мерчанта"""
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    if not wallet:
        return {"available_usdt": 0, "locked_usdt": 0}
    
    return {
        "available_usdt": wallet.get("available_balance_usdt", 0),
        "locked_usdt": wallet.get("locked_balance_usdt", 0),
        "pending_usdt": wallet.get("pending_balance_usdt", 0)
    }


@router.get("/merchant/stats")
async def get_merchant_stats(
    period: str = "today",
    user: dict = Depends(require_merchant())
):
    """
    Получить статистику мерчанта
    period: today, week, month, all
    """
    from datetime import timedelta
    
    merchant = await _db.merchants.find_one({"user_id": user["id"]}, {"_id": 0})
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    now = datetime.now(timezone.utc)
    
    # Определяем временной диапазон
    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = None
    
    # Базовый запрос
    base_query = {"merchant_id": merchant["id"]}
    if start_date:
        base_query["created_at"] = {"$gte": start_date.isoformat()}
    
    # Общая статистика
    total_invoices = await _db.orders.count_documents(base_query)
    
    # По статусам
    paid_query = {**base_query, "status": {"$in": ["paid", "completed"]}}
    pending_query = {**base_query, "status": {"$in": ["pending", "waiting_buyer_confirmation", "waiting_trader_confirmation"]}}
    failed_query = {**base_query, "status": {"$in": ["failed", "cancelled", "expired"]}}
    dispute_query = {**base_query, "status": {"$in": ["dispute", "disputed"]}}
    
    paid_count = await _db.orders.count_documents(paid_query)
    pending_count = await _db.orders.count_documents(pending_query)
    failed_count = await _db.orders.count_documents(failed_query)
    dispute_count = await _db.orders.count_documents(dispute_query)
    
    # Суммы
    pipeline = [
        {"$match": paid_query},
        {"$group": {
            "_id": None,
            "total_rub": {"$sum": "$amount_rub"},
            "total_usdt": {"$sum": "$amount_usdt"}
        }}
    ]
    
    amounts = await _db.orders.aggregate(pipeline).to_list(1)
    total_rub = amounts[0]["total_rub"] if amounts else 0
    total_usdt = amounts[0]["total_usdt"] if amounts else 0
    
    # Средний чек
    avg_amount = total_rub / paid_count if paid_count > 0 else 0
    
    # Конверсия
    conversion_rate = (paid_count / total_invoices * 100) if total_invoices > 0 else 0
    
    # Курс
    settings = await _db.settings.find_one({"key": "exchange_rate"})
    exchange_rate = settings.get("value", 100) if settings else 100
    
    return {
        "status": "success",
        "data": {
            "period": period,
            "period_start": start_date.isoformat() if start_date else None,
            "summary": {
                "total_invoices": total_invoices,
                "paid": paid_count,
                "pending": pending_count,
                "failed": failed_count,
                "disputes": dispute_count
            },
            "volume": {
                "total_rub": round(total_rub or 0, 2),
                "total_usdt": round(total_usdt or 0, 2),
                "average_amount_rub": round(avg_amount, 2)
            },
            "conversion_rate": round(conversion_rate, 2),
            "balance": {
                "available_usdt": wallet.get("available_balance_usdt", 0) if wallet else 0,
                "locked_usdt": wallet.get("locked_balance_usdt", 0) if wallet else 0
            },
            "exchange_rate": exchange_rate,
            "rate_limits": {
                "create": {"limit": 60, "remaining": 60, "reset_in": 60},
                "status": {"limit": 120, "remaining": 120, "reset_in": 60},
                "transactions": {"limit": 30, "remaining": 30, "reset_in": 60}
            }
        }
    }


@router.get("/merchant/orders")
async def get_merchant_orders(
    status: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(require_merchant())
):
    """Получить ордера мерчанта"""
    merchant = await _db.merchants.find_one({"user_id": user["id"]})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    query = {"merchant_id": merchant["id"]}
    if status:
        query["status"] = status
    
    orders = await _db.orders.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"orders": orders}


@router.post("/merchant/regenerate-api-key")
async def regenerate_api_key(user: dict = Depends(require_merchant())):
    """Перегенерировать API ключ"""
    new_key = f"sk_live_{secrets.token_hex(24)}"
    
    await _db.merchants.update_one(
        {"user_id": user["id"]},
        {"$set": {"api_key": new_key}}
    )
    
    return {"success": True, "api_key": new_key}


@router.post("/merchant/regenerate-secret-key")
async def regenerate_secret_key(user: dict = Depends(require_merchant())):
    """Перегенерировать Secret ключ для подписи"""
    new_secret = secrets.token_hex(32)
    
    await _db.merchants.update_one(
        {"user_id": user["id"]},
        {"$set": {"secret_key": new_secret}}
    )
    
    return {"success": True, "secret_key": new_secret}


@router.get("/merchant/transactions")
async def get_merchant_transactions(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(require_merchant())
):
    """
    Получить список транзакций мерчанта с фильтрацией
    status: all, active, completed, dispute
    """
    merchant = await _db.merchants.find_one({"user_id": user["id"]})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    query = {"merchant_id": merchant["id"]}
    
    # Фильтрация по статусу
    if status and status != "all":
        if status == "active":
            query["status"] = {"$in": ["pending", "waiting_buyer_confirmation", "waiting_trader_confirmation", "new"]}
        elif status == "completed":
            query["status"] = {"$in": ["paid", "completed"]}
        elif status == "dispute":
            query["status"] = {"$in": ["dispute", "disputed"]}
        elif status == "cancelled":
            query["status"] = {"$in": ["cancelled", "expired", "failed"]}
        else:
            query["status"] = status
    
    # Получаем транзакции
    orders = await _db.orders.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    total = await _db.orders.count_documents(query)
    
    # Добавляем dispute_url для спорных транзакций
    for order in orders:
        if order.get("status") in ["dispute", "disputed"] and order.get("dispute_token"):
            order["dispute_url"] = f"{_site_url}/dispute/{order['dispute_token']}"
        elif order.get("dispute_id"):
            # Получаем токен из dispute
            dispute = await _db.disputes.find_one({"id": order["dispute_id"]}, {"_id": 0, "dispute_token": 1})
            if dispute and dispute.get("dispute_token"):
                order["dispute_url"] = f"{_site_url}/dispute/{dispute['dispute_token']}"
    
    return {
        "transactions": orders,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/merchant/transaction/{order_id}")
async def get_merchant_transaction(
    order_id: str,
    user: dict = Depends(require_merchant())
):
    """Получить детали конкретной транзакции"""
    merchant = await _db.merchants.find_one({"user_id": user["id"]})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    order = await _db.orders.find_one({
        "id": order_id,
        "merchant_id": merchant["id"]
    }, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")
    
    # Добавляем dispute_url если есть спор
    if order.get("dispute_token"):
        order["dispute_url"] = f"{_site_url}/dispute/{order['dispute_token']}"
    elif order.get("dispute_id"):
        dispute = await _db.disputes.find_one({"id": order["dispute_id"]}, {"_id": 0})
        if dispute:
            order["dispute_info"] = {
                "id": dispute["id"],
                "status": dispute.get("status"),
                "reason": dispute.get("reason"),
                "created_at": dispute.get("created_at"),
                "dispute_url": f"{_site_url}/dispute/{dispute.get('dispute_token')}" if dispute.get("dispute_token") else None
            }
    
    return {"transaction": order}


@router.post("/merchant/transaction/{order_id}/open-dispute")
async def merchant_open_dispute(
    order_id: str,
    reason: str,
    user: dict = Depends(require_merchant())
):
    """Открыть спор по транзакции (для мерчанта)"""
    merchant = await _db.merchants.find_one({"user_id": user["id"]})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    order = await _db.orders.find_one({
        "id": order_id,
        "merchant_id": merchant["id"]
    })
    
    if not order:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")
    
    # Проверяем, можно ли открыть спор
    if order.get("status") in ["dispute", "disputed"]:
        raise HTTPException(status_code=400, detail="Спор уже открыт")
    
    if order.get("status") in ["completed"]:
        raise HTTPException(status_code=400, detail="Нельзя открыть спор по завершённой транзакции")
    
    # Генерируем токен спора
    dispute_token = order.get("dispute_token") or secrets.token_urlsafe(32)
    dispute_url = f"{_site_url}/dispute/{dispute_token}"
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Создаём спор
    dispute_id = generate_id("dsp_")
    dispute = {
        "id": dispute_id,
        "order_id": order_id,
        "merchant_id": merchant["id"],
        "trader_id": order.get("trader_id"),
        "dispute_token": dispute_token,
        "reason": reason,
        "status": "open",
        "initiated_by": "merchant",
        "created_at": now,
        "updated_at": now
    }
    await _db.disputes.insert_one(dispute)
    
    # Обновляем заказ
    await _db.orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "status": "dispute",
                "dispute_id": dispute_id,
                "dispute_token": dispute_token,
                "dispute_url": dispute_url
            }
        }
    )
    
    return {
        "success": True,
        "dispute_id": dispute_id,
        "dispute_url": dispute_url,
        "message": "Спор открыт. Передайте ссылку клиенту для связи с поддержкой."
    }


# ================== V1 API (для интеграции) ==================

@router.get("/v1/merchant/orders")
async def v1_get_orders(api_key: str, status: Optional[str] = None, limit: int = 50):
    """API v1: Получить ордера"""
    merchant = await get_merchant_by_api_key(api_key)
    
    query = {"merchant_id": merchant["id"]}
    if status:
        query["status"] = status
    
    orders = await _db.orders.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"orders": orders}


@router.get("/v1/merchant/orders/{order_id}")
async def v1_get_order(order_id: str, api_key: str):
    """API v1: Получить ордер по ID"""
    merchant = await get_merchant_by_api_key(api_key)
    
    order = await _db.orders.find_one({
        "id": order_id,
        "merchant_id": merchant["id"]
    }, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Ордер не найден")
    
    return {"order": order}


@router.get("/v1/merchant/balance")
async def v1_get_balance(api_key: str):
    """API v1: Получить баланс"""
    merchant = await get_merchant_by_api_key(api_key)
    
    wallet = await _db.wallets.find_one({"user_id": merchant["user_id"]}, {"_id": 0})
    
    return {
        "available_usdt": wallet.get("available_balance_usdt", 0) if wallet else 0,
        "locked_usdt": wallet.get("locked_balance_usdt", 0) if wallet else 0
    }


@router.get("/v1/merchant/exchange-rate")
async def v1_get_exchange_rate(api_key: str):
    """API v1: Получить текущий курс"""
    await get_merchant_by_api_key(api_key)  # Проверка API ключа
    
    settings = await _db.settings.find_one({"key": "exchange_rate"})
    rate = settings.get("value", 100) if settings else 100
    
    return {"rate": rate, "currency": "USDT/RUB"}



@router.get("/merchant/analytics")
async def get_merchant_analytics(
    period: str = "week",
    user: dict = Depends(require_merchant())
):
    """Получить аналитику мерчанта за период"""
    merchant = await _db.merchants.find_one({"user_id": user["id"]}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    # Определяем диапазон дат
    from datetime import timedelta
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
    
    # Получаем заказы мерчанта за период
    orders = await _db.orders.find({
        "merchant_id": merchant["id"],
        "created_at": {"$gte": start_date}
    }, {"_id": 0}).to_list(10000)
    
    # Фильтруем по статусу
    completed_orders = [o for o in orders if o.get("status") == "completed"]
    cancelled_orders = [o for o in orders if o.get("status") in ["cancelled", "expired"]]
    pending_orders = [o for o in orders if o.get("status") not in ["completed", "cancelled", "expired"]]
    
    # Считаем статистику
    total_volume_rub = sum(o.get("amount_rub", 0) or 0 for o in completed_orders)
    total_received_usdt = sum(o.get("merchant_amount_usdt", 0) or 0 for o in completed_orders)
    
    # Средний чек
    avg_order_rub = total_volume_rub / len(completed_orders) if completed_orders else 0
    
    # Успешность
    total_orders = len(completed_orders) + len(cancelled_orders)
    success_rate = (len(completed_orders) / total_orders * 100) if total_orders > 0 else 0
    
    # Данные по дням для графиков
    daily_data = {}
    for o in completed_orders:
        date = o.get("completed_at", o.get("created_at", ""))[:10]
        if date:
            if date not in daily_data:
                daily_data[date] = {"volume_rub": 0, "count": 0}
            daily_data[date]["volume_rub"] += o.get("amount_rub", 0) or 0
            daily_data[date]["count"] += 1
    
    daily_volume = [
        {"date": d, "volume_rub": v["volume_rub"], "count": v["count"]}
        for d, v in sorted(daily_data.items())
    ]
    
    # По методам оплаты
    payment_methods = {}
    for o in completed_orders:
        method = o.get("payment_method", "unknown")
        if method not in payment_methods:
            payment_methods[method] = {"count": 0, "volume_rub": 0}
        payment_methods[method]["count"] += 1
        payment_methods[method]["volume_rub"] += o.get("amount_rub", 0) or 0
    
    # Баланс мерчанта
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    balance_usdt = wallet.get("available_balance_usdt", 0) if wallet else 0
    
    return {
        "balance_usdt": balance_usdt,
        "volume": {
            "total_rub": total_volume_rub,
            "total_usdt": total_received_usdt
        },
        "orders": {
            "total": len(orders),
            "completed": len(completed_orders),
            "cancelled": len(cancelled_orders),
            "pending": len(pending_orders)
        },
        "success_rate": success_rate,
        "avg_order_rub": avg_order_rub,
        "daily_volume": daily_volume,
        "payment_methods": payment_methods,
        "period": period
    }
