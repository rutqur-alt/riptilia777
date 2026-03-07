"""
Invoice API для мерчантов (v1)
REST API для приема рублевых платежей через P2P USDT
Адаптировано из BIT-9-DOK-main для интеграции в REP01-main

Endpoints:
- POST /v1/invoice/create - создание инвойса
- GET /v1/invoice/status - проверка статуса
- GET /v1/invoice/payment-methods - список методов оплаты
- GET /v1/invoice/transactions - история транзакций
- GET /v1/invoice/stats - статистика
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
import uuid

from core.database import db

router = APIRouter(prefix="/v1/invoice", tags=["Invoice API v1"])
logger = logging.getLogger(__name__)

# Rate limits per merchant per minute
RATE_LIMITS = {
    "create": 60,
    "status": 120,
    "transactions": 30
}

# In-memory rate limit storage
_rate_limit_storage = defaultdict(lambda: defaultdict(list))

# Retry intervals для webhook (в секундах)
WEBHOOK_RETRY_INTERVALS = [60, 300, 900, 3600, 7200, 14400, 43200, 86400]

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


def generate_id(prefix: str = "inv") -> str:
    """Генерация уникального ID"""
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{prefix}_{date_part}_{secrets.token_hex(4).upper()}"


def check_rate_limit(merchant_id: str, endpoint: str) -> bool:
    """Проверка rate limit"""
    limit = RATE_LIMITS.get(endpoint, 60)
    now = time.time()
    window = 60
    
    _rate_limit_storage[merchant_id][endpoint] = [
        t for t in _rate_limit_storage[merchant_id][endpoint]
        if now - t < window
    ]
    
    if len(_rate_limit_storage[merchant_id][endpoint]) >= limit:
        return False
    
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


# ================== SIGNATURE UTILS ==================

def generate_signature(data: Dict[str, Any], secret_key: str) -> str:
    """Генерация HMAC-SHA256 подписи"""
    sign_data = {}
    for k, v in data.items():
        if k == 'sign' or v is None:
            continue
        if isinstance(v, float) and v == int(v):
            v = int(v)
        sign_data[k] = v
    
    sorted_params = sorted(sign_data.items())
    sign_string = '&'.join(f"{k}={v}" for k, v in sorted_params)
    sign_string += secret_key
    
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
    payment_method: Optional[str] = Field(None, description="Метод оплаты")
    sign: str = Field(..., description="HMAC-SHA256 подпись запроса")


class InvoiceStatusRequest(BaseModel):
    """Запрос статуса инвойса"""
    merchant_id: str
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    sign: str


# ================== WEBHOOK SYSTEM ==================

async def send_webhook_notification(invoice_id: str, new_status: str, extra_data: dict = None):
    """Отправляет webhook-уведомление мерчанту"""
    try:
        invoice = await db.merchant_invoices.find_one({"id": invoice_id}, {"_id": 0})
        if not invoice:
            return
        
        callback_url = invoice.get("callback_url")
        if not callback_url:
            return
        
        merchant = await db.merchants.find_one({"id": invoice.get("merchant_id")}, {"_id": 0})
        if not merchant:
            return
        
        secret_key = merchant.get("api_secret") or merchant.get("api_key", "")
        
        callback_data = {
            "order_id": invoice.get("external_order_id", invoice_id),
            "payment_id": invoice_id,
            "status": new_status,
            "amount": invoice.get("original_amount_rub") or invoice.get("amount_rub"),
            "amount_usdt": invoice.get("amount_usdt"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if extra_data:
            callback_data.update(extra_data)
        
        callback_data["sign"] = generate_signature(callback_data, secret_key)
        
        # Save webhook to history
        webhook_record = {
            "id": generate_id("whk"),
            "invoice_id": invoice_id,
            "merchant_id": invoice.get("merchant_id"),
            "callback_url": callback_url,
            "payload": callback_data,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.webhook_history.insert_one(webhook_record)
        
        # Send webhook (test_webhooks will be saved by test-webhook-receiver endpoint)
        success = await send_webhook(callback_url, callback_data, 0)
        
        await db.webhook_history.update_one(
            {"id": webhook_record["id"]},
            {"$set": {
                "status": "delivered" if success else "retry_scheduled",
                "delivered_at": datetime.now(timezone.utc).isoformat() if success else None
            }}
        )
        
    except Exception as e:
        logger.error(f"Error sending webhook for invoice {invoice_id}: {e}")


async def send_webhook(callback_url: str, payload: Dict[str, Any], retry_count: int = 0) -> bool:
    """Отправка webhook с retry логикой"""
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
                        return True
                except:
                    pass
            
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    
    # Schedule retry
    if retry_count < len(WEBHOOK_RETRY_INTERVALS):
        delay = WEBHOOK_RETRY_INTERVALS[retry_count]
        await db.webhook_queue.insert_one({
            "id": generate_id("wbq"),
            "callback_url": callback_url,
            "payload": payload,
            "retry_count": retry_count + 1,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    return False


# ================== ENDPOINTS ==================

@router.get("/payment-methods")
async def get_payment_methods(x_api_key: str = Header(..., alias="X-Api-Key")):
    """Получить список доступных способов оплаты для мерчанта"""
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    # Always merchant_pays model
    # Return only configured methods or all if none configured
    method_commissions = merchant.get("method_commissions", {})
    payment_method_commissions = merchant.get("payment_method_commissions", [])
    
    available_methods = []
    
    for method in STANDARD_PAYMENT_METHODS:
        method_id = method["id"]
        
        if method_id in method_commissions:
            config = method_commissions[method_id]
            if config.get("enabled", True):
                available_methods.append(method)
                continue
        
        for old_config in payment_method_commissions:
            if old_config.get("payment_method") == method_id:
                available_methods.append(method)
                break
    
    if not available_methods:
        available_methods = STANDARD_PAYMENT_METHODS
    
    return {"status": "success", "payment_methods": available_methods}


@router.post("/create")
async def create_invoice(
    request: InvoiceCreateRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(..., alias="X-Api-Key"),
    http_request: Request = None
):
    """Создание инвойса для пополнения"""
    
    # 1. Verify API key
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    # 2. Check rate limit
    if not check_rate_limit(merchant["id"], "create"):
        rate_info = get_rate_limit_info(merchant["id"], "create")
        raise HTTPException(status_code=429, detail={
            "status": "error",
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Превышен лимит запросов. Повторите через {rate_info['reset_in']} сек."
        })
    
    if merchant.get("id") != request.merchant_id:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "MERCHANT_MISMATCH",
            "message": "Merchant ID не соответствует API ключу"
        })
    
    # 3. Verify signature (payment_method НЕ входит в подпись)
    sign_data = {
        "merchant_id": request.merchant_id,
        "order_id": request.order_id,
        "amount": request.amount,
        "currency": request.currency,
        "user_id": request.user_id,
        "callback_url": request.callback_url
    }
    
    secret_key = merchant.get("api_secret") or merchant.get("api_key", "")
    
    if not verify_signature(sign_data, request.sign, secret_key):
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_SIGNATURE",
            "message": "Неверная подпись запроса"
        })
    
    # 4. Check for duplicate order_id
    existing = await db.merchant_invoices.find_one({
        "merchant_id": request.merchant_id,
        "external_order_id": request.order_id
    })
    if existing:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "DUPLICATE_ORDER_ID",
            "message": "Заказ с таким order_id уже существует"
        })
    
    # 5. Check minimum amount
    min_amount = 100.0
    if request.amount < min_amount:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_AMOUNT",
            "message": f"Сумма меньше минимальной ({min_amount} RUB)"
        })
    
    # 6. Get exchange rate from Rapira API (payout_settings)
    payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    exchange_rate = payout_settings.get("base_rate", 78.0) if payout_settings else 78.0
    if not exchange_rate or exchange_rate <= 0:
        settings = await db.commission_settings.find_one({}, {"_id": 0})
        exchange_rate = settings.get("default_price_rub", 78.0) if settings else 78.0
    
    # 7. Validate payment method
    valid_payment_methods = ['card', 'sbp', 'sim', 'mono_bank', 'sng_sbp', 'sng_card', 'qr_code']
    requested_method = request.payment_method
    
    if requested_method and requested_method not in valid_payment_methods:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_PAYMENT_METHOD",
            "message": f"Недопустимый метод оплаты. Доступны: {', '.join(valid_payment_methods)}"
        })
    
    # 8. Calculate fees — always merchant_pays model
    fee_model = "merchant_pays"
    merchant_fee_percent = merchant.get("commission_rate", 3.0)
    
    # Check method-specific commission
    if requested_method:
        method_commissions = merchant.get("method_commissions", {})
        payment_method_commissions = merchant.get("payment_method_commissions", [])
        
        method_found = False
        
        if requested_method in method_commissions:
            method_config = method_commissions[requested_method]
            if method_config.get("enabled", True):
                method_found = True
                intervals = method_config.get("intervals", [])
                for interval in intervals:
                    min_amt = interval.get("min_amount", 0)
                    max_amt = interval.get("max_amount", float('inf'))
                    if min_amt <= request.amount <= max_amt:
                        merchant_fee_percent = interval.get("percent", merchant_fee_percent)
                        break
        
        if not method_found and payment_method_commissions:
            for method_config in payment_method_commissions:
                if method_config.get("payment_method") == requested_method:
                    method_found = True
                    intervals = method_config.get("intervals", [])
                    for interval in intervals:
                        min_amt = interval.get("min_amount", 0)
                        max_amt = interval.get("max_amount", float('inf'))
                        if min_amt <= request.amount <= max_amt:
                            merchant_fee_percent = interval.get("percent", merchant_fee_percent)
                            break
                    break
    
    # 9. Add marker for payment identification
    import random
    marker = random.randint(5, 20)
    
    original_amount = request.amount
    
    # Merchant pays fee, customer pays only amount + marker
    total_amount = original_amount + marker
    
    usdt_amount = round(total_amount / exchange_rate, 4)
    
    # 10. Create invoice
    invoice_id = generate_id("inv")
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=30)
    
    invoice = {
        "id": invoice_id,
        "merchant_id": request.merchant_id,
        "external_order_id": request.order_id,
        "external_user_id": request.user_id,
        "original_amount_rub": original_amount,
        "amount_rub": total_amount,
        "marker": marker,
        "amount_usdt": usdt_amount,
        "exchange_rate": exchange_rate,
        "fee_model": fee_model,
        "merchant_fee_percent": merchant_fee_percent,
        "currency": request.currency,
        "callback_url": request.callback_url,
        "description": request.description,
        "requested_payment_method": requested_method,
        "status": "waiting_requisites",
        "trader_id": None,
        "payment_details": None,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "paid_at": None,
        "webhook_sent": False
    }
    
    await db.merchant_invoices.insert_one(invoice)
    
    # 11. Create payment link for compatibility
    payment_link = {
        "id": invoice_id,
        "merchant_id": merchant["id"],
        "amount_rub": total_amount,
        "amount_usdt": usdt_amount,
        "price_rub": exchange_rate,
        "description": request.description,
        "client_id": request.user_id,
        "webhook_url": request.callback_url,
        "link_url": f"/pay/{invoice_id}",
        "status": "active",
        "invoice_id": invoice_id,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat()
    }
    await db.payment_links.insert_one(payment_link)
    
    # 12. Build payment URL
    # Всегда используем правильный публичный домен для payment_url
    import os
    base_url = os.environ.get("SITE_URL", "https://secure-payments.st")
    
    # URL на страницу выбора оператора
    payment_url = f"{base_url}/select-operator/{invoice_id}"
    
    return {
        "status": "success",
        "payment_id": invoice_id,
        "payment_url": payment_url,
        "details": {
            "type": "waiting",
            "message": "Ожидание реквизитов. Откройте страницу оплаты.",
            "original_amount": original_amount,
            "total_amount": total_amount,
            "marker": marker,
            "amount_usdt": usdt_amount,
            "expires_at": expires_at.isoformat()
        }
    }


@router.get("/status")
async def get_invoice_status(
    order_id: Optional[str] = None,
    payment_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    sign: Optional[str] = None,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """Проверка статуса платежа"""
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    if not check_rate_limit(merchant["id"], "status"):
        rate_info = get_rate_limit_info(merchant["id"], "status")
        raise HTTPException(status_code=429, detail={
            "status": "error",
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Превышен лимит запросов. Повторите через {rate_info['reset_in']} сек."
        })
    
    # Use merchant_id from API key if not provided
    effective_merchant_id = merchant_id or merchant["id"]
    
    # Find invoice
    query = {"merchant_id": effective_merchant_id}
    if payment_id:
        query["id"] = payment_id
    elif order_id:
        query["external_order_id"] = order_id
    else:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "MISSING_IDENTIFIER",
            "message": "Укажите order_id или payment_id"
        })
    
    invoice = await db.merchant_invoices.find_one(query, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "NOT_FOUND",
            "message": "Платёж не найден"
        })
    
    return {
        "status": "success",
        "data": {
            "order_id": invoice.get("external_order_id"),
            "payment_id": invoice["id"],
            "status": invoice.get("status", "created"),
            "amount": invoice.get("original_amount_rub"),
            "total_amount": invoice.get("amount_rub"),
            "amount_usdt": invoice.get("amount_usdt"),
            "created_at": invoice.get("created_at"),
            "paid_at": invoice.get("paid_at"),
            "expires_at": invoice.get("expires_at")
        }
    }



# ================== WHITE-LABEL INTEGRATION ENDPOINTS ==================

@router.get("/{invoice_id}/operators")
async def get_operators_for_invoice(
    invoice_id: str,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """
    White-label: Получить список доступных операторов для инвойса.
    Мерчант отображает этот список на СВОЁМ сайте.
    """
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={"status": "error", "message": "Неверный API ключ"})
    
    invoice = await db.merchant_invoices.find_one({"id": invoice_id, "merchant_id": merchant["id"]}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Инвойс не найден"})
    
    amount_rub = invoice.get("original_amount_rub") or invoice.get("amount_rub", 0)
    
    # Get current exchange rate
    rate_data = await db.exchange_rates.find_one({"key": "usdt_rub"}, {"_id": 0})
    exchange_rate = rate_data.get("rate", 95) if rate_data else 95
    amount_usdt = amount_rub / exchange_rate
    
    # Find matching offers with STRICT validation
    offers = await db.offers.find({
        "type": "sell",
        "is_active": True,
        "paused_by_trader": {"$ne": True},       # НЕ на паузе
        "available_usdt": {"$gte": amount_usdt * 0.95},
        "$or": [
            {"min_amount_rub": {"$exists": False}},
            {"min_amount_rub": {"$lte": amount_rub}}
        ]
    }, {"_id": 0}).to_list(50)
    
    if not offers:
        return {
            "status": "success",
            "operators": [],
            "message": "Нет доступных операторов для данной суммы"
        }
    
    operators = []
    for offer in offers:
        # СТРОГАЯ ПРОВЕРКА: Пропускаем если объявление на паузе или неактивно
        if not offer.get("is_active"):
            continue
        if offer.get("paused_by_trader"):
            continue
        
        trader = await db.traders.find_one({"id": offer["trader_id"]}, {"_id": 0})
        if not trader:
            continue
        
        # СТРОГАЯ ПРОВЕРКА: Трейдер должен быть активен
        trader_status = trader.get("status", "active")
        if trader_status not in [None, "active"]:
            continue
        if trader.get("is_blocked") or trader.get("blocked"):
            continue
        
        # СТРОГАЯ ПРОВЕРКА: Достаточно баланса на объявлении
        available = offer.get("available_usdt", 0)
        if available < amount_usdt * 0.99:
            continue
        
        # СТРОГАЯ ПРОВЕРКА: Сумма в пределах лимитов
        min_amt = offer.get("min_amount", 0)
        max_amt = offer.get("max_amount")
        if amount_usdt < min_amt:
            continue
        if max_amt and amount_usdt > max_amt and amount_usdt > available:
            continue
        
        # Calculate price with trader's rate
        price_rub = offer.get("price_rub", exchange_rate)
        to_pay_rub = round(amount_usdt * price_rub)
        commission_percent = round(((price_rub - exchange_rate) / exchange_rate) * 100, 1)
        
        operators.append({
            "offer_id": offer["id"],
            "nickname": trader.get("nickname", "Трейдер"),
            "rating": trader.get("rating", 100),
            "trades_count": trader.get("completed_trades", 0),
            "payment_methods": offer.get("payment_methods", []),
            "price_rub": price_rub,
            "amount_to_pay": to_pay_rub,
            "commission_percent": max(0, commission_percent),
            "min_amount": offer.get("min_amount_rub", 100),
            "max_amount": offer.get("max_amount_rub", 500000)
        })
    
    # Sort by price (cheapest first)
    operators.sort(key=lambda x: x["amount_to_pay"])
    
    return {
        "status": "success",
        "invoice_id": invoice_id,
        "amount_rub": amount_rub,
        "exchange_rate": exchange_rate,
        "operators": operators
    }


class SelectOperatorRequest(BaseModel):
    offer_id: str
    payment_method: str  # 'card' or 'sbp'


@router.post("/{invoice_id}/select-operator")
async def select_operator_for_invoice(
    invoice_id: str,
    request: SelectOperatorRequest,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """
    White-label: Выбрать оператора и получить реквизиты для оплаты.
    Мерчант показывает реквизиты на СВОЁМ сайте.
    """
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={"status": "error", "message": "Неверный API ключ"})
    
    invoice = await db.merchant_invoices.find_one({"id": invoice_id, "merchant_id": merchant["id"]}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Инвойс не найден"})
    
    if invoice.get("trade_id"):
        raise HTTPException(status_code=400, detail={"status": "error", "message": "Оператор уже выбран"})
    
    # Get offer and trader
    offer = await db.offers.find_one({"id": request.offer_id, "is_active": True}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Объявление не найдено или неактивно"})
    
    trader = await db.traders.find_one({"id": offer["trader_id"]}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Трейдер не найден"})
    
    # Get requisites for selected payment method
    # First try offer.requisites, then try payment_details collection
    requisites = offer.get("requisites", [])
    matching_req = None
    
    for req in requisites:
        req_type = req.get("type") or req.get("payment_method") or req.get("payment_type")
        if req_type == request.payment_method:
            # Requisites can have nested data or flat structure
            data = req.get("data", {})
            matching_req = {
                "id": req.get("id"),
                "type": req_type,
                "bank": data.get("bank_name", req.get("bank_name", "")),
                "number": data.get("card_number") or data.get("phone") or req.get("card_number") or req.get("phone_number", ""),
                "holder": data.get("card_holder") or data.get("holder") or req.get("holder_name", "")
            }
            break
    
    # If not found in offer.requisites, try payment_details collection
    if not matching_req:
        payment_detail = await db.payment_details.find_one({
            "trader_id": offer["trader_id"],
            "$or": [
                {"type": request.payment_method},
                {"payment_type": request.payment_method}
            ]
        }, {"_id": 0})
        
        if payment_detail:
            matching_req = {
                "id": payment_detail.get("id"),
                "type": request.payment_method,
                "bank": payment_detail.get("bank_name", ""),
                "number": payment_detail.get("card_number") or payment_detail.get("phone_number", ""),
                "holder": payment_detail.get("holder_name", "")
            }
    
    if not matching_req or not matching_req.get("number"):
        raise HTTPException(status_code=400, detail={"status": "error", "message": f"Реквизиты для метода оплаты {request.payment_method} не найдены у этого оператора"})
    
    # Calculate amounts
    amount_rub = invoice.get("original_amount_rub") or invoice.get("amount_rub", 0)
    rate_data = await db.exchange_rates.find_one({"key": "usdt_rub"}, {"_id": 0})
    exchange_rate = rate_data.get("rate", 95) if rate_data else 95
    price_rub = offer.get("price_rub", exchange_rate)
    amount_usdt = amount_rub / price_rub
    
    # Check available balance
    if offer.get("available_usdt", 0) < amount_usdt:
        raise HTTPException(status_code=400, detail={"status": "error", "message": "Недостаточно средств у оператора"})
    
    # Create trade
    trade_id = f"trd_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc)
    
    trade_doc = {
        "id": trade_id,
        "invoice_id": invoice_id,
        "offer_id": offer["id"],
        "trader_id": offer["trader_id"],
        "buyer_type": "merchant_client",
        "merchant_id": merchant["id"],
        "amount_usdt": round(amount_usdt, 4),
        "amount_rub": amount_rub,
        "price_rub": price_rub,
        "payment_method": request.payment_method,
        "requisites": [matching_req],
        "status": "pending",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat()
    }
    await db.trades.insert_one(trade_doc)
    
    # Reserve USDT from offer
    await db.offers.update_one(
        {"id": offer["id"]},
        {"$inc": {"available_usdt": -amount_usdt}}
    )
    
    # Link trade to invoice
    await db.merchant_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "trade_id": trade_id,
            "status": "pending",
            "updated_at": now.isoformat()
        }}
    )
    
    # Send pending webhook
    from routes.trades import send_merchant_webhook_on_trade
    await send_merchant_webhook_on_trade(trade_doc, "pending", {"trade_id": trade_id})
    
    return {
        "status": "success",
        "trade_id": trade_id,
        "operator": {
            "nickname": trader.get("nickname", "Трейдер"),
            "rating": trader.get("rating", 100)
        },
        "payment": {
            "method": request.payment_method,
            "amount": amount_rub,
            "requisites": {
                "type": matching_req.get("type") or matching_req.get("payment_method"),
                "bank": matching_req.get("bank", ""),
                "number": matching_req.get("number") or matching_req.get("card_number") or matching_req.get("phone"),
                "holder": matching_req.get("holder") or matching_req.get("card_holder", "")
            }
        },
        "expires_at": trade_doc["expires_at"],
        "time_limit_minutes": 30
    }


@router.post("/{invoice_id}/mark-paid")
async def mark_invoice_paid(
    invoice_id: str,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """
    White-label: Клиент нажал "Я оплатил" на сайте мерчанта.
    Отправляет webhook 'paid' мерчанту.
    """
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={"status": "error", "message": "Неверный API ключ"})
    
    invoice = await db.merchant_invoices.find_one({"id": invoice_id, "merchant_id": merchant["id"]}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Инвойс не найден"})
    
    trade_id = invoice.get("trade_id")
    if not trade_id:
        raise HTTPException(status_code=400, detail={"status": "error", "message": "Сначала выберите оператора"})
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Сделка не найдена"})
    
    if trade["status"] != "pending":
        raise HTTPException(status_code=400, detail={"status": "error", "message": f"Нельзя отметить оплату. Текущий статус: {trade['status']}"})
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update trade status
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {"status": "paid", "paid_at": now}}
    )
    
    # Update invoice status
    await db.merchant_invoices.update_one(
        {"id": invoice_id},
        {"$set": {"status": "paid", "paid_at": now, "updated_at": now}}
    )
    
    # Send system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": f"✅ Клиент подтвердил оплату {trade['amount_rub']:,.0f} ₽. Трейдер, проверьте поступление средств на ваши реквизиты.",
        "created_at": now
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Create notification for trader
    try:
        await db.event_notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": trade["trader_id"],
            "type": "trade_payment",
            "title": "Оплата получена",
            "message": f"Клиент оплатил сделку на {trade['amount_rub']:,.0f} ₽",
            "link": f"/trader/sales/{trade_id}",
            "read": False,
            "created_at": now
        })
    except:
        pass
    
    # Send webhook
    from routes.trades import send_merchant_webhook_on_trade
    trade["invoice_id"] = invoice_id  # Ensure invoice_id is set
    await send_merchant_webhook_on_trade(trade, "paid", {"trade_id": trade_id, "paid_at": now})
    
    return {
        "status": "success",
        "message": "Оплата отмечена. Ожидайте подтверждения от оператора.",
        "trade_status": "paid"
    }


@router.get("/{invoice_id}/messages")
async def get_invoice_messages(
    invoice_id: str,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """
    White-label: Получить сообщения чата для инвойса.
    Мерчант может отображать чат на СВОЁМ сайте.
    """
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={"status": "error", "message": "Неверный API ключ"})
    
    invoice = await db.merchant_invoices.find_one({"id": invoice_id, "merchant_id": merchant["id"]}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Инвойс не найден"})
    
    trade_id = invoice.get("trade_id")
    if not trade_id:
        return {"status": "success", "messages": []}
    
    messages = await db.trade_messages.find(
        {"trade_id": trade_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    # Format messages for client
    formatted = []
    for msg in messages:
        formatted.append({
            "id": msg.get("id"),
            "sender": "system" if msg.get("sender_type") == "system" else ("operator" if msg.get("sender_type") == "trader" else "client"),
            "text": msg.get("content"),
            "timestamp": msg.get("created_at")
        })
    
    return {"status": "success", "messages": formatted}


class SendMessageRequest(BaseModel):
    text: str


@router.post("/{invoice_id}/messages")
async def send_invoice_message(
    invoice_id: str,
    request: SendMessageRequest,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """
    White-label: Отправить сообщение от клиента в чат.
    Мерчант отправляет сообщения от имени клиента.
    """
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={"status": "error", "message": "Неверный API ключ"})
    
    invoice = await db.merchant_invoices.find_one({"id": invoice_id, "merchant_id": merchant["id"]}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Инвойс не найден"})
    
    trade_id = invoice.get("trade_id")
    if not trade_id:
        raise HTTPException(status_code=400, detail={"status": "error", "message": "Сначала выберите оператора"})
    
    now = datetime.now(timezone.utc).isoformat()
    
    message = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": f"client_{invoice_id}",
        "sender_type": "buyer",
        "content": request.text,
        "created_at": now
    }
    await db.trade_messages.insert_one(message)
    
    # Notify trader about new message
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if trade:
        try:
            await db.event_notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": trade["trader_id"],
                "type": "trade_message",
                "title": "Новое сообщение",
                "message": f"Клиент: {request.text[:50]}...",
                "link": f"/trader/sales/{trade_id}",
                "read": False,
                "created_at": now
            })
        except:
            pass
    
    return {
        "status": "success",
        "message": {
            "id": message["id"],
            "sender": "client",
            "text": request.text,
            "timestamp": now
        }
    }


@router.get("/transactions")
async def get_merchant_transactions(
    x_api_key: str = Header(..., alias="X-Api-Key"),
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Получить список транзакций мерчанта"""
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Неверный API ключ"
        })
    
    query = {"merchant_id": merchant["id"]}
    
    if status:
        if status == "active":
            query["status"] = {"$in": ["pending", "waiting_requisites", "waiting_payment"]}
        elif status == "completed":
            query["status"] = {"$in": ["paid", "completed"]}
        else:
            query["status"] = status
    
    # Get from merchant_invoices
    invoices = await db.merchant_invoices.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    # Also get from trades with this merchant_id
    trades = await db.trades.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    # Combine and sort
    all_transactions = invoices + trades
    all_transactions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    all_transactions = all_transactions[:limit]
    
    total_invoices = await db.merchant_invoices.count_documents(query)
    total_trades = await db.trades.count_documents(query)
    total = total_invoices + total_trades
    
    return {
        "status": "success",
        "data": {
            "transactions": all_transactions,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    }


@router.get("/stats")
async def get_merchant_stats(
    x_api_key: str = Header(..., alias="X-Api-Key"),
    period: str = "today"
):
    """Статистика API для мерчанта"""
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
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
    
    total_invoices = await db.merchant_invoices.count_documents(base_query)
    
    paid_query = {**base_query, "status": {"$in": ["paid", "completed"]}}
    pending_query = {**base_query, "status": {"$in": ["pending", "waiting_requisites", "waiting_payment"]}}
    failed_query = {**base_query, "status": {"$in": ["failed", "cancelled", "expired"]}}
    
    paid_count = await db.merchant_invoices.count_documents(paid_query)
    pending_count = await db.merchant_invoices.count_documents(pending_query)
    failed_count = await db.merchant_invoices.count_documents(failed_query)
    
    # Volume calculation
    pipeline = [
        {"$match": paid_query},
        {"$group": {
            "_id": None,
            "total_rub": {"$sum": "$amount_rub"},
            "total_usdt": {"$sum": "$amount_usdt"}
        }}
    ]
    
    amounts = await db.merchant_invoices.aggregate(pipeline).to_list(1)
    total_rub = amounts[0]["total_rub"] if amounts else 0
    total_usdt = amounts[0]["total_usdt"] if amounts else 0
    
    avg_amount = total_rub / paid_count if paid_count > 0 else 0
    conversion_rate = (paid_count / total_invoices * 100) if total_invoices > 0 else 0
    
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
                "failed": failed_count
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


@router.get("/docs")
async def get_api_documentation():
    """Получить документацию API"""
    return {
        "api_version": "v1",
        "base_url": "/api/v1/invoice",
        "authentication": {
            "header": "X-Api-Key",
            "description": "API ключ выдается при одобрении мерчанта"
        },
        "endpoints": {
            "GET /payment-methods": "Получить список доступных способов оплаты",
            "POST /create": "Создание инвойса на оплату",
            "GET /status": "Проверка статуса платежа",
            "GET /transactions": "Список транзакций мерчанта",
            "GET /stats": "Статистика API usage"
        },
        "statuses": {
            "waiting_requisites": "Ожидание реквизитов от трейдера",
            "pending": "Ожидает оплаты",
            "paid": "Оплачен",
            "completed": "Завершён",
            "failed": "Ошибка/Отмена",
            "expired": "Истёк срок"
        }
    }



# ================== LINK TRADE TO INVOICE ==================

from pydantic import BaseModel as PydanticBaseModel

class LinkTradeRequest(PydanticBaseModel):
    trade_id: str


@router.patch("/{invoice_id}/link-trade")
async def link_trade_to_invoice(invoice_id: str, request: LinkTradeRequest):
    """Link a trade to an invoice (called when buyer selects operator)"""
    invoice = await db.merchant_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Update invoice with trade_id
    await db.merchant_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "trade_id": request.trade_id,
            "status": "pending",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Also update trade with invoice_id (needed for webhook routing)
    await db.trades.update_one(
        {"id": request.trade_id},
        {"$set": {"invoice_id": invoice_id}}
    )
    
    return {"status": "success", "message": "Trade linked to invoice"}



# ================== MERCHANT DISPUTE MANAGEMENT ==================

class DisputeOpenRequest(PydanticBaseModel):
    trade_id: Optional[str] = None
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    reason: str = ""

class DisputeMessageRequest(PydanticBaseModel):
    trade_id: Optional[str] = None
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    message: str


@router.get("/disputes")
async def get_merchant_disputes(
    status: Optional[str] = None,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """Get all disputed trades for a merchant.
    Optional filter: status=disputed|completed|cancelled
    """
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Invalid API key"
        })

    query = {"merchant_id": merchant["id"]}
    if status:
        query["status"] = status
    else:
        query["status"] = {"$in": ["disputed", "completed", "cancelled"]}

    trades = await db.trades.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)

    result = []
    for trade in trades:
        invoice = await db.merchant_invoices.find_one(
            {"trade_id": trade["id"]}, {"_id": 0, "id": 1, "external_order_id": 1}
        )
        result.append({
            "trade_id": trade["id"],
            "payment_id": invoice["id"] if invoice else None,
            "order_id": invoice.get("external_order_id") if invoice else None,
            "status": trade["status"],
            "amount_rub": trade.get("client_amount_rub") or trade.get("amount_rub"),  # Запрошенная сумма клиента
            "client_amount_rub": trade.get("client_amount_rub"),
            "amount_usdt": trade.get("amount_usdt"),
            "disputed_at": trade.get("disputed_at"),
            "disputed_by": trade.get("disputed_by"),
            "dispute_reason": trade.get("dispute_reason"),
            "dispute_resolved_at": trade.get("dispute_resolved_at"),
            "dispute_resolution": trade.get("dispute_resolution"),
            "created_at": trade.get("created_at")
        })

    return {"status": "success", "data": result, "total": len(result)}


