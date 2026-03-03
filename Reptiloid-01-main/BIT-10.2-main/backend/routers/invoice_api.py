"""
BITARBITR P2P Platform - Invoice API для мерчантов (v1)
REST API для приема рублевых платежей через p2p USDT

Endpoints:
- POST /v1/invoice/create - создание инвойса
- GET /v1/invoice/status - проверка статуса
- POST /v1/invoice/callback (внутренний) - отправка callback мерчанту
"""
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import secrets
import hashlib
import hmac
import httpx
import asyncio
import logging
import time

router = APIRouter(prefix="/v1/invoice", tags=["Invoice API v1"])
logger = logging.getLogger(__name__)

# Глобальные зависимости
_db = None
_generate_id = None
_calculate_usdt_amount = None
_manager = None  # WebSocket manager
_site_url = "https://api.example.com"
_notify_new_order = None

# Retry intervals для callback (в секундах)
CALLBACK_RETRY_INTERVALS = [60, 300, 900, 3600, 7200, 14400, 43200, 86400]  # 1m, 5m, 15m, 1h, 2h, 4h, 12h, 24h

# ================== RATE LIMITING ==================
# Rate limits per merchant per minute
RATE_LIMITS = {
    "create": 60,      # 60 создание инвойсов в минуту
    "status": 120,     # 120 проверок статуса в минуту
    "transactions": 30  # 30 запросов списка в минуту
}

# In-memory rate limit storage (per merchant)
_rate_limit_storage = defaultdict(lambda: defaultdict(list))


def check_rate_limit(merchant_id: str, endpoint: str) -> bool:
    """
    Проверка rate limit для мерчанта
    Возвращает True если лимит не превышен
    """
    limit = RATE_LIMITS.get(endpoint, 60)
    now = time.time()
    window = 60  # 1 минута
    
    # Очищаем старые записи
    _rate_limit_storage[merchant_id][endpoint] = [
        t for t in _rate_limit_storage[merchant_id][endpoint]
        if now - t < window
    ]
    
    # Проверяем лимит
    if len(_rate_limit_storage[merchant_id][endpoint]) >= limit:
        return False
    
    # Записываем новый запрос
    _rate_limit_storage[merchant_id][endpoint].append(now)
    return True


def get_rate_limit_info(merchant_id: str, endpoint: str) -> dict:
    """Получить информацию о rate limit"""
    limit = RATE_LIMITS.get(endpoint, 60)
    now = time.time()
    window = 60
    
    current = len([
        t for t in _rate_limit_storage[merchant_id][endpoint]
        if now - t < window
    ])
    
    return {
        "limit": limit,
        "remaining": max(0, limit - current),
        "reset_in": int(window - (now % window))
    }


def init_router(database, generate_id_func, calculate_usdt_func, ws_manager=None, site_url: str = None, notify_new_order_func=None):
    """Инициализация роутера с зависимостями"""
    global _db, _generate_id, _calculate_usdt_amount, _manager, _site_url, _notify_new_order
    _db = database
    _generate_id = generate_id_func
    _calculate_usdt_amount = calculate_usdt_func
    _manager = ws_manager
    if site_url:
        _site_url = site_url
    _notify_new_order = notify_new_order_func


# ================== WEBHOOK NOTIFICATION SYSTEM ==================

