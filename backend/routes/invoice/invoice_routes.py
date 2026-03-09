from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Request
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging
import random

from core.database import db
from .models import InvoiceCreateRequest, InvoiceStatusRequest
from .utils import generate_id, check_rate_limit, get_rate_limit_info, verify_signature

router = APIRouter()
logger = logging.getLogger(__name__)

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
        "status": "active",
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat()
    }
    await db.payment_links.insert_one(payment_link)
    
    # 12. Return response
    payment_url = f"https://secure-payments.st/select-operator/{invoice_id}"
    
    return {
        "status": "success",
        "invoice_id": invoice_id,
        "payment_url": payment_url,
        "amount": total_amount,
        "currency": "RUB",
        "expires_at": expires_at.isoformat()
    }


@router.get("/status")
async def get_invoice_status(
    merchant_id: str,
    order_id: Optional[str] = None,
    payment_id: Optional[str] = None,
    sign: str = None
):
    """Проверка статуса инвойса"""
    
    # 1. Verify API key (implicitly via merchant_id lookup for now, but better via header)
    # For GET requests, we usually use query params, but let's check if we can get merchant by ID
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "MERCHANT_NOT_FOUND",
            "message": "Мерчант не найден"
        })
    
    # 2. Check rate limit
    if not check_rate_limit(merchant_id, "status"):
        rate_info = get_rate_limit_info(merchant_id, "status")
        raise HTTPException(status_code=429, detail={
            "status": "error",
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Превышен лимит запросов. Повторите через {rate_info['reset_in']} сек."
        })
    
    # 3. Verify signature
    sign_data = {"merchant_id": merchant_id}
    if order_id:
        sign_data["order_id"] = order_id
    if payment_id:
        sign_data["payment_id"] = payment_id
        
    secret_key = merchant.get("api_secret") or merchant.get("api_key", "")
    
    if not verify_signature(sign_data, sign, secret_key):
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_SIGNATURE",
            "message": "Неверная подпись запроса"
        })
    
    # 4. Find invoice
    query = {"merchant_id": merchant_id}
    if payment_id:
        query["id"] = payment_id
    elif order_id:
        query["external_order_id"] = order_id
    else:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "MISSING_PARAMETERS",
            "message": "Необходимо указать order_id или payment_id"
        })
        
    invoice = await db.merchant_invoices.find_one(query, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "INVOICE_NOT_FOUND",
            "message": "Инвойс не найден"
        })
    
    return {
        "status": "success",
        "invoice": {
            "payment_id": invoice["id"],
            "order_id": invoice.get("external_order_id"),
            "status": invoice["status"],
            "amount": invoice.get("original_amount_rub") or invoice.get("amount_rub"),
            "amount_usdt": invoice.get("amount_usdt"),
            "created_at": invoice["created_at"],
            "paid_at": invoice.get("paid_at")
        }
    }