@router.post("/dispute/open")
async def merchant_open_dispute(
    data: DisputeOpenRequest,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """Merchant opens a dispute on a trade.
    Provide trade_id, payment_id, or order_id to identify the trade.
    """
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Invalid API key"
        })

    trade = None
    if data.trade_id:
        trade = await db.trades.find_one({"id": data.trade_id, "merchant_id": merchant["id"]}, {"_id": 0})
    elif data.payment_id or data.order_id:
        invoice_query = {"merchant_id": merchant["id"]}
        if data.payment_id:
            invoice_query["id"] = data.payment_id
        else:
            invoice_query["external_order_id"] = data.order_id
        invoice = await db.merchant_invoices.find_one(invoice_query, {"_id": 0})
        if invoice and invoice.get("trade_id"):
            trade = await db.trades.find_one({"id": invoice["trade_id"]}, {"_id": 0})

    if not trade:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "TRADE_NOT_FOUND",
            "message": "Trade not found or does not belong to this merchant"
        })

    if trade["status"] == "disputed":
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "ALREADY_DISPUTED",
            "message": "Trade is already in dispute"
        })

    if trade["status"] not in ["paid", "pending"]:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_STATUS",
            "message": f"Cannot open dispute on trade with status '{trade['status']}'. Only paid/pending trades can be disputed."
        })

    reason = data.reason or "Dispute opened by merchant"

    await db.trades.update_one(
        {"id": trade["id"]},
        {"$set": {
            "status": "disputed",
            "disputed_at": datetime.now(timezone.utc).isoformat(),
            "dispute_reason": reason,
            "disputed_by": f"merchant:{merchant['id']}"
        }}
    )

    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade["id"],
        "sender_id": "system",
        "sender_type": "system",
        "content": f"\u26a0\ufe0f Спор открыт мерчантом! Причина: {reason}. Администратор подключится к чату.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)

    existing_conv = await db.unified_conversations.find_one(
        {"related_id": trade["id"], "type": {"$in": ["p2p_dispute", "p2p_trade"]}},
        {"_id": 0}
    )
    if existing_conv:
        await db.unified_conversations.update_one(
            {"id": existing_conv["id"]},
            {"$set": {"status": "disputed", "archived": False, "resolved": False}}
        )
    else:
        new_conv = {
            "id": str(uuid.uuid4()),
            "type": "p2p_dispute",
            "related_id": trade["id"],
            "status": "disputed",
            "title": f"Спор: {round(trade.get('amount_rub', 0)):,} ₽",
            "participants": [trade.get("trader_id"), f"merchant:{merchant['id']}"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "archived": False,
            "resolved": False,
            "unread_counts": {}
        }
        await db.unified_conversations.insert_one(new_conv)

    try:
        await send_webhook_notification(
            None, "disputed",
            extra_data={"trade_id": trade["id"], "reason": reason, "opened_by": "merchant"}
        )
    except Exception:
        pass

    return {
        "status": "success",
        "data": {
            "trade_id": trade["id"],
            "status": "disputed",
            "reason": reason,
            "disputed_at": datetime.now(timezone.utc).isoformat()
        }
    }


@router.get("/dispute/messages")
async def get_merchant_dispute_messages(
    trade_id: Optional[str] = None,
    payment_id: Optional[str] = None,
    order_id: Optional[str] = None,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """Get dispute chat messages. Merchant can read all messages in disputes for their trades."""
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Invalid API key"
        })

    trade = None
    if trade_id:
        trade = await db.trades.find_one({"id": trade_id, "merchant_id": merchant["id"]}, {"_id": 0})
    elif payment_id or order_id:
        invoice_query = {"merchant_id": merchant["id"]}
        if payment_id:
            invoice_query["id"] = payment_id
        else:
            invoice_query["external_order_id"] = order_id
        invoice = await db.merchant_invoices.find_one(invoice_query, {"_id": 0})
        if invoice and invoice.get("trade_id"):
            trade = await db.trades.find_one({"id": invoice["trade_id"]}, {"_id": 0})

    if not trade:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "TRADE_NOT_FOUND",
            "message": "Trade not found or does not belong to this merchant"
        })

    messages = await db.trade_messages.find(
        {"trade_id": trade["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)

    clean_messages = []
    for msg in messages:
        clean_messages.append({
            "id": msg.get("id"),
            "sender_type": msg.get("sender_type", "unknown"),
            "sender_id": msg.get("sender_id"),
            "content": msg.get("content"),
            "created_at": msg.get("created_at")
        })

    return {
        "status": "success",
        "data": {
            "trade_id": trade["id"],
            "trade_status": trade["status"],
            "messages": clean_messages,
            "total": len(clean_messages)
        }
    }


@router.post("/dispute/message")
async def merchant_send_dispute_message(
    data: DisputeMessageRequest,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """Merchant sends a message in a dispute chat."""
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail={
            "status": "error",
            "code": "INVALID_API_KEY",
            "message": "Invalid API key"
        })

    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "EMPTY_MESSAGE",
            "message": "Message cannot be empty"
        })

    trade = None
    if data.trade_id:
        trade = await db.trades.find_one({"id": data.trade_id, "merchant_id": merchant["id"]}, {"_id": 0})
    elif data.payment_id or data.order_id:
        invoice_query = {"merchant_id": merchant["id"]}
        if data.payment_id:
            invoice_query["id"] = data.payment_id
        else:
            invoice_query["external_order_id"] = data.order_id
        invoice = await db.merchant_invoices.find_one(invoice_query, {"_id": 0})
        if invoice and invoice.get("trade_id"):
            trade = await db.trades.find_one({"id": invoice["trade_id"]}, {"_id": 0})

    if not trade:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "TRADE_NOT_FOUND",
            "message": "Trade not found or does not belong to this merchant"
        })

    if trade["status"] not in ["disputed", "paid", "completed"]:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "CANNOT_MESSAGE",
            "message": f"Cannot send messages in trade with status '{trade['status']}'"
        })

    merchant_name = merchant.get("name", merchant.get("login", "Merchant"))

    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade["id"],
        "sender_id": f"merchant:{merchant['id']}",
        "sender_type": "merchant",
        "sender_name": merchant_name,
        "content": data.message.strip(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(msg)

    try:
        from routes.ws_routes import ws_manager
        if ws_manager:
            await ws_manager.broadcast(f"trade_{trade['id']}", {
                "type": "new_message",
                "message": {k: v for k, v in msg.items() if k != "_id"}
            })
    except Exception:
        pass

    return {
        "status": "success",
        "data": {
            "message_id": msg["id"],
            "trade_id": trade["id"],
            "created_at": msg["created_at"]
        }
    }



# ================== WEBHOOK TESTING FOR DEMO SHOP ==================

@router.post("/test-webhook-receiver")
async def test_webhook_receiver(request: Request):
    """
    Test webhook receiver for demo shop.
    Stores incoming webhooks in DB for display in demo shop UI.
    This endpoint receives webhooks from the system (no auth required).
    """
    body = await request.json()
    
    # Extract merchant_id from payment_id (invoice)
    payment_id = body.get("payment_id")
    merchant_id = None
    
    if payment_id:
        invoice = await db.merchant_invoices.find_one({"id": payment_id}, {"_id": 0})
        if invoice:
            merchant_id = invoice.get("merchant_id")
    
    # Store webhook for demo display
    webhook_record = {
        "id": f"twh_{secrets.token_hex(8)}",
        "merchant_id": merchant_id,
        "payload": body,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "status": body.get("status"),
        "payment_id": payment_id,
        "order_id": body.get("order_id"),
        "amount": body.get("amount")
    }
    await db.test_webhooks.insert_one(webhook_record)
    
    return {"status": "ok"}


@router.get("/test-webhooks")
async def get_test_webhooks(
    limit: int = 20,
    x_api_key: str = Header(..., alias="X-Api-Key")
):
    """
    Get list of received test webhooks for demo shop.
    """
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    webhooks = await db.test_webhooks.find(
        {"merchant_id": merchant["id"]},
        {"_id": 0}
    ).sort("received_at", -1).limit(limit).to_list(limit)
    
    return {"webhooks": webhooks}


@router.delete("/test-webhooks")
async def clear_test_webhooks(x_api_key: str = Header(..., alias="X-Api-Key")):
    """
    Clear all test webhooks for demo shop.
    """
    merchant = await db.merchants.find_one({"api_key": x_api_key}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    await db.test_webhooks.delete_many({"merchant_id": merchant["id"]})
    
    return {"status": "ok", "message": "Webhooks cleared"}