async def send_webhook_notification(order_id: str, new_status: str, extra_data: dict = None):
    """
    Отправляет webhook-уведомление мерчанту при изменении статуса заказа.
    
    Args:
        order_id: ID заказа
        new_status: Новый статус (paid, completed, cancelled, expired, dispute)
        extra_data: Дополнительные данные для callback (amount, dispute_url и т.д.)
    """
    if _db is None:
        logger.error("Database not initialized for webhook")
        return
    
    try:
        # Получаем заказ
        order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            logger.warning(f"Order {order_id} not found for webhook")
            return
        
        callback_url = order.get("callback_url")
        if not callback_url:
            logger.info(f"No callback_url for order {order_id}")
            return
        
        # Получаем мерчанта для подписи
        merchant = await _db.merchants.find_one({"id": order.get("merchant_id")}, {"_id": 0})
        if not merchant:
            logger.warning(f"Merchant not found for order {order_id}")
            return
        
        secret_key = merchant.get("secret_key") or merchant.get("api_secret", "")
        
        # Формируем payload
        callback_data = {
            "order_id": order.get("external_id", order_id),
            "payment_id": order_id,
            "status": new_status,
            "amount": order.get("original_amount_rub") or order.get("amount_rub"),
            "amount_usdt": order.get("amount_usdt"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Добавляем extra_data если есть
        if extra_data:
            callback_data.update(extra_data)
        
        # Добавляем dispute_url если статус dispute
        if new_status in ["dispute", "disputed"] and order.get("dispute_token"):
            callback_data["dispute_url"] = f"{_site_url}/dispute/{order['dispute_token']}"
        
        # Генерируем подпись
        callback_data["sign"] = generate_signature(callback_data, secret_key)
        
        # Логируем отправку
        logger.info(f"Sending webhook for order {order_id}: status={new_status}")
        
        # Сохраняем webhook в историю
        webhook_record = {
            "id": _generate_id("whk"),
            "order_id": order_id,
            "merchant_id": order.get("merchant_id"),
            "callback_url": callback_url,
            "payload": callback_data,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await _db.webhook_history.insert_one(webhook_record)
        
        # Отправляем callback
        success = await send_callback(callback_url, callback_data, 0)
        
        # Обновляем статус в истории
        await _db.webhook_history.update_one(
            {"id": webhook_record["id"]},
            {"$set": {
                "status": "delivered" if success else "retry_scheduled",
                "delivered_at": datetime.now(timezone.utc).isoformat() if success else None
            }}
        )
        
    except Exception as e:
        logger.error(f"Error sending webhook for order {order_id}: {e}")


# ================== MODELS ==================

class InvoiceCreateRequest(BaseModel):
    """Запрос на создание инвойса"""
    merchant_id: str = Field(..., description="ID мерчанта в системе")
    order_id: str = Field(..., description="Уникальный ID заказа в системе мерчанта")
    amount: float = Field(..., gt=0, description="Сумма к оплате в рублях")
    currency: str = Field(default="RUB", description="Код валюты")
    user_id: Optional[str] = Field(None, description="ID пользователя в системе мерчанта")
    callback_url: str = Field(..., description="URL для callback уведомлений")
    description: Optional[str] = Field(None, description="Описание платежа")
    payment_method: Optional[str] = Field(None, description="Метод оплаты: card, sbp, sim, mono_bank, sng_sbp, sng_card, qr_code")
    sign: str = Field(..., description="HMAC-SHA256 подпись запроса")


class InvoiceCreateResponse(BaseModel):
    """Ответ на создание инвойса"""
    status: str
    payment_id: str
    payment_url: str
    details: Dict[str, Any]


class InvoiceStatusRequest(BaseModel):
    """Запрос статуса инвойса"""
    merchant_id: str
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    sign: str


class InvoiceStatusResponse(BaseModel):
    """Ответ со статусом инвойса"""
    status: str
    data: Dict[str, Any]


class CallbackPayload(BaseModel):
    """Payload для callback"""
    order_id: str
    payment_id: str
    status: str
    amount: float
    sign: str


class ErrorResponse(BaseModel):
    """Ответ с ошибкой"""
    status: str = "error"
    code: str
    message: str


# ================== SIGNATURE UTILS ==================

def generate_signature(data: Dict[str, Any], secret_key: str) -> str:
    """
    Генерация HMAC-SHA256 подписи
    Алгоритм: сортировка параметров по алфавиту, конкатенация key=value&, добавление secret_key
    """
    # Исключаем поле sign из данных для подписи
    sign_data = {}
    for k, v in data.items():
        if k == 'sign' or v is None:
            continue
        # Нормализуем числа - убираем .0 у целых
        if isinstance(v, float) and v == int(v):
            v = int(v)
        sign_data[k] = v
    
    # Сортируем по ключам и формируем строку
    sorted_params = sorted(sign_data.items())
    sign_string = '&'.join(f"{k}={v}" for k, v in sorted_params)
    sign_string += secret_key
    
    # HMAC-SHA256
    signature = hmac.new(
        secret_key.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_signature(data: Dict[str, Any], provided_sign: str, secret_key: str) -> bool:
    """Проверка подписи"""
    expected_sign = generate_signature(data, secret_key)
    return hmac.compare_digest(expected_sign.lower(), provided_sign.lower())


def generate_dispute_token() -> str:
    """Генерация уникального токена для спора"""
    return secrets.token_urlsafe(32)


# ================== CALLBACK SYSTEM ==================

async def send_callback(callback_url: str, payload: Dict[str, Any], retry_count: int = 0):
    """
    Отправка callback мерчанту с retry логикой
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                callback_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                try:
                    resp_data = response.json()
                    if resp_data.get("status") == "ok":
                        logger.info(f"Callback успешно доставлен: {callback_url}")
                        return True
                except Exception:
                    pass
                
            logger.warning(f"Callback неудачен (HTTP {response.status_code}): {callback_url}")
            
    except Exception as e:
        logger.error(f"Callback ошибка: {e}")
    
    # Планируем retry если не превышен лимит
    if retry_count < len(CALLBACK_RETRY_INTERVALS):
        delay = CALLBACK_RETRY_INTERVALS[retry_count]
        logger.info(f"Планируем retry #{retry_count + 1} через {delay}с для {callback_url}")
        
        # Сохраняем задачу на retry в БД
        await _db.callback_queue.insert_one({
            "id": _generate_id("cbk"),
            "callback_url": callback_url,
            "payload": payload,
            "retry_count": retry_count + 1,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    else:
        logger.error(f"Callback превышен лимит retry для {callback_url}")
        # Сохраняем как failed
        await _db.callback_queue.insert_one({
            "id": _generate_id("cbk"),
            "callback_url": callback_url,
            "payload": payload,
            "retry_count": retry_count,
            "status": "failed",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    return False


async def process_callback_queue():
    """Фоновая задача обработки очереди callback"""
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            # Находим задачи готовые к выполнению
            pending_tasks = await _db.callback_queue.find({
                "status": "pending",
                "scheduled_at": {"$lte": now}
            }).to_list(100)
            
            for task in pending_tasks:
                # Помечаем как processing
                await _db.callback_queue.update_one(
                    {"id": task["id"]},
                    {"$set": {"status": "processing"}}
                )
                
                success = await send_callback(
                    task["callback_url"],
                    task["payload"],
                    task["retry_count"]
                )
                
                if success:
                    await _db.callback_queue.update_one(
                        {"id": task["id"]},
                        {"$set": {"status": "completed", "completed_at": now}}
                    )
                else:
                    # Удаляем текущую задачу, новая создана в send_callback
                    await _db.callback_queue.delete_one({"id": task["id"]})
                    
        except Exception as e:
            logger.error(f"Ошибка обработки callback queue: {e}")
        
        await asyncio.sleep(30)  # Проверяем каждые 30 секунд


# ================== ENDPOINTS ==================

# Стандартные способы оплаты
STANDARD_PAYMENT_METHODS = [
    {"id": "card", "name": "Банковская карта", "description": "Visa, Mastercard, МИР"},
    {"id": "sbp", "name": "СБП", "description": "Система быстрых платежей"},
    {"id": "sim", "name": "Мобильный счёт", "description": "Пополнение SIM"},
    {"id": "mono_bank", "name": "Monobank", "description": "Украина"},
    {"id": "sng_sbp", "name": "СБП СНГ", "description": "Казахстан, Беларусь"},
    {"id": "sng_card", "name": "Карта СНГ", "description": "Банки СНГ"},
    {"id": "qr_code", "name": "QR-код", "description": "Сканирование QR"},
]


@router.get("/payment-methods")
async def get_payment_methods(
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """
    Получить список доступных способов оплаты для мерчанта
    
    Используйте этот endpoint чтобы показать покупателю выбор способа оплаты
    на вашем сайте ПЕРЕД созданием инвойса.
    
    Возвращает список методов с id, названием и описанием.
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Проверяем API ключ
    merchant = await _db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    # Для fee_model = "customer_pays" возвращаем все методы
    fee_model = merchant.get("fee_model", "customer_pays")
    
    if fee_model == "customer_pays":
        # Все методы доступны
        return {
            "status": "success",
            "payment_methods": STANDARD_PAYMENT_METHODS
        }
    else:
        # Для "merchant_pays" - только настроенные методы
        method_commissions = merchant.get("method_commissions", {})
        payment_method_commissions = merchant.get("payment_method_commissions", [])
        
        available_methods = []
        
        # Проверяем новый формат (dict)
        for method in STANDARD_PAYMENT_METHODS:
            method_id = method["id"]
            
            # Проверяем в новом формате
            if method_id in method_commissions:
                config = method_commissions[method_id]
                if config.get("enabled", True):
                    available_methods.append(method)
                    continue
            
            # Проверяем в старом формате (array)
            for old_config in payment_method_commissions:
                if old_config.get("payment_method") == method_id:
                    available_methods.append(method)
                    break
        
        # Если ничего не настроено - возвращаем все методы
        if not available_methods:
            available_methods = STANDARD_PAYMENT_METHODS
        
        return {
            "status": "success",
            "payment_methods": available_methods
        }


@router.post("/create", response_model=InvoiceCreateResponse)
async def create_invoice(
    request: InvoiceCreateRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(..., alias="X-Api-Key"),
    http_request: Request = None
):
    """
    Создание инвойса для пополнения
    
    Мерчант запрашивает реквизиты для пополнения счета клиента.
    Возвращает payment_url и реквизиты для перевода.
    
    Rate limit: 60 запросов в минуту
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # 1. Проверяем API ключ
    merchant = await _db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    # 2. Проверяем rate limit
    if not check_rate_limit(merchant["id"], "create"):
        rate_info = get_rate_limit_info(merchant["id"], "create")
        raise HTTPException(status_code=429, detail={
            "status": "error",
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Превышен лимит запросов ({rate_info['limit']}/мин). Повторите через {rate_info['reset_in']} сек."
        })
    
    if merchant.get("id") != request.merchant_id:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "MERCHANT_MISMATCH",
            "message": "Merchant ID не соответствует API ключу"
        })
    
    # 3. Проверяем подпись
    sign_data = {
        "merchant_id": request.merchant_id,
        "order_id": request.order_id,
        "amount": request.amount,
        "currency": request.currency,
        "user_id": request.user_id,
        "callback_url": request.callback_url,
        "payment_method": request.payment_method
    }
    
    secret_key = merchant.get("secret_key") or merchant.get("api_secret", "")
    
    if not verify_signature(sign_data, request.sign, secret_key):
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_SIGNATURE",
            "message": "Неверная подпись запроса"
        })
    
    # 4. Проверяем уникальность order_id
    existing = await _db.merchant_invoices.find_one({
        "merchant_id": request.merchant_id,
        "order_id": request.order_id
    })
    if existing:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "DUPLICATE_ORDER_ID",
            "message": "Заказ с таким order_id уже существует"
        })
    
    # 4. Проверяем минимальную сумму
    min_amount = 100.0  # Минимум 100 рублей
    if request.amount < min_amount:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_AMOUNT",
            "message": f"Сумма меньше минимальной ({min_amount} RUB)"
        })
    
    # 5. Рассчитываем USDT
    usdt_amount, exchange_rate = await _calculate_usdt_amount(request.amount)
    
    # 6. Валидация метода оплаты
    valid_payment_methods = ['card', 'sbp', 'sim', 'mono_bank', 'sng_sbp', 'sng_card', 'qr_code']
    requested_method = request.payment_method
    
    if requested_method and requested_method not in valid_payment_methods:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_PAYMENT_METHOD",
            "message": f"Недопустимый метод оплаты. Доступны: {', '.join(valid_payment_methods)}"
        })
    
    # 6.1 Проверяем что у мерчанта настроен этот метод оплаты
    # Для fee_model = "customer_pays" - все методы доступны без ограничений
    # Для fee_model = "merchant_pays" - проверяем настройки метода у мерчанта
    
    fee_model = merchant.get("fee_model", "customer_pays")
    method_fee_percent = None
    
    if requested_method:
        if fee_model == "customer_pays":
            # Тип 2: Покупатель платит комиссию - все методы доступны
            # Используем общую комиссию мерчанта
            method_fee_percent = merchant.get("total_fee_percent", 30.0)
        else:
            # Тип 1: Мерчант платит комиссию - проверяем настройки метода
            # Поддерживаем оба формата: новый (method_commissions) и старый (payment_method_commissions)
            method_commissions_new = merchant.get("method_commissions", {})
            payment_method_commissions_old = merchant.get("payment_method_commissions", [])
            
            method_found = False
            
            # Сначала проверяем новый формат (object)
            if requested_method in method_commissions_new:
                method_config = method_commissions_new[requested_method]
                if method_config.get("enabled", True):  # По умолчанию включен если есть
                    method_found = True
                    intervals = method_config.get("intervals", [])
                    for interval in intervals:
                        min_amt = interval.get("min_amount", 0)
                        max_amt = interval.get("max_amount", float('inf'))
                        if min_amt <= request.amount <= max_amt:
                            method_fee_percent = interval.get("percent")
                            break
            
            # Если не найден в новом формате, проверяем старый (array)
            if not method_found and payment_method_commissions_old:
                for method_config in payment_method_commissions_old:
                    if method_config.get("payment_method") == requested_method:
                        method_found = True
                        intervals = method_config.get("intervals", [])
                        for interval in intervals:
                            min_amt = interval.get("min_amount", 0)
                            max_amt = interval.get("max_amount", float('inf'))
                            if min_amt <= request.amount <= max_amt:
                                method_fee_percent = interval.get("percent")
                                break
                        break
            
            # Если метод не найден ни в одном формате
            if not method_found:
                raise HTTPException(status_code=400, detail={
                    "status": "error",
                    "code": "PAYMENT_METHOD_NOT_AVAILABLE",
                    "message": f"Способ оплаты '{requested_method}' не настроен у данного мерчанта"
                })
            
            # Если метод найден, но сумма не в допустимом диапазоне
            if method_fee_percent is None:
                raise HTTPException(status_code=400, detail={
                    "status": "error",
                    "code": "AMOUNT_OUT_OF_RANGE",
                    "message": f"Сумма {request.amount}₽ не входит в допустимый диапазон для метода '{requested_method}'"
                })
    
    # 7. Добавляем маркер (5-20₽) для идентификации платежа
    import random
    marker = random.randint(5, 20)
    
    # 8. fee_model уже определён выше, используем комиссию из настроек метода оплаты
    # Используем комиссию из настроек метода оплаты, если есть
    if method_fee_percent is not None:
        merchant_fee_percent = method_fee_percent
    else:
        merchant_fee_percent = merchant.get("total_fee_percent", 30.0)
    
    # original_amount - это то что клиент ХОЧЕТ пополнить (в данных от мерчанта)
    original_amount = request.amount
    
    if fee_model == "customer_pays":
        # ТИП 2: Покупатель платит накрутку
        # total = original + накрутка + маркер
        markup = round(original_amount * merchant_fee_percent / 100, 2)
        amount_with_markup_and_marker = original_amount + markup + marker
    else:
        # ТИП 1: Мерчант платит комиссию
        # total = original + маркер (без накрутки!)
        amount_with_markup_and_marker = original_amount + marker
    
    usdt_amount_final = round(amount_with_markup_and_marker / exchange_rate, 4)
    
    # 9. Создаём инвойс БЕЗ трейдера - трейдер сам возьмёт заявку
    payment_id = _generate_id("inv")
    dispute_token = generate_dispute_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=30)  # 30 минут на оплату
    
    invoice = {
        "id": payment_id,
        "merchant_id": request.merchant_id,
        "order_id": request.order_id,
        "external_user_id": request.user_id,
        "original_amount_rub": original_amount,  # Исходная сумма (что хочет клиент)
        "amount_rub_original": original_amount,  # Дубль для совместимости
        "amount_rub": amount_with_markup_and_marker,  # TOTAL сумма к оплате
        "marker": marker,
        "amount_usdt": usdt_amount_final,
        "exchange_rate": exchange_rate,
        "fee_model": fee_model,
        "merchant_fee_percent": merchant_fee_percent,  # Сохраняем использованную комиссию
        "currency": request.currency,
        "callback_url": request.callback_url,
        "description": request.description,
        "requested_payment_method": requested_method,
        "status": "waiting_requisites",  # Всегда ждём пока трейдер возьмёт
        "trader_id": None,
        "payment_details_id": None,
        "payment_details": None,
        "dispute_token": dispute_token,
        "dispute_url": None,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "paid_at": None,
        "callback_sent": False,
        "callback_attempts": 0
    }
    
    await _db.merchant_invoices.insert_one(invoice)
    
    # 10. Создаём запись в orders для совместимости с существующей системой
    order = {
        "id": payment_id,
        "merchant_id": merchant["id"],
        "trader_id": None,  # Трейдер ещё не назначен
        "external_id": request.order_id,
        "original_amount_rub": original_amount,  # Исходная сумма (что хочет клиент)
        "amount_rub_original": original_amount,  # Дубль для совместимости
        "amount_rub": amount_with_markup_and_marker,  # TOTAL сумма к оплате
        "marker": marker,
        "amount_usdt": usdt_amount_final,
        "exchange_rate": exchange_rate,
        "fee_model": fee_model,
        "merchant_fee_percent": merchant_fee_percent,  # Сохраняем использованную комиссию
        "payment_method": None,
        "requested_payment_method": requested_method,
        "payment_details": None,
        "status": "waiting_requisites",  # Ждём пока трейдер возьмёт заявку
        "callback_url": request.callback_url,
        "dispute_token": dispute_token,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat()
    }
    await _db.orders.insert_one(order)
    
    # Уведомляем трейдеров о новом заказе
    if _notify_new_order:
        asyncio.create_task(_notify_new_order(order))
    
    # 11. Формируем ответ - всегда ожидание реквизитов
    # Фиксированный домен для payment_url
    base_url = "https://bitarbitr.org"
    
    payment_url = f"{base_url}/pay/{payment_id}"
    
    return {
        "status": "success",
        "payment_id": payment_id,
        "payment_url": payment_url,
        "details": {
            "type": "waiting",
            "message": "Ожидание реквизитов. Трейдер скоро возьмёт заявку.",
            "payment_method": requested_method,
            "amount": amount_with_markup_and_marker,  # TOTAL сумма к оплате
            "amount_original": original_amount,  # Исходная сумма
            "marker": marker,
            "fee_model": fee_model,
            "expires_at": expires_at.isoformat()
        }
    }


@router.get("/status")
async def get_invoice_status(
    merchant_id: str,
    sign: str,
    order_id: Optional[str] = None,
    payment_id: Optional[str] = None,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """
    Проверка статуса платежа
    
    Позволяет мерчанту запросить статус платежа по order_id или payment_id.
    
    Rate limit: 120 запросов в минуту
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    if not order_id and not payment_id:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "MISSING_PARAMS",
            "message": "Требуется order_id или payment_id"
        })
    
    # Проверяем API ключ
    merchant = await _db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    # Rate limit
    if not check_rate_limit(merchant["id"], "status"):
        rate_info = get_rate_limit_info(merchant["id"], "status")
        raise HTTPException(status_code=429, detail={
            "status": "error",
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Превышен лимит запросов. Повторите через {rate_info['reset_in']} сек."
        })
    
    if merchant.get("id") != merchant_id:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "MERCHANT_MISMATCH",
            "message": "Merchant ID не соответствует API ключу"
        })
    
    # Проверяем подпись
    sign_data = {"merchant_id": merchant_id}
    if order_id:
        sign_data["order_id"] = order_id
    if payment_id:
        sign_data["payment_id"] = payment_id
    
    secret_key = merchant.get("secret_key") or merchant.get("api_secret", "")
    if not verify_signature(sign_data, sign, secret_key):
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_SIGNATURE",
            "message": "Неверная подпись запроса"
        })
    
    # Ищем инвойс
    query = {"merchant_id": merchant_id}
    if order_id:
        query["order_id"] = order_id
    if payment_id:
        query["id"] = payment_id
    
    invoice = await _db.merchant_invoices.find_one(query, {"_id": 0})
    if not invoice:
        # Пробуем найти в orders по external_id
        order_query = {"merchant_id": merchant["id"]}
        if order_id:
            order_query["external_id"] = order_id
        if payment_id:
            order_query["id"] = payment_id
        
        order = await _db.orders.find_one(order_query, {"_id": 0})
        if not order:
            raise HTTPException(status_code=404, detail={
                "status": "error",
                "code": "NOT_FOUND",
                "message": "Платёж не найден"
            })
        
        # Конвертируем order в формат ответа
        invoice = {
            "id": order["id"],
            "order_id": order.get("external_id", order["id"]),
            "status": map_order_status_to_invoice(order["status"]),
            "amount_rub": order["amount_rub"],
            "amount_usdt": order.get("amount_usdt"),
            "created_at": order.get("created_at"),
            "paid_at": order.get("completed_at"),
            "dispute_token": order.get("dispute_token"),
            "dispute_url": order.get("dispute_url")
        }
    
    # Формируем ответ
    response_data = {
        "order_id": invoice.get("order_id") or invoice.get("external_id"),
        "payment_id": invoice["id"],
        "status": invoice["status"],
        "amount": invoice.get("amount_rub"),
        "amount_usdt": invoice.get("amount_usdt"),
        "created_at": invoice.get("created_at"),
        "paid_at": invoice.get("paid_at"),
        "expires_at": invoice.get("expires_at")
    }
    
    # Добавляем dispute_url если статус dispute
    if invoice["status"] == "dispute" and invoice.get("dispute_token"):
        response_data["dispute_url"] = f"{_site_url}/dispute/{invoice['dispute_token']}"
    
    return {
        "status": "success",
        "data": response_data
    }


