"""
BITARBITR P2P Platform - Trader Router
Операции трейдера
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import secrets
import logging
import os

router = APIRouter(tags=["Trader"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

# Глобальные зависимости
_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"
_send_telegram = None
_fetch_rate_func = None
_notify_order_completed = None


def init_router(database, jwt_secret: str, jwt_algorithm: str = "HS256",
                telegram_func=None, fetch_rate_func=None, notify_order_completed_func=None):
    """Инициализация роутера"""
    global _db, _jwt_secret, _jwt_algorithm, _send_telegram, _fetch_rate_func, _notify_order_completed
    _db = database
    _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm
    _send_telegram = telegram_func
    _fetch_rate_func = fetch_rate_func
    _notify_order_completed = notify_order_completed_func


async def get_current_rate():
    """Получение актуального курса USDT/RUB из единого источника"""
    if _fetch_rate_func:
        try:
            rate = await _fetch_rate_func()
            return rate
        except Exception as e:
            logger.error(f"Error fetching rate: {e}")
    # Fallback на базу данных
    settings = await _db.settings.find_one({"key": "exchange_rate"})
    return settings.get("value", 75.0) if settings else 75.0


def generate_id(prefix: str = "") -> str:
    """Генерация уникального ID"""
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{prefix}{date_part}_{secrets.token_hex(3).upper()}"


async def process_referral_earnings(user_id: str, commission_usdt: float, order_id: str):
    """
    Обработка реферальных начислений при завершении сделки.
    Начисляет процент от заработка трейдера рефереру (до 3 уровней).
    ВАЖНО: Бонусы платит ПЛОЩАДКА, не вычитаются из заработка трейдера!
    """
    if commission_usdt <= 0:
        return
    
    # Получаем настройки реферальной программы
    settings = await _db.platform_settings.find_one({"key": "referral"})
    if not settings or not settings.get("enabled", True):
        return
    
    levels = settings.get("levels", [
        {"level": 1, "percent": 5},
        {"level": 2, "percent": 3},
        {"level": 3, "percent": 1}
    ])
    
    # Получаем пользователя который совершил сделку
    user = await _db.users.find_one({"id": user_id}, {"_id": 0})
    if not user or not user.get("referrer_id"):
        return
    
    # Уровень 1: Прямой реферер
    referrer_id = user.get("referrer_id")
    if referrer_id and len(levels) >= 1:
        percent = levels[0].get("percent", 5)
        earning = round(commission_usdt * percent / 100, 4)
        if earning > 0:
            await _db.referral_earnings.insert_one({
                "id": generate_id("ref_"),
                "referrer_id": referrer_id,
                "from_user_id": user_id,
                "order_id": order_id,
                "level": 1,
                "percent": percent,
                "amount_usdt": earning,
                "paid_by": "platform",  # Платит площадка
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            # Обновляем реферальный баланс (в USDT)
            await _db.users.update_one(
                {"id": referrer_id},
                {"$inc": {"referral_balance": earning}}
            )
            logger.info(f"Referral earning L1: {earning} USDT for {referrer_id} from order {order_id} (paid by platform)")
    
    # Уровень 2: Реферер реферера
    if referrer_id and len(levels) >= 2:
        level2_user = await _db.users.find_one({"id": referrer_id}, {"_id": 0, "referrer_id": 1})
        if level2_user and level2_user.get("referrer_id"):
            referrer2_id = level2_user["referrer_id"]
            percent = levels[1].get("percent", 3)
            earning = round(commission_usdt * percent / 100, 4)
            if earning > 0:
                await _db.referral_earnings.insert_one({
                    "id": generate_id("ref_"),
                    "referrer_id": referrer2_id,
                    "from_user_id": user_id,
                    "order_id": order_id,
                    "level": 2,
                    "percent": percent,
                    "amount_usdt": earning,
                    "paid_by": "platform",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                await _db.users.update_one(
                    {"id": referrer2_id},
                    {"$inc": {"referral_balance": earning}}
                )
                logger.info(f"Referral earning L2: {earning} USDT for {referrer2_id} from order {order_id} (paid by platform)")
            
            # Уровень 3
            if len(levels) >= 3:
                level3_user = await _db.users.find_one({"id": referrer2_id}, {"_id": 0, "referrer_id": 1})
                if level3_user and level3_user.get("referrer_id"):
                    referrer3_id = level3_user["referrer_id"]
                    percent = levels[2].get("percent", 1)
                    earning = round(commission_usdt * percent / 100, 4)
                    if earning > 0:
                        await _db.referral_earnings.insert_one({
                            "id": generate_id("ref_"),
                            "referrer_id": referrer3_id,
                            "from_user_id": user_id,
                            "order_id": order_id,
                            "level": 3,
                            "percent": percent,
                            "amount_usdt": earning,
                            "paid_by": "platform",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        })
                        await _db.users.update_one(
                            {"id": referrer3_id},
                            {"$inc": {"referral_balance": earning}}
                        )
                        logger.info(f"Referral earning L3: {earning} USDT for {referrer3_id} from order {order_id} (paid by platform)")


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


def require_trader():
    """Проверка роли трейдера"""
    async def checker(user: dict = Depends(get_current_user)):
        if user["role"] != "trader":
            raise HTTPException(status_code=403, detail="Доступ только для трейдеров")
        return user
    return checker


# ================== MODELS ==================

class PaymentDetailCreate(BaseModel):
    bank_name: Optional[str] = None
    card_number: Optional[str] = None
    holder_name: Optional[str] = None
    phone_number: Optional[str] = None
    operator_name: Optional[str] = None
    qr_data: Optional[str] = None
    manual_text: Optional[str] = None
    account_number: Optional[str] = None
    recipient_name: Optional[str] = None
    comment: Optional[str] = None
    payment_type: Optional[str] = "card"
    min_amount_rub: Optional[float] = 100.0
    max_amount_rub: Optional[float] = 500000.0
    daily_limit_rub: Optional[float] = 1500000.0
    priority: Optional[int] = 10
    is_active: Optional[bool] = True


# ================== ENDPOINTS ==================

@router.get("/trader/profile")
async def get_trader_profile(user: dict = Depends(require_trader())):
    """Получить профиль трейдера"""
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Профиль трейдера не найден")
    
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    return {
        **trader,
        "wallet": wallet,
        "user": {
            "id": user["id"],
            "login": user["login"],
            "nickname": user.get("nickname"),
            "approval_status": user.get("approval_status")
        }
    }


@router.put("/trader/profile")
async def update_trader_profile(
    is_available: Optional[bool] = None,
    auto_mode: Optional[bool] = None,
    min_deal_amount_rub: Optional[float] = None,
    max_deal_amount_rub: Optional[float] = None,
    user: dict = Depends(require_trader())
):
    """Обновить профиль трейдера"""
    update = {}
    if is_available is not None:
        update["is_available"] = is_available
    if auto_mode is not None:
        update["auto_mode"] = auto_mode
    if min_deal_amount_rub is not None:
        update["min_deal_amount_rub"] = min_deal_amount_rub
    if max_deal_amount_rub is not None:
        update["max_deal_amount_rub"] = max_deal_amount_rub
    
    if update:
        await _db.traders.update_one({"user_id": user["id"]}, {"$set": update})
    
    return {"success": True}


@router.get("/trader/balance")
async def get_trader_balance(user: dict = Depends(require_trader())):
    """Получить баланс трейдера для отображения в шапке"""
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    if not wallet:
        return {
            "available": 0,
            "locked": 0,
            "earned": 0,
            "pending_withdrawal": 0
        }
    
    return {
        "available": wallet.get("available_balance_usdt", 0),
        "locked": wallet.get("locked_balance_usdt", 0),
        "earned": wallet.get("earned_balance_usdt", 0),
        "pending_withdrawal": wallet.get("pending_withdrawal_usdt", 0)
    }


@router.post("/trader/withdraw-earnings")
async def withdraw_earnings(user: dict = Depends(require_trader())):
    """Перевести заработанное на баланс"""
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Кошелёк не найден")
    
    earned = wallet.get("earned_balance_usdt", 0)
    if earned <= 0:
        raise HTTPException(status_code=400, detail="Нет заработанных средств для вывода")
    
    # Переводим earned в available
    await _db.wallets.update_one(
        {"user_id": user["id"]},
        {
            "$inc": {"available_balance_usdt": earned},
            "$set": {"earned_balance_usdt": 0}
        }
    )
    
    # Логируем операцию
    await _db.wallet_transactions.insert_one({
        "id": generate_id("wtx_"),
        "user_id": user["id"],
        "type": "earnings_withdrawal",
        "amount_usdt": earned,
        "description": "Перевод заработанных средств на баланс",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": True, "withdrawn": earned}


@router.get("/trader/payment-details")
async def get_payment_details(user: dict = Depends(require_trader())):
    """Получить платёжные реквизиты"""
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    trader_id = trader["id"] if trader else None
    
    # Ищем и по user_id и по trader_id
    details = await _db.payment_details.find(
        {"$or": [{"user_id": user["id"]}, {"trader_id": trader_id}]},
        {"_id": 0}
    ).to_list(50)
    return details


@router.post("/trader/payment-details")
async def create_payment_detail(
    data: PaymentDetailCreate,
    user: dict = Depends(require_trader())
):
    """Добавить платёжные реквизиты"""
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Профиль трейдера не найден")
    
    detail = {
        "id": generate_id("pd_"),
        "user_id": user["id"],
        "trader_id": trader["id"],
        "payment_type": data.payment_type or "card",
        "bank_name": data.bank_name,
        "card_number": data.card_number,
        "holder_name": data.holder_name or data.comment,  # comment как fallback
        "phone_number": data.phone_number,
        "operator_name": data.operator_name,
        "qr_data": data.qr_data,
        "manual_text": data.manual_text,
        "account_number": data.account_number,
        "recipient_name": data.recipient_name,
        "comment": data.comment,
        "is_active": data.is_active if data.is_active is not None else True,
        "min_amount_rub": data.min_amount_rub or 100,
        "max_amount_rub": data.max_amount_rub or 500000,
        "daily_limit_rub": data.daily_limit_rub or 1500000,
        "priority": data.priority or 1,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await _db.payment_details.insert_one(detail)
    detail.pop("_id", None)
    return {"success": True, "detail": detail}


@router.delete("/trader/payment-details/{detail_id}")
async def delete_payment_detail(detail_id: str, user: dict = Depends(require_trader())):
    """Удалить платёжные реквизиты"""
    result = await _db.payment_details.delete_one({
        "id": detail_id,
        "user_id": user["id"]
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Реквизиты не найдены")
    return {"success": True}


@router.get("/trader/stats")
async def get_trader_stats(user: dict = Depends(require_trader())):
    """Получить статистику трейдера"""
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    # ID для поиска ордеров - может быть user_id или trader.id
    trader_ids = [user["id"]]
    if trader and trader.get("id"):
        trader_ids.append(trader["id"])
    
    # Подсчёт активных ордеров
    active_orders = await _db.orders.count_documents({
        "trader_id": {"$in": trader_ids},
        "status": {"$in": ["pending", "paid", "processing"]}
    })
    
    # Статистика за сегодня
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    today_orders = await _db.orders.find({
        "trader_id": {"$in": trader_ids},
        "status": "completed",
        "completed_at": {"$gte": today_start}
    }).to_list(1000)
    
    today_volume_rub = sum(o.get("amount_rub", 0) for o in today_orders)
    today_commission = sum(o.get("trader_commission_usdt", 0) for o in today_orders)
    
    # Получаем курс из единого источника
    exchange_rate = await get_current_rate()
    
    return {
        "balance": {
            "available_usdt": wallet.get("available_balance_usdt", 0) if wallet else 0,
            "locked_usdt": wallet.get("locked_balance_usdt", 0) if wallet else 0,
            "pending_withdrawal_usdt": wallet.get("pending_withdrawal_usdt", 0) if wallet else 0
        },
        "rating": trader.get("rating", 5.0) if trader else 5.0,
        "is_available": trader.get("is_available", False) if trader else False,
        "active_orders": active_orders,
        "today": {
            "deals_count": len(today_orders),
            "volume_rub": today_volume_rub,
            "commission_usdt": today_commission
        },
        "total": {
            "deals": trader.get("total_deals", 0) if trader else 0,
            "successful_deals": trader.get("successful_deals", 0) if trader else 0,
            "volume_rub": trader.get("total_volume_rub", 0) if trader else 0,
            "commission_usdt": trader.get("total_commission_usdt", 0) if trader else 0
        },
        "exchange_rate": exchange_rate
    }


@router.get("/trader/orders")
async def get_trader_orders(
    status: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(require_trader())
):
    """Получить ордера трейдера"""
    # Get trader record first
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader:
        return {"orders": []}
    
    query = {"trader_id": trader["id"]}
    if status:
        query["status"] = status
    
    orders = await _db.orders.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"orders": orders}


@router.get("/trader/disputes")
async def get_trader_disputes(user: dict = Depends(require_trader())):
    """Получить споры трейдера с данными заказов"""
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader:
        return {"disputes": []}
    
    disputes = await _db.disputes.find(
        {"trader_id": trader["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    # Добавляем данные заказа к каждому спору
    result = []
    for dispute in disputes:
        order = await _db.orders.find_one({"id": dispute.get("order_id")}, {"_id": 0})
        dispute["order"] = order
        result.append(dispute)
    
    return {"disputes": result}


@router.post("/trader/orders/{order_id}/dispute")
async def create_trader_dispute(
    order_id: str,
    user: dict = Depends(require_trader())
):
    """Трейдер открывает спор по заказу"""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Профиль трейдера не найден")
    
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем что это заказ этого трейдера
    if trader["id"] != order.get("trader_id"):
        raise HTTPException(status_code=403, detail="Нет доступа к этому заказу")
    
    # Проверяем статус заказа - трейдер может открыть спор сразу после подтверждения покупателем
    allowed_statuses = ["waiting_trader_confirmation", "paid"]
    if order.get("status") not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Невозможно открыть спор для заказа в статусе: {order.get('status')}")
    
    # Трейдер может открыть спор сразу (без ожидания 10 минут)
    # Проверяем только что покупатель подтвердил оплату
    if not order.get("buyer_confirmed_at"):
        raise HTTPException(status_code=400, detail="Покупатель ещё не подтвердил оплату")
    
    # Проверяем что спор ещё не открыт
    existing = await _db.disputes.find_one({"order_id": order_id}, {"_id": 0})
    if existing:
        return {
            "success": True, 
            "dispute_id": existing["id"], 
            "public_token": existing.get("public_token"),
            "message": "Спор уже существует"
        }
    
    # Генерируем токен для публичного доступа
    public_token = secrets.token_urlsafe(32)
    short_order_id = order_id.split('_')[-1] if '_' in order_id else order_id[-6:]
    
    dispute = {
        "id": generate_id("DSP-"),
        "order_id": order_id,
        "merchant_id": order.get("merchant_id"),
        "trader_id": trader["id"],
        "status": "open",
        "reason": "Трейдер открыл спор",
        "public_token": public_token,
        "initiated_by": "trader",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await _db.disputes.insert_one(dispute)
    
    # Обновляем статус заказа
    await _db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "disputed",
            "dispute_id": dispute["id"],
            "disputed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Формируем полную ссылку на спор
    # Используем SITE_URL или REACT_APP_BACKEND_URL
    site_url = os.environ.get("SITE_URL", "")
    if not site_url:
        backend_url = os.environ.get("REACT_APP_BACKEND_URL", "")
        if "/api" in backend_url:
            site_url = backend_url.replace("/api", "")
        else:
            site_url = backend_url
    
    dispute_link = f"{site_url}/dispute/{public_token}?buyer=true"
    
    # Автосообщение с полной ссылкой
    auto_message = {
        "id": generate_id("MSG-"),
        "dispute_id": dispute["id"],
        "sender_role": "admin",
        "sender_id": "system",
        "sender_name": "Система",
        "text": f"📋 Спор по заказу #{short_order_id} открыт трейдером.\n\n🔗 Ссылка на чат спора:\n{dispute_link}",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await _db.dispute_messages.insert_one(auto_message)
    
    logger.info(f"Dispute {dispute['id']} created by trader {trader['id']} for order {order_id}")
    
    return {
        "success": True,
        "dispute_id": dispute["id"],
        "public_token": public_token,
        "dispute_url": f"/dispute/{public_token}?buyer=true"
    }



@router.get("/trader/debug-orders")
async def debug_available_orders(user: dict = Depends(require_trader())):
    """
    ОТЛАДОЧНЫЙ ENDPOINT - показывает всё без фильтров
    """
    from bson import ObjectId
    
    def clean_doc(doc):
        if doc is None:
            return None
        cleaned = {}
        for k, v in doc.items():
            if k == '_id' or isinstance(v, ObjectId):
                continue
            cleaned[k] = v
        return cleaned
    
    # 1. Информация о трейдере
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    
    # 2. Реквизиты трейдера
    payment_details = []
    if trader:
        pds = await _db.payment_details.find({"trader_id": trader["id"]}, {"_id": 0}).to_list(50)
        payment_details = [clean_doc(pd) for pd in pds]
    
    # 3. Кошелёк
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    # 4. ВСЕ заказы waiting_requisites (без фильтров!)
    all_waiting = await _db.orders.find({"status": "waiting_requisites"}, {"_id": 0}).limit(20).to_list(20)
    all_waiting = [clean_doc(o) for o in all_waiting]
    
    # 5. Заказы без трейдера
    no_trader = await _db.orders.find({
        "status": "waiting_requisites",
        "$or": [{"trader_id": None}, {"trader_id": {"$exists": False}}, {"trader_id": ""}]
    }, {"_id": 0}).limit(20).to_list(20)
    no_trader = [clean_doc(o) for o in no_trader]
    
    # 6. Общее количество заказов
    total_orders = await _db.orders.count_documents({})
    waiting_count = await _db.orders.count_documents({"status": "waiting_requisites"})
    
    return {
        "trader": {
            "id": trader.get("id") if trader else None,
            "user_id": user["id"],
            "is_available": trader.get("is_available") if trader else None,
            "exists": trader is not None
        },
        "payment_details": {
            "count": len(payment_details),
            "active_count": len([pd for pd in payment_details if pd.get("is_active")]),
            "types": [pd.get("payment_type") for pd in payment_details if pd.get("is_active")],
            "details": payment_details
        },
        "wallet": {
            "available_balance_usdt": wallet.get("available_balance_usdt") if wallet else 0,
            "frozen_balance_usdt": wallet.get("frozen_balance_usdt") if wallet else 0
        },
        "orders_stats": {
            "total_in_db": total_orders,
            "waiting_requisites_count": waiting_count
        },
        "all_waiting_orders": all_waiting,
        "orders_without_trader": no_trader
    }


@router.get("/trader/available-orders")
async def get_available_orders(
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    payment_method: Optional[str] = None,
    payment_methods: Optional[str] = None,  # Несколько методов через запятую
    user: dict = Depends(require_trader())
):
    """
    Получить список доступных заявок для взятия в работу.
    Показывает только заявки со статусом waiting_requisites,
    которые ещё не взяты другим трейдером.
    
    Фильтры (опциональные):
    - min_amount: минимальная сумма в рублях
    - max_amount: максимальная сумма в рублях
    - payment_method: один тип оплаты (card, sbp, sim и т.д.)
    - payment_methods: несколько типов через запятую (card,sbp,sim)
    """
    from bson import ObjectId
    
    def clean_doc(doc):
        """Удаляет ObjectId из документа"""
        if doc is None:
            return None
        cleaned = {}
        for k, v in doc.items():
            if k == '_id' or isinstance(v, ObjectId):
                continue
            cleaned[k] = v
        return cleaned
    
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Профиль трейдера не найден")
    
    logger.info(f"Getting available orders for trader {trader.get('id')}, is_available={trader.get('is_available')}")
    
    # Получаем реквизиты трейдера
    payment_details = await _db.payment_details.find({
        "trader_id": trader["id"],
        "is_active": True
    }, {"_id": 0}).to_list(50)
    
    logger.info(f"Trader {trader.get('id')} has {len(payment_details)} active payment details")
    
    # Собираем доступные типы платежей трейдера
    trader_payment_types = set()
    for pd in payment_details:
        ptype = pd.get("payment_type")
        if ptype:
            trader_payment_types.add(ptype)
    
    logger.info(f"Trader payment types: {trader_payment_types}")
    
    # Получаем баланс трейдера
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    available_balance = wallet.get("available_balance_usdt", 0) if wallet else 0
    
    logger.info(f"Trader available balance: {available_balance} USDT")
    
    # Получаем лимиты трейдера из профиля
    trader_min_amount = trader.get("min_deal_amount_rub", 100)
    trader_max_amount = trader.get("max_deal_amount_rub", 500000)
    
    # Базовый запрос: все заявки waiting_requisites без трейдера
    query = {
        "status": "waiting_requisites",
        "$or": [
            {"trader_id": None},
            {"trader_id": {"$exists": False}},
            {"trader_id": ""}
        ]
    }
    
    # Добавляем фильтры по сумме если указаны в запросе
    if min_amount is not None and min_amount > 0:
        query["amount_rub"] = {"$gte": min_amount}
    if max_amount is not None and max_amount > 0:
        if "amount_rub" in query:
            query["amount_rub"]["$lte"] = max_amount
        else:
            query["amount_rub"] = {"$lte": max_amount}
    
    # Фильтр по методам оплаты (поддержка нескольких через запятую)
    methods_list = []
    if payment_methods:
        methods_list = [m.strip() for m in payment_methods.split(',') if m.strip()]
    elif payment_method:
        methods_list = [payment_method]
    
    if methods_list:
        query["requested_payment_method"] = {"$in": methods_list}
    
    logger.info(f"MongoDB query: {query}")
    
    # Получаем заказы
    orders_raw = await _db.orders.find(query, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    
    logger.info(f"Found {len(orders_raw)} raw orders in database")
    
    # Очищаем от возможных ObjectId
    orders = [clean_doc(o) for o in orders_raw]
    
    # Фильтруем и добавляем метаданные для каждого заказа
    available_orders = []
    for order in orders:
        order_amount_rub = order.get("amount_rub", 0)
        order_amount_usdt = order.get("amount_usdt", 0)
        requested_method = order.get("requested_payment_method")
        
        # Проверяем лимиты трейдера
        within_limits = trader_min_amount <= order_amount_rub <= trader_max_amount
        
        # Проверяем совместимость метода оплаты
        method_compatible = not requested_method or requested_method in trader_payment_types
        
        # Проверяем баланс
        has_balance = order_amount_usdt <= available_balance
        
        # Определяем можно ли взять заказ
        can_accept = within_limits and method_compatible and has_balance
        
        # Определяем причину если нельзя
        reason = None
        if not within_limits:
            reason = "out_of_limits"
        elif not method_compatible:
            reason = "no_matching_details"
        elif not has_balance:
            reason = "low_balance"
        
        # Добавляем метаданные
        order["can_accept"] = can_accept
        order["reason"] = reason
        order["required_usdt"] = order_amount_usdt
        order["your_balance"] = available_balance
        order["within_limits"] = within_limits
        order["method_compatible"] = method_compatible
        
        available_orders.append(order)
    
    logger.info(f"Returning {len(available_orders)} available orders for trader {trader['id']}")
    
    return {
        "orders": available_orders,
        "trader_payment_types": list(trader_payment_types),
        "available_balance": available_balance,
        "trader_limits": {
            "min_amount_rub": trader_min_amount,
            "max_amount_rub": trader_max_amount
        },
        "has_deposit": available_balance > 0,
        "has_payment_details": len(payment_details) > 0
    }


@router.post("/trader/take-order/{order_id}")
async def take_order(
    order_id: str,
    payment_detail_id: str = None,
    data: dict = Body(default={}),
    user: dict = Depends(require_trader())
):
    """
    Взять заявку в работу.
    Трейдер выбирает свои реквизиты или вводит вручную для этой заявки.
    """
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Профиль трейдера не найден")
    
    if not trader.get("is_available", False):
        raise HTTPException(status_code=400, detail="Включите режим работы")
    
    # Получаем заявку
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    if order.get("status") != "waiting_requisites":
        raise HTTPException(status_code=400, detail="Заявка уже взята или отменена")
    
    if order.get("trader_id"):
        raise HTTPException(status_code=400, detail="Заявка уже взята другим трейдером")
    
    # Ручной ввод реквизитов
    manual_text = data.get("manual_text")
    
    if manual_text:
        # Ручной ввод реквизитов
        if len(manual_text) > 500:
            raise HTTPException(status_code=400, detail="Максимум 500 символов")
        
        payment_details_for_buyer = {
            "type": "text",
            "manual_text": manual_text.strip()
        }
        payment_detail_id_to_save = None
    elif payment_detail_id:
        # Выбор из сохранённых реквизитов
        payment_detail = await _db.payment_details.find_one({
            "id": payment_detail_id,
            "trader_id": trader["id"],
            "is_active": True
        }, {"_id": 0})
        
        if not payment_detail:
            raise HTTPException(status_code=404, detail="Реквизиты не найдены")
        
        # Проверяем метод оплаты
        requested_method = order.get("requested_payment_method")
        if requested_method and payment_detail.get("payment_type") != requested_method:
            raise HTTPException(status_code=400, detail=f"Нужны реквизиты типа {requested_method}")
        
        # Проверяем лимиты
        amount_rub = order.get("amount_rub", 0)
        if amount_rub < payment_detail.get("min_amount_rub", 0):
            raise HTTPException(status_code=400, detail="Сумма меньше минимальной для этих реквизитов")
        if amount_rub > payment_detail.get("max_amount_rub", float('inf')):
            raise HTTPException(status_code=400, detail="Сумма больше максимальной для этих реквизитов")
        
        # Формируем payment_details для покупателя
        payment_details_for_buyer = {
            "type": payment_detail.get("payment_type"),
            "bank_name": payment_detail.get("bank_name"),
            "card_number": payment_detail.get("card_number"),
            "phone_number": payment_detail.get("phone_number"),
            "holder_name": payment_detail.get("holder_name"),
            "comment": order.get("external_id") or order.get("id")
        }
        payment_detail_id_to_save = payment_detail_id
    else:
        raise HTTPException(status_code=400, detail="Укажите реквизиты или введите вручную")
    
    # Проверяем баланс
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    available_balance = wallet.get("available_balance_usdt", 0) if wallet else 0
    amount_usdt = order.get("amount_usdt", 0)
    
    if amount_usdt > available_balance:
        raise HTTPException(status_code=400, detail="Недостаточно USDT на балансе")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Получаем payment_method для обновления
    payment_method = payment_details_for_buyer.get("type", "text")
    
    # Обновляем заявку
    await _db.orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "trader_id": trader["id"],
                "payment_method": payment_method,
                "payment_details": payment_details_for_buyer,
                "payment_details_id": payment_detail_id_to_save,
                "status": "waiting_buyer_confirmation",
                "taken_at": now,
                "updated_at": now
            }
        }
    )
    
    # Обновляем invoice если есть
    await _db.merchant_invoices.update_one(
        {"id": order_id},
        {
            "$set": {
                "trader_id": trader["id"],
                "payment_details_id": payment_detail_id_to_save,
                "payment_details": payment_details_for_buyer,
                "status": "pending",
                "updated_at": now
            }
        }
    )
    
    # Блокируем USDT трейдера (с округлением до 4 знаков для избежания float погрешности)
    amount_usdt_rounded = round(amount_usdt, 4)
    await _db.wallets.update_one(
        {"user_id": user["id"]},
        {
            "$inc": {
                "available_balance_usdt": -amount_usdt_rounded,
                "locked_balance_usdt": amount_usdt_rounded
            }
        }
    )
    
    return {
        "success": True,
        "order_id": order_id,
        "status": "waiting_buyer_confirmation",
        "message": "Заявка взята в работу. Реквизиты отправлены покупателю."
    }


@router.post("/trader/orders/{order_id}/confirm")
async def confirm_order_payment(
    order_id: str,
    user: dict = Depends(require_trader())
):
    """
    Трейдер подтверждает получение оплаты.
    
    Финансовая логика:
    1. Locked USDT трейдера → распределяется
    2. Комиссия трейдера (fee_percent от original) → Earned
    3. Мерчант получает свою долю → Available
    4. Платформа получает накрутку + маркер
    """
    from financial_logic import calculate_completion_distribution
    
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Профиль трейдера не найден")
    
    # Получаем заказ
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем что заказ принадлежит этому трейдеру
    if order.get("trader_id") != trader["id"]:
        raise HTTPException(status_code=403, detail="Этот заказ не принадлежит вам")
    
    # Проверяем статус - разрешаем подтверждение в большинстве статусов
    # Трейдер может завершить сделку в пользу покупателя в любой момент
    forbidden_statuses = ["completed", "cancelled", "failed", "expired"]
    if order.get("status") in forbidden_statuses:
        raise HTTPException(status_code=400, detail=f"Нельзя подтвердить заказ со статусом: {order.get('status')}")
    
    # Получаем настройки мерчанта для fee_model
    merchant = await _db.merchants.find_one({"id": order.get("merchant_id")}, {"_id": 0})
    fee_model = merchant.get("fee_model", "customer_pays") if merchant else "customer_pays"
    
    # Если комиссия была сохранена при создании заказа - используем её
    if order.get("merchant_fee_percent") is not None:
        merchant_fee_percent = order.get("merchant_fee_percent")
        logger.info(f"Using saved merchant_fee_percent from order: {merchant_fee_percent}%")
    else:
        merchant_fee_percent = merchant.get("total_fee_percent", 30.0) if merchant else 30.0
    
    # Получаем сумму заказа
    original_amount_rub = order.get("original_amount_rub", order.get("amount_rub_original", order.get("amount_rub", 0)))
    payment_method = order.get("payment_method", order.get("requested_payment_method", "card"))
    
    # Для Типа 1 (merchant_pays) используем гибкие комиссии по методам оплаты
    # Только если комиссия НЕ была сохранена при создании
    if fee_model == "merchant_pays" and merchant and order.get("merchant_fee_percent") is None:
        method_commissions = merchant.get("payment_method_commissions", [])
        
        # Ищем комиссию для данного метода оплаты
        for method_config in method_commissions:
            if method_config.get("payment_method") == payment_method:
                # Ищем подходящий интервал по сумме
                for interval in method_config.get("intervals", []):
                    if interval.get("min_amount", 0) <= original_amount_rub <= interval.get("max_amount", float('inf')):
                        merchant_fee_percent = interval.get("percent", merchant_fee_percent)
                        logger.info(f"Using method commission: {payment_method} - {merchant_fee_percent}% for {original_amount_rub}₽")
                        break
                break
        
        # Также проверяем новый формат method_commissions
        method_commissions_new = merchant.get("method_commissions", {})
        if payment_method in method_commissions_new:
            method_config = method_commissions_new[payment_method]
            for interval in method_config.get("intervals", []):
                if interval.get("min_amount", 0) <= original_amount_rub <= interval.get("max_amount", float('inf')):
                    merchant_fee_percent = interval.get("percent", merchant_fee_percent)
                    logger.info(f"Using new method commission: {payment_method} - {merchant_fee_percent}% for {original_amount_rub}₽")
                    break
    
    # Получаем настройки комиссии трейдера
    trader_fee_percent = trader.get("fee_percent", trader.get("default_fee_percent", 10.0))
    
    # Проверяем интервалы комиссий трейдера
    fee_intervals = trader.get("fee_intervals", [])
    
    for interval in fee_intervals:
        if interval.get("min_amount", 0) <= original_amount_rub <= interval.get("max_amount", float('inf')):
            trader_fee_percent = interval.get("percent", trader_fee_percent)
            logger.info(f"Using trader interval: {interval.get('min_amount')}-{interval.get('max_amount')} → {trader_fee_percent}%")
            break
    
    # Используем курс из заказа! (тот же что при создании/взятии)
    usdt_rate = order.get("exchange_rate")
    if not usdt_rate:
        # Fallback на единый источник курса
        usdt_rate = await get_current_rate()
    
    # Расчёт распределения
    total_amount_rub = order.get("amount_rub", 0)
    marker_rub = order.get("marker", order.get("marker_rub", order.get("marker_amount_rub", 0)))
    
    try:
        distribution = calculate_completion_distribution(
            original_amount_rub=original_amount_rub,
            total_amount_rub=total_amount_rub,
            marker_rub=marker_rub,
            merchant_fee_percent=merchant_fee_percent,
            trader_fee_percent=trader_fee_percent,
            fee_model=fee_model,
            usdt_rate=usdt_rate
        )
    except Exception as e:
        logger.error(f"Error calculating distribution for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта распределения: {str(e)}")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Сумма которая была заблокирована (из заказа)
    order_amount_usdt = order.get("amount_usdt", 0)
    
    # 1. ТРЕЙДЕР: разблокируем ВСЁ что было заблокировано, добавляем earned
    await _db.wallets.update_one(
        {"user_id": user["id"]},
        {"$inc": {
            "locked_balance_usdt": -round(order_amount_usdt, 4),  # Разблокируем ВСЮ сумму
            "earned_balance_usdt": round(distribution.trader_earns_usdt, 4)
        }}
    )
    
    # Исправляем погрешность округления - locked не может быть отрицательным или слишком маленьким
    wallet_check = await _db.wallets.find_one(
        {"user_id": user["id"]}, 
        {"_id": 0, "locked_balance_usdt": 1}
    )
    locked_val = wallet_check.get("locked_balance_usdt", 0) if wallet_check else 0
    # Если locked < 0 или очень маленькое значение (погрешность), обнуляем
    if locked_val < 0 or (0 < locked_val < 0.01):
        await _db.wallets.update_one(
            {"user_id": user["id"]},
            {"$set": {"locked_balance_usdt": 0}}
        )
    
    logger.info(f"Trader {trader['id']}: locked -{order_amount_usdt}, earned +{distribution.trader_earns_usdt}")
    
    # 2. МЕРЧАНТ: зачисляем на баланс
    if merchant and merchant.get("user_id"):
        await _db.wallets.update_one(
            {"user_id": merchant["user_id"]},
            {"$inc": {"available_balance_usdt": distribution.merchant_receives_usdt}},
            upsert=True
        )
        
        # Обновляем статистику мерчанта
        await _db.merchants.update_one(
            {"id": merchant["id"]},
            {"$inc": {
                "total_volume_usdt": distribution.merchant_receives_usdt,
                "total_orders_completed": 1
            }}
        )
        logger.info(f"Merchant {merchant['id']}: +{distribution.merchant_receives_usdt} USDT")
    
    # 3. ПЛАТФОРМА: записываем доход
    await _db.platform_income.insert_one({
        "id": generate_id("pinc_"),
        "order_id": order_id,
        "amount_rub": distribution.platform_receives_rub,
        "amount_usdt": distribution.platform_receives_usdt,
        "fee_model": fee_model,
        "created_at": now
    })
    
    # 4. Обновляем статистику трейдера
    await _db.traders.update_one(
        {"id": trader["id"]},
        {"$inc": {
            "total_deals": 1,
            "successful_deals": 1,
            "total_volume_rub": total_amount_rub,
            "total_commission_usdt": distribution.trader_earns_usdt
        }}
    )
    
    # 5. Обновляем заказ
    await _db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "completed",
            "completed_at": now,
            "updated_at": now,
            "merchant_receives_usdt": distribution.merchant_receives_usdt,
            "trader_commission_usdt": distribution.trader_earns_usdt,
            "platform_commission_usdt": distribution.platform_receives_usdt,
            "completion_distribution": distribution.to_dict()
        }}
    )
    
    # 6. Обновляем invoice если есть
    await _db.merchant_invoices.update_one(
        {"id": order_id},
        {"$set": {
            "status": "completed",
            "paid_at": now,
            "updated_at": now
        }}
    )
    
    # Начисляем реферальные бонусы (от комиссии трейдера)
    await process_referral_earnings(user["id"], distribution.trader_earns_usdt, order_id)
    
    logger.info(f"Order {order_id} completed by trader {trader['id']}. Distribution: merchant={distribution.merchant_receives_usdt}, trader={distribution.trader_earns_usdt}, platform={distribution.platform_receives_usdt}")
    
    # Уведомляем участников о завершении сделки
    if _notify_order_completed:
        import asyncio
        order["status"] = "completed"
        asyncio.create_task(_notify_order_completed(order, distribution.trader_earns_usdt))
    
    # Отправляем webhook мерчанту
    from routers.invoice_api import send_webhook_notification
    import asyncio
    asyncio.create_task(send_webhook_notification(order_id, "paid", {
        "merchant_receives_usdt": distribution.merchant_receives_usdt
    }))
    
    return {
        "success": True,
        "order_id": order_id,
        "status": "completed",
        "distribution": {
            "merchant_receives_usdt": distribution.merchant_receives_usdt,
            "trader_earns_usdt": distribution.trader_earns_usdt,
            "platform_receives_usdt": distribution.platform_receives_usdt
        },
        "message": "Сделка успешно завершена! Комиссия начислена в заработанное."
    }



@router.post("/trader/orders/{order_id}/resolve-for-buyer")
async def resolve_dispute_for_buyer(
    order_id: str,
    user: dict = Depends(require_trader())
):
    """
    Трейдер закрывает спор в пользу покупателя.
    Это эквивалентно подтверждению сделки - средства распределяются как обычно.
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Получаем трейдера
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Профиль трейдера не найден")
    
    # Получаем заказ
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем что это заказ этого трейдера
    if trader["id"] != order.get("trader_id"):
        raise HTTPException(status_code=403, detail="Нет доступа к этому заказу")
    
    # Проверяем что заказ в статусе спора
    if order.get("status") != "disputed":
        raise HTTPException(status_code=400, detail="Заказ не в статусе спора")
    
    # Получаем спор
    dispute = await _db.disputes.find_one({"order_id": order_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    # Импортируем финансовую логику
    from financial_logic import calculate_completion_distribution
    
    # Получаем настройки мерчанта
    merchant = await _db.merchants.find_one({"id": order.get("merchant_id")}, {"_id": 0})
    fee_model = merchant.get("fee_model", "customer_pays") if merchant else "customer_pays"
    merchant_fee_percent = merchant.get("total_fee_percent", 30.0) if merchant else 30.0
    
    # Получаем настройки комиссии трейдера
    trader_fee_percent = trader.get("fee_percent", trader.get("default_fee_percent", 10.0))
    
    # Проверяем интервалы комиссий трейдера
    original_amount_rub = order.get("original_amount_rub", order.get("amount_rub_original", order.get("amount_rub", 0)))
    fee_intervals = trader.get("fee_intervals", [])
    for interval in fee_intervals:
        if interval.get("min_amount", 0) <= original_amount_rub <= interval.get("max_amount", float('inf')):
            trader_fee_percent = interval.get("percent", trader_fee_percent)
            logger.info(f"Using trader interval: {interval.get('min_amount')}-{interval.get('max_amount')} → {trader_fee_percent}%")
            break
    
    # Получаем курс из заказа или единый источник
    usdt_rate = order.get("exchange_rate")
    if not usdt_rate:
        usdt_rate = await get_current_rate()
    
    # Получаем суммы из заказа
    total_amount_rub = order.get("amount_rub", 0)
    marker_rub = order.get("marker", order.get("marker_rub", order.get("marker_amount_rub", 0)))
    order_amount_usdt = order.get("amount_usdt", 0)
    
    try:
        # Рассчитываем распределение
        distribution = calculate_completion_distribution(
            original_amount_rub=original_amount_rub,
            total_amount_rub=total_amount_rub,
            marker_rub=marker_rub,
            merchant_fee_percent=merchant_fee_percent,
            trader_fee_percent=trader_fee_percent,
            fee_model=fee_model,
            usdt_rate=usdt_rate
        )
    except Exception as e:
        logger.error(f"Error calculating distribution for dispute resolution {order_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта распределения: {str(e)}")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # 1. ТРЕЙДЕР: разблокируем ВСЁ что было заблокировано, добавляем earned
    await _db.wallets.update_one(
        {"user_id": user["id"]},
        {"$inc": {
            "locked_balance_usdt": -round(order_amount_usdt, 4),
            "earned_balance_usdt": round(distribution.trader_earns_usdt, 4)
        }}
    )
    
    # Исправляем погрешность округления - locked не может быть отрицательным
    wallet_check = await _db.wallets.find_one(
        {"user_id": user["id"]}, 
        {"_id": 0, "locked_balance_usdt": 1}
    )
    locked_val = wallet_check.get("locked_balance_usdt", 0) if wallet_check else 0
    if locked_val < 0 or (0 < locked_val < 0.01):
        await _db.wallets.update_one(
            {"user_id": user["id"]},
            {"$set": {"locked_balance_usdt": 0}}
        )
    
    logger.info(f"Trader {trader['id']}: locked -{order_amount_usdt}, earned +{distribution.trader_earns_usdt}")
    
    # 2. МЕРЧАНТ: зачисляем на баланс
    if merchant and merchant.get("user_id"):
        await _db.wallets.update_one(
            {"user_id": merchant["user_id"]},
            {"$inc": {"available_balance_usdt": distribution.merchant_receives_usdt}},
            upsert=True
        )
        
        # Обновляем статистику мерчанта
        await _db.merchants.update_one(
            {"id": merchant["id"]},
            {"$inc": {
                "total_volume_usdt": distribution.merchant_receives_usdt,
                "total_orders_completed": 1
            }}
        )
        logger.info(f"Merchant {merchant['id']}: +{distribution.merchant_receives_usdt} USDT")
    
    # 3. ПЛАТФОРМА: записываем доход
    await _db.platform_income.insert_one({
        "id": generate_id("pinc_"),
        "order_id": order_id,
        "amount_rub": distribution.platform_receives_rub,
        "amount_usdt": distribution.platform_receives_usdt,
        "fee_model": fee_model,
        "source": "dispute_resolution_by_trader",
        "created_at": now
    })
    
    # 4. Обновляем статистику трейдера
    await _db.traders.update_one(
        {"id": trader["id"]},
        {"$inc": {
            "total_deals": 1,
            "successful_deals": 1,
            "total_volume_rub": total_amount_rub,
            "total_commission_usdt": distribution.trader_earns_usdt
        }}
    )
    
    # 5. Обновляем статус заказа
    await _db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "completed",
            "completed_at": now,
            "updated_at": now,
            "merchant_receives_usdt": distribution.merchant_receives_usdt,
            "trader_commission_usdt": distribution.trader_earns_usdt,
            "platform_commission_usdt": distribution.platform_receives_usdt,
            "resolved_by": "trader",
            "completion_distribution": distribution.to_dict()
        }}
    )
    
    # 6. Обновляем invoice если есть
    await _db.merchant_invoices.update_one(
        {"id": order_id},
        {"$set": {
            "status": "completed",
            "paid_at": now,
            "updated_at": now
        }}
    )
    
    # 7. Закрываем спор
    short_order_id = order_id.split('_')[-1] if '_' in order_id else order_id[-6:]
    
    await _db.disputes.update_one(
        {"id": dispute["id"]},
        {"$set": {
            "status": "resolved",
            "resolution": "completed_by_trader",
            "resolution_comment": "Трейдер подтвердил получение оплаты",
            "resolved_at": now,
            "resolved_by": trader["id"]
        }}
    )
    
    # Добавляем системное сообщение в чат
    system_message = {
        "id": f"MSG-{secrets.token_hex(8).upper()}",
        "dispute_id": dispute["id"],
        "sender_role": "admin",
        "sender_id": "system",
        "sender_name": "Система",
        "text": f"✅ Спор по заказу #{short_order_id} закрыт трейдером в пользу покупателя.\n\nСделка завершена успешно.\n• Мерчант получил: {distribution.merchant_receives_usdt:.2f} USDT\n• Трейдер заработал: {distribution.trader_earns_usdt:.2f} USDT",
        "created_at": now
    }
    await _db.dispute_messages.insert_one(system_message)
    
    logger.info(f"Dispute {dispute['id']} resolved by trader {trader['id']} for order {order_id}")
    
    return {
        "success": True,
        "message": "Спор закрыт в пользу покупателя. Комиссия начислена.",
        "distribution": {
            "merchant_receives_usdt": distribution.merchant_receives_usdt,
            "trader_earns_usdt": distribution.trader_earns_usdt,
            "platform_receives_usdt": distribution.platform_receives_usdt
        }
    }