def map_order_status_to_invoice(order_status: str) -> str:
    """Маппинг статусов заказа в статусы инвойса"""
    mapping = {
        "new": "pending",
        "pending": "pending",
        "waiting_buyer_confirmation": "pending",
        "waiting_trader_confirmation": "pending",
        "paid": "paid",
        "completed": "paid",
        "cancelled": "failed",
        "expired": "expired",
        "dispute": "dispute",
        "disputed": "dispute"
    }
    return mapping.get(order_status, order_status)


@router.post("/confirm-payment/{payment_id}")
async def confirm_payment(
    payment_id: str,
    background_tasks: BackgroundTasks
):
    """
    Подтверждение оплаты (внутренний endpoint)
    Вызывается когда трейдер подтверждает получение средств
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    invoice = await _db.merchant_invoices.find_one({"id": payment_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Инвойс не найден")
    
    if invoice["status"] != "pending":
        raise HTTPException(status_code=400, detail="Инвойс не в статусе ожидания")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Обновляем инвойс
    await _db.merchant_invoices.update_one(
        {"id": payment_id},
        {
            "$set": {
                "status": "paid",
                "paid_at": now
            }
        }
    )
    
    # Получаем merchant для подписи callback
    merchant = await _db.merchants.find_one({"id": invoice["merchant_id"]}, {"_id": 0})
    secret_key = merchant.get("secret_key") or merchant.get("api_secret", "")
    
    # Формируем callback payload
    callback_data = {
        "order_id": invoice["order_id"],
        "payment_id": payment_id,
        "status": "paid",
        "amount": invoice["amount_rub"]
    }
    callback_data["sign"] = generate_signature(callback_data, secret_key)
    
    # Отправляем callback
    background_tasks.add_task(send_callback, invoice["callback_url"], callback_data, 0)
    
    return {"status": "success", "message": "Платёж подтверждён, callback отправлен"}


@router.post("/open-dispute/{payment_id}")
async def open_dispute(
    payment_id: str,
    reason: str,
    background_tasks: BackgroundTasks
):
    """
    Открытие спора по платежу
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    invoice = await _db.merchant_invoices.find_one({"id": payment_id})
    if not invoice:
        # Пробуем найти в orders
        order = await _db.orders.find_one({"id": payment_id})
        if not order:
            raise HTTPException(status_code=404, detail="Платёж не найден")
        invoice = order
    
    dispute_token = invoice.get("dispute_token") or generate_dispute_token()
    dispute_url = f"{_site_url}/dispute/{dispute_token}"
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Создаём спор
    dispute = {
        "id": _generate_id("dsp"),
        "order_id": payment_id,
        "invoice_id": invoice.get("id"),
        "merchant_id": invoice.get("merchant_id"),
        "trader_id": invoice.get("trader_id"),
        "dispute_token": dispute_token,
        "reason": reason,
        "status": "open",
        "initiated_by": "merchant_api",
        "created_at": now,
        "messages": []
    }
    await _db.disputes.insert_one(dispute)
    
    # Обновляем инвойс
    await _db.merchant_invoices.update_one(
        {"id": payment_id},
        {
            "$set": {
                "status": "dispute",
                "dispute_url": dispute_url,
                "dispute_id": dispute["id"]
            }
        }
    )
    
    # Обновляем order
    await _db.orders.update_one(
        {"id": payment_id},
        {
            "$set": {
                "status": "dispute",
                "dispute_url": dispute_url,
                "dispute_id": dispute["id"],
                "dispute_token": dispute_token
            }
        }
    )
    
    return {
        "status": "success",
        "dispute_id": dispute["id"],
        "dispute_url": dispute_url
    }


# ================== PUBLIC DISPUTE PAGE ==================

@router.get("/dispute/{dispute_token}")
async def get_public_dispute(dispute_token: str):
    """
    Публичная страница спора по токену
    Доступна без авторизации - для клиентов мерчанта
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Ищем спор по токену
    dispute = await _db.disputes.find_one({"dispute_token": dispute_token}, {"_id": 0})
    if not dispute:
        # Пробуем найти в orders
        order = await _db.orders.find_one({"dispute_token": dispute_token}, {"_id": 0})
        if not order:
            raise HTTPException(status_code=404, detail="Спор не найден")
        
        # Ищем связанный dispute
        dispute = await _db.disputes.find_one({"order_id": order["id"]}, {"_id": 0})
        if not dispute:
            raise HTTPException(status_code=404, detail="Спор не найден")
    
    # Получаем order
    order = await _db.orders.find_one({"id": dispute.get("order_id")}, {"_id": 0})
    
    # Получаем сообщения
    messages = await _db.dispute_messages.find(
        {"dispute_id": dispute["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    return {
        "status": "success",
        "dispute": {
            "id": dispute["id"],
            "status": dispute["status"],
            "reason": dispute.get("reason"),
            "created_at": dispute.get("created_at"),
            "resolved_at": dispute.get("resolved_at"),
            "resolution": dispute.get("resolution")
        },
        "order": {
            "id": order["id"] if order else None,
            "amount_rub": order.get("amount_rub") if order else None,
            "status": order.get("status") if order else None,
            "created_at": order.get("created_at") if order else None
        } if order else None,
        "messages": messages,
        "can_send_message": dispute["status"] == "open"
    }


@router.post("/dispute/{dispute_token}/message")
async def send_public_dispute_message(
    dispute_token: str,
    text: str,
    sender_name: Optional[str] = "Клиент"
):
    """
    Отправка сообщения в спор (публичный доступ по токену)
    Для клиентов мерчанта
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Ищем спор
    dispute = await _db.disputes.find_one({"dispute_token": dispute_token})
    if not dispute:
        order = await _db.orders.find_one({"dispute_token": dispute_token}, {"_id": 0})
        if order:
            dispute = await _db.disputes.find_one({"order_id": order["id"]})
        if not dispute:
            raise HTTPException(status_code=404, detail="Спор не найден")
    
    if dispute["status"] != "open":
        raise HTTPException(status_code=400, detail="Спор закрыт")
    
    now = datetime.now(timezone.utc).isoformat()
    
    message = {
        "id": _generate_id("msg"),
        "dispute_id": dispute["id"],
        "sender_id": "buyer",
        "sender_role": "buyer",
        "sender_name": sender_name,
        "text": text,
        "created_at": now
    }
    
    await _db.dispute_messages.insert_one(message)
    
    # Обновляем время спора
    await _db.disputes.update_one(
        {"id": dispute["id"]},
        {"$set": {"updated_at": now}}
    )
    
    message.pop("_id", None)
    return {"status": "success", "message": message}