@router.get("/trader/analytics")
async def get_trader_analytics(
    period: str = "week",
    user: dict = Depends(require_trader())
):
    """Получить аналитику трейдера за период"""
    trader = await _db.traders.find_one({"user_id": user["id"]}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    # Определяем диапазон дат
    now = datetime.now(timezone.utc)
    if period == "week":
        days = 7
    elif period == "month":
        days = 30
    elif period == "year":
        days = 365
    else:
        days = 7
    
    from datetime import timedelta
    start_date = (now - timedelta(days=days)).isoformat()
    
    # Получаем заказы за период
    orders = await _db.orders.find({
        "trader_id": trader["id"],
        "created_at": {"$gte": start_date}
    }, {"_id": 0}).to_list(10000)
    
    # Фильтруем завершённые и отменённые
    completed_orders = [o for o in orders if o.get("status") == "completed"]
    cancelled_orders = [o for o in orders if o.get("status") in ["cancelled", "expired"]]
    
    # Считаем статистику
    total_earnings_usdt = sum(o.get("trader_commission_usdt", 0) or 0 for o in completed_orders)
    total_volume_rub = sum(o.get("amount_rub", 0) or 0 for o in completed_orders)
    
    # Курс для конвертации
    exchange_rate = await get_current_rate()
    total_earnings_rub = total_earnings_usdt * exchange_rate
    
    # Средний чек
    avg_deal_rub = total_volume_rub / len(completed_orders) if completed_orders else 0
    
    # Успешность
    total_deals = len(completed_orders) + len(cancelled_orders)
    success_rate = (len(completed_orders) / total_deals * 100) if total_deals > 0 else 0
    
    # Данные по дням для графиков
    daily_data = {}
    for o in completed_orders:
        date = o.get("completed_at", o.get("created_at", ""))[:10]
        if date:
            if date not in daily_data:
                daily_data[date] = {"earnings_usdt": 0, "volume_rub": 0}
            daily_data[date]["earnings_usdt"] += o.get("trader_commission_usdt", 0) or 0
            daily_data[date]["volume_rub"] += o.get("amount_rub", 0) or 0
    
    # Сортируем по дате
    daily_earnings = [
        {"date": d, "earnings_usdt": v["earnings_usdt"]}
        for d, v in sorted(daily_data.items())
    ]
    daily_volume = [
        {"date": d, "volume_rub": v["volume_rub"]}
        for d, v in sorted(daily_data.items())
    ]
    
    return {
        "earnings": {
            "total_usdt": total_earnings_usdt,
            "total_rub": total_earnings_rub
        },
        "volume": {
            "total_rub": total_volume_rub
        },
        "deals": {
            "total": total_deals,
            "completed": len(completed_orders),
            "cancelled": len(cancelled_orders)
        },
        "success_rate": success_rate,
        "avg_deal_rub": avg_deal_rub,
        "daily_earnings": daily_earnings,
        "daily_volume": daily_volume,
        "period": period
    }