# ================== MERCHANT TRANSACTIONS LIST ==================

@router.get("/transactions")
async def get_merchant_transactions(
    x_api_key: str = Header(..., alias="X-Api-Key"),
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Получить список транзакций мерчанта
    С фильтрацией по статусу и пагинацией
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    merchant = await _db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    query = {"merchant_id": merchant["id"]}
    
    # Фильтрация по статусу
    if status:
        if status == "active":
            query["status"] = {"$in": ["pending", "waiting_buyer_confirmation", "waiting_trader_confirmation"]}
        elif status == "completed":
            query["status"] = {"$in": ["paid", "completed"]}
        elif status == "dispute":
            query["status"] = {"$in": ["dispute", "disputed"]}
        else:
            query["status"] = status
    
    # Получаем транзакции
    orders = await _db.orders.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    total = await _db.orders.count_documents(query)
    
    # Обогащаем данные dispute_url
    for order in orders:
        if order.get("status") in ["dispute", "disputed"] and order.get("dispute_token"):
            order["dispute_url"] = f"{_site_url}/dispute/{order['dispute_token']}"
    
    return {
        "status": "success",
        "data": {
            "transactions": orders,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    }


# ================== API STATISTICS ==================

@router.get("/stats")
async def get_merchant_stats(
    x_api_key: str = Header(..., alias="X-Api-Key"),
    period: str = "today"  # today, week, month, all
):
    """
    Статистика API usage для мерчанта
    
    period: today, week, month, all
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    merchant = await _db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    # Определяем временной диапазон
    now = datetime.now(timezone.utc)
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
    
    # Rate limit info
    rate_info = {
        "create": get_rate_limit_info(merchant["id"], "create"),
        "status": get_rate_limit_info(merchant["id"], "status"),
        "transactions": get_rate_limit_info(merchant["id"], "transactions")
    }
    
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
                "total_rub": round(total_rub, 2),
                "total_usdt": round(total_usdt, 2),
                "average_amount_rub": round(avg_amount, 2)
            },
            "conversion_rate": round(conversion_rate, 2),
            "rate_limits": rate_info
        }
    }


@router.get("/analytics")
async def get_merchant_analytics(
    x_api_key: str = Header(..., alias="X-Api-Key"),
    period: str = "month"  # today, week, month, all
):
    """
    Расширенная аналитика для мерчанта:
    - Статистика по маркерам
    - Конверсия по методам оплаты
    - Распределение по суммам
    - Временная динамика
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    merchant = await _db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    now = datetime.now(timezone.utc)
    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = None
    
    base_query = {"merchant_id": merchant["id"]}
    if start_date:
        base_query["created_at"] = {"$gte": start_date.isoformat()}
    
    # ========== MARKER ANALYTICS ==========
    marker_pipeline = [
        {"$match": base_query},
        {"$group": {
            "_id": "$marker",
            "count": {"$sum": 1},
            "paid_count": {"$sum": {"$cond": [{"$in": ["$status", ["paid", "completed"]]}, 1, 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    marker_stats = await _db.orders.aggregate(marker_pipeline).to_list(100)
    
    # Подсчёт эффективности маркеров
    marker_data = {}
    total_with_marker = 0
    paid_with_marker = 0
    
    for m in marker_stats:
        marker_val = m["_id"]
        if marker_val and marker_val >= 5 and marker_val <= 20:
            marker_data[marker_val] = {
                "count": m["count"],
                "paid": m["paid_count"],
                "conversion": round(m["paid_count"] / m["count"] * 100, 1) if m["count"] > 0 else 0
            }
            total_with_marker += m["count"]
            paid_with_marker += m["paid_count"]
    
    marker_summary = {
        "total_orders_with_marker": total_with_marker,
        "paid_orders_with_marker": paid_with_marker,
        "marker_range": {"min": 5, "max": 20},
        "average_marker": round(sum(k * v["count"] for k, v in marker_data.items()) / total_with_marker, 1) if total_with_marker > 0 else 0,
        "distribution": marker_data
    }
    
    # ========== PAYMENT METHOD ANALYTICS ==========
    method_pipeline = [
        {"$match": base_query},
        {"$group": {
            "_id": {"$ifNull": ["$requested_payment_method", "$payment_method"]},
            "total": {"$sum": 1},
            "paid": {"$sum": {"$cond": [{"$in": ["$status", ["paid", "completed"]]}, 1, 0]}},
            "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
            "expired": {"$sum": {"$cond": [{"$eq": ["$status", "expired"]}, 1, 0]}},
            "disputed": {"$sum": {"$cond": [{"$in": ["$status", ["dispute", "disputed"]]}, 1, 0]}},
            "volume_rub": {"$sum": {"$cond": [
                {"$in": ["$status", ["paid", "completed"]]},
                {"$ifNull": ["$original_amount_rub", "$amount_rub"]},
                0
            ]}},
            "avg_amount": {"$avg": {"$ifNull": ["$original_amount_rub", "$amount_rub"]}}
        }},
        {"$sort": {"total": -1}}
    ]
    
    method_stats = await _db.orders.aggregate(method_pipeline).to_list(20)
    
    payment_methods = {}
    for m in method_stats:
        method_id = m["_id"] or "unknown"
        payment_methods[method_id] = {
            "total_orders": m["total"],
            "paid": m["paid"],
            "cancelled": m["cancelled"],
            "expired": m["expired"],
            "disputed": m["disputed"],
            "conversion_rate": round(m["paid"] / m["total"] * 100, 1) if m["total"] > 0 else 0,
            "volume_rub": round(m["volume_rub"], 2),
            "avg_order_amount": round(m["avg_amount"], 2) if m["avg_amount"] else 0
        }
    
    # ========== AMOUNT DISTRIBUTION ==========
    amount_ranges = [
        (0, 500, "0-500"),
        (500, 1000, "500-1000"),
        (1000, 2000, "1000-2000"),
        (2000, 5000, "2000-5000"),
        (5000, 10000, "5000-10000"),
        (10000, float('inf'), "10000+")
    ]
    
    amount_distribution = {}
    for min_amt, max_amt, label in amount_ranges:
        range_query = {**base_query}
        if max_amt == float('inf'):
            range_query["original_amount_rub"] = {"$gte": min_amt}
        else:
            range_query["original_amount_rub"] = {"$gte": min_amt, "$lt": max_amt}
        
        total = await _db.orders.count_documents(range_query)
        paid_query = {**range_query, "status": {"$in": ["paid", "completed"]}}
        paid = await _db.orders.count_documents(paid_query)
        
        amount_distribution[label] = {
            "total": total,
            "paid": paid,
            "conversion": round(paid / total * 100, 1) if total > 0 else 0
        }
    
    # ========== TIME DISTRIBUTION ==========
    # Группировка по часам дня для определения пиковых часов
    hour_pipeline = [
        {"$match": {**base_query, "status": {"$in": ["paid", "completed"]}}},
        {"$project": {
            "hour": {"$hour": {"$dateFromString": {"dateString": "$created_at"}}}
        }},
        {"$group": {
            "_id": "$hour",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    try:
        hour_stats = await _db.orders.aggregate(hour_pipeline).to_list(24)
        hourly_distribution = {h["_id"]: h["count"] for h in hour_stats}
        
        # Находим пиковые часы
        if hourly_distribution:
            peak_hour = max(hourly_distribution, key=hourly_distribution.get)
            peak_count = hourly_distribution[peak_hour]
        else:
            peak_hour = None
            peak_count = 0
    except Exception:
        hourly_distribution = {}
        peak_hour = None
        peak_count = 0
    
    # ========== OVERALL CONVERSION FUNNEL ==========
    total_orders = await _db.orders.count_documents(base_query)
    paid_orders = await _db.orders.count_documents({**base_query, "status": {"$in": ["paid", "completed"]}})
    cancelled_orders = await _db.orders.count_documents({**base_query, "status": "cancelled"})
    expired_orders = await _db.orders.count_documents({**base_query, "status": "expired"})
    disputed_orders = await _db.orders.count_documents({**base_query, "status": {"$in": ["dispute", "disputed"]}})
    
    return {
        "status": "success",
        "data": {
            "period": period,
            "period_start": start_date.isoformat() if start_date else None,
            "generated_at": now.isoformat(),
            
            "conversion_funnel": {
                "total_orders": total_orders,
                "paid": paid_orders,
                "cancelled": cancelled_orders,
                "expired": expired_orders,
                "disputed": disputed_orders,
                "overall_conversion": round(paid_orders / total_orders * 100, 1) if total_orders > 0 else 0
            },
            
            "markers": marker_summary,
            
            "payment_methods": payment_methods,
            
            "amount_distribution": amount_distribution,
            
            "peak_hours": {
                "peak_hour": peak_hour,
                "peak_orders": peak_count,
                "hourly_distribution": hourly_distribution
            }
        }
    }


# ================== API DOCUMENTATION ENDPOINT ==================

@router.get("/docs")
async def get_api_documentation(http_request: Request = None):
    """
    Получить документацию API
    """
    # Фиксированный домен для документации
    base_url = "https://bitarbitr.org"
    
    return {
        "api_version": "v1",
        "base_url": f"{base_url}/api/v1/invoice",
        "authentication": {
            "header": "X-Api-Key",
            "description": "API ключ выдается при регистрации мерчанта"
        },
        "signature": {
            "algorithm": "HMAC-SHA256",
            "description": "Запросы подписываются с использованием Secret Key",
            "important_notes": [
                "Для /create в подпись входят ТОЛЬКО поля: merchant_id, order_id, amount, currency, user_id, callback_url, payment_method",
                "Поле description и другие дополнительные поля НЕ участвуют в подписи!",
                "ВАЖНО: если amount - целое число (1500.0), оно приводится к int (1500) перед подписью"
            ],
            "steps": [
                "1. Взять только разрешённые поля для подписи (см. important_notes)",
                "2. Убрать sign и поля с null значениями",
                "3. Если число float и целое (v == int(v)), привести к int: 1500.0 → 1500",
                "4. Отсортировать по ключам в алфавитном порядке",
                "5. Сформировать строку key1=value1&key2=value2&...",
                "6. Добавить Secret Key в конец строки (без &)",
                "7. Вычислить HMAC-SHA256 хеш",
                "8. Передать хеш в поле sign"
            ],
            "example_python": """
# Поля для подписи /create
SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url', 'payment_method']

def generate_signature(params, secret_key):
    sign_params = {}
    for k, v in params.items():
        if k not in SIGN_FIELDS or k == 'sign' or v is None:
            continue
        if isinstance(v, float) and v == int(v):
            v = int(v)
        sign_params[k] = v
    sorted_params = sorted(sign_params.items())
    sign_string = '&'.join(f'{k}={v}' for k, v in sorted_params) + secret_key
    return hmac.new(secret_key.encode(), sign_string.encode(), hashlib.sha256).hexdigest()
"""
        },
        "endpoints": {
            "GET /payment-methods": {
                "description": "Получить список доступных способов оплаты",
                "auth": "X-Api-Key header",
                "response": {
                    "status": "success",
                    "payment_methods": [
                        {"id": "card", "name": "Банковская карта", "description": "Visa, Mastercard, МИР"},
                        {"id": "sbp", "name": "СБП", "description": "Система быстрых платежей"}
                    ]
                }
            },
            "POST /create": {
                "description": "Создание инвойса на оплату",
                "request": {
                    "merchant_id": "string (required)",
                    "order_id": "string (required, unique)",
                    "amount": "number (required, RUB)",
                    "currency": "string (default: RUB)",
                    "user_id": "string (optional)",
                    "callback_url": "string (required)",
                    "payment_method": "string (optional, id из /payment-methods)",
                    "sign": "string (required)"
                },
                "response": {
                    "status": "success",
                    "payment_id": "string",
                    "payment_url": "string (ОТКРЫВАТЬ В НОВОЙ ВКЛАДКЕ!)",
                    "details": {
                        "type": "waiting",
                        "message": "string",
                        "amount": "number",
                        "expires_at": "string"
                    }
                }
            },
            "GET /status": {
                "description": "Проверка статуса платежа",
                "params": {
                    "merchant_id": "string (required)",
                    "order_id": "string (optional)",
                    "payment_id": "string (optional)",
                    "sign": "string (required)"
                },
                "response": {
                    "status": "success",
                    "data": {
                        "order_id": "string",
                        "payment_id": "string",
                        "status": "pending|paid|failed|expired|dispute",
                        "amount": "number",
                        "dispute_url": "string (if status=dispute)"
                    }
                }
            },
            "GET /transactions": {
                "description": "Список транзакций мерчанта",
                "params": {
                    "status": "active|completed|dispute (optional)",
                    "limit": "number (default: 50)",
                    "offset": "number (default: 0)"
                }
            },
            "GET /stats": {
                "description": "Статистика API usage",
                "params": {
                    "period": "today|week|month|all (default: today)"
                },
                "response": {
                    "summary": {"total_invoices": "number", "paid": "number", "pending": "number"},
                    "volume": {"total_rub": "number", "total_usdt": "number"},
                    "conversion_rate": "number",
                    "rate_limits": "object"
                }
            }
        },
        "integration_flow": {
            "description": "Пошаговая интеграция на вашем сайте",
            "steps": [
                "1. GET /payment-methods - получите список способов оплаты",
                "2. Покажите покупателю выбор способа оплаты НА ВАШЕМ САЙТЕ",
                "3. POST /create - создайте инвойс с выбранным payment_method",
                "4. window.open(payment_url, '_blank') - откройте страницу оплаты В НОВОЙ ВКЛАДКЕ",
                "5. Страница оплаты на нашем домене покажет реквизиты и чат",
                "6. Получите callback или проверяйте статус через GET /status"
            ],
            "important": [
                "Реквизиты НЕ передаются на ваш сайт - они показываются только на нашем домене",
                "payment_url ВСЕГДА открывайте в новой вкладке через window.open()",
                "После оплаты покупатель закроет вкладку и вернётся на ваш сайт"
            ]
        },
        "code_example_javascript": """
// 1. Получаем способы оплаты
const methodsRes = await fetch('https://YOUR_DOMAIN/api/v1/invoice/payment-methods', {
  headers: { 'X-Api-Key': 'YOUR_API_KEY' }
});
const { payment_methods } = await methodsRes.json();

// 2. Покупатель выбирает метод на ВАШЕМ сайте
const selectedMethod = 'card'; // выбор пользователя

// 3. Создаём инвойс
const params = {
  merchant_id: 'YOUR_MERCHANT_ID',
  order_id: 'ORDER_' + Date.now(),
  amount: 1500,
  currency: 'RUB',
  callback_url: 'https://yoursite.com/callback',
  payment_method: selectedMethod
};
params.sign = generateHmacSha256(params, 'YOUR_SECRET_KEY');

const invoiceRes = await fetch('https://YOUR_DOMAIN/api/v1/invoice/create', {
  method: 'POST',
  headers: { 
    'X-Api-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(params)
});
const invoice = await invoiceRes.json();

// 4. ОТКРЫВАЕМ СТРАНИЦУ ОПЛАТЫ В НОВОЙ ВКЛАДКЕ
window.open(invoice.payment_url, '_blank');
// Покупатель видит реквизиты и оплачивает на НАШЕМ домене
// После оплаты он закрывает вкладку и возвращается к вам
        """,
        "callback": {
            "method": "POST",
            "content_type": "application/json",
            "body": {
                "order_id": "string",
                "payment_id": "string",
                "status": "paid|failed|expired",
                "amount": "number",
                "sign": "string"
            },
            "expected_response": {
                "status_code": 200,
                "body": {"status": "ok"}
            },
            "retry_policy": "1m, 5m, 15m, 1h, 2h, 4h, 12h, 24h"
        },
        "statuses": {
            "waiting_requisites": "Ожидание реквизитов от трейдера",
            "pending": "Ожидает оплаты",
            "paid": "Оплачен",
            "failed": "Ошибка/Отмена",
            "expired": "Истёк срок",
            "dispute": "Открыт спор"
        },
        "errors": {
            "INVALID_API_KEY": "Неверный API ключ",
            "INVALID_SIGNATURE": "Неверная подпись",
            "DUPLICATE_ORDER_ID": "Дублирующийся order_id",
            "INVALID_AMOUNT": "Некорректная сумма",
            "INVALID_PAYMENT_METHOD": "Недопустимый способ оплаты",
            "PAYMENT_METHOD_NOT_AVAILABLE": "Способ оплаты не настроен у мерчанта",
            "NO_TRADERS_AVAILABLE": "Нет доступных трейдеров",
            "NOT_FOUND": "Платёж не найден"
        }
    }
