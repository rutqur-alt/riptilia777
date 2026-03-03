"""
Merchant Integration API - Боевое API для интеграции мерчантов
Все запросы с API Key + API Secret + Merchant ID
HMAC подпись для безопасности
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import hmac
import hashlib
import json
import secrets

from core.database import db

router = APIRouter(prefix="/merchant/v1", tags=["Merchant API"])


def generate_signature(api_secret: str, data: dict) -> str:
    """Generate HMAC-SHA256 signature"""
    sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hmac.new(
        api_secret.encode('utf-8'),
        sorted_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def verify_signature(api_secret: str, data: dict, provided_signature: str) -> bool:
    """Verify HMAC signature"""
    expected = generate_signature(api_secret, data)
    return hmac.compare_digest(expected, provided_signature)


async def verify_merchant(api_key: str, api_secret: str, merchant_id: str):
    """Verify all 3 credentials and return merchant"""
    merchant = await db.merchants.find_one({"api_key": api_key}, {"_id": 0})
    
    if not merchant:
        return None, "INVALID_API_KEY"
    
    if merchant.get("api_secret") != api_secret:
        return None, "INVALID_API_SECRET"
    
    if merchant.get("id") != merchant_id:
        return None, "INVALID_MERCHANT_ID"
    
    if merchant.get("status") != "active":
        return None, "MERCHANT_NOT_ACTIVE"
    
    return merchant, None


# ==================== AUTH ====================

class AuthRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str


@router.post("/auth")
async def authenticate(data: AuthRequest):
    """
    Проверка API ключей мерчанта.
    Возвращает информацию о мерчанте если ключи валидны.
    """
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    
    if error:
        raise HTTPException(status_code=401, detail={
            "success": False,
            "error": error,
            "message": {
                "INVALID_API_KEY": "Неверный API Key",
                "INVALID_API_SECRET": "Неверный API Secret",
                "INVALID_MERCHANT_ID": "Неверный Merchant ID",
                "MERCHANT_NOT_ACTIVE": "Мерчант не активен"
            }.get(error, "Ошибка авторизации")
        })
    
    # Get exchange rate
    payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = payout_settings.get("base_rate", 78.5) if payout_settings else 78.5
    
    # Get stats - client_amount and merchant_receives
    pipeline = [
        {"$match": {"merchant_id": data.merchant_id, "status": "completed"}},
        {"$group": {
            "_id": None, 
            "total_client_rub": {"$sum": "$client_amount_rub"},
            "total_merchant_rub": {"$sum": "$merchant_receives_rub"}
        }}
    ]
    agg = await db.trades.aggregate(pipeline).to_list(1)
    stats = agg[0] if agg else {"total_client_rub": 0, "total_merchant_rub": 0}
    
    # Get completed count
    completed = await db.trades.count_documents({
        "merchant_id": data.merchant_id, 
        "status": "completed"
    })
    
    balance_usdt = merchant.get("balance_usdt", 0)
    balance_rub = round(balance_usdt * base_rate, 2)
    
    return {
        "success": True,
        "merchant_id": merchant["id"],
        "merchant_name": merchant.get("merchant_name") or merchant.get("login"),
        "balance_usdt": round(balance_usdt, 2),
        "balance_rub": balance_rub,
        "commission_rate": merchant.get("commission_rate", 10.0),
        # Баланс клиента на сайте мерчанта
        "total_client_rub": round(stats.get("total_client_rub", 0), 2),
        # Баланс мерчанта
        "total_received_rub": round(stats.get("total_merchant_rub", 0), 2),
        "transactions_count": completed,
        "status": merchant.get("status"),
        "exchange_rate": base_rate
    }


# ==================== CREATE INVOICE ====================

class CreateInvoiceRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    amount_rub: int  # Сумма пополнения клиента (то что он получит на сайте мерчанта)
    order_id: Optional[str] = None
    description: Optional[str] = "Пополнение баланса"
    callback_url: Optional[str] = None
    signature: Optional[str] = None


@router.post("/invoice/create")
async def create_invoice(data: CreateInvoiceRequest):
    """
    Создать счёт на оплату.
    
    amount_rub = сумма которую клиент получит на сайте мерчанта (1000 RUB)
    Клиент заплатит: amount_rub + наценка трейдера
    Мерчант получит: amount_rub - комиссия площадки
    """
    # 1. Verify credentials
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={
            "success": False,
            "error": error
        })
    
    # 2. Verify signature if provided
    if data.signature:
        sign_data = {
            "api_key": data.api_key,
            "merchant_id": data.merchant_id,
            "amount_rub": data.amount_rub
        }
        if not verify_signature(data.api_secret, sign_data, data.signature):
            raise HTTPException(status_code=401, detail={
                "success": False,
                "error": "INVALID_SIGNATURE"
            })
    
    # 3. Get base exchange rate
    payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = payout_settings.get("base_rate", 78.0) if payout_settings else 78.0
    if not base_rate or base_rate <= 0:
        base_rate = 78.0
    
    # 4. Calculate amounts
    # amount_rub = что получит клиент на сайте мерчанта
    # amount_usdt = amount_rub / base_rate (базовый курс)
    amount_usdt = round(data.amount_rub / base_rate, 4)
    
    # Комиссия мерчанта (что площадка заберёт)
    # Мерчант получает: amount_rub - (amount_rub * commission%)
    merchant_commission = merchant.get("commission_rate", 10.0)  # По умолчанию 10%
    platform_fee_rub = round(data.amount_rub * merchant_commission / 100, 2)
    merchant_receives_rub = data.amount_rub - platform_fee_rub
    merchant_receives_usdt = round(merchant_receives_rub / base_rate, 4)
    
    # 5. Generate invoice ID
    invoice_id = f"INV_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4).upper()}"
    
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=1)
    
    # 6. Create invoice
    invoice = {
        "id": invoice_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant.get("merchant_name"),
        "external_order_id": data.order_id,
        
        # Суммы
        "amount_rub": data.amount_rub,  # Что получит клиент
        "amount_usdt": amount_usdt,
        "base_rate": base_rate,
        
        # Комиссии
        "merchant_commission_percent": merchant_commission,
        "platform_fee_rub": platform_fee_rub,
        "merchant_receives_rub": merchant_receives_rub,
        "merchant_receives_usdt": merchant_receives_usdt,
        
        # Meta
        "description": data.description,
        "callback_url": data.callback_url,
        "status": "pending",
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        
        # Will be set later
        "trader_id": None,
        "trade_id": None,
        "client_pays_rub": None,  # Будет известно после выбора трейдера
        "paid_at": None,
        "completed_at": None
    }
    
    await db.merchant_invoices.insert_one(invoice)
    
    # Also create payment_link for shop compatibility
    payment_link = {
        "id": invoice_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant.get("merchant_name"),
        "amount_rub": data.amount_rub,
        "amount_usdt": amount_usdt,
        "merchant_receives_rub": merchant_receives_rub,
        "merchant_receives_usdt": merchant_receives_usdt,
        "description": data.description,
        "status": "pending",
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat()
    }
    await db.payment_links.insert_one(payment_link)
    
    return {
        "success": True,
        "invoice_id": invoice_id,
        "amount_rub": data.amount_rub,
        "amount_usdt": amount_usdt,
        "merchant_commission_percent": merchant_commission,
        "merchant_receives_rub": merchant_receives_rub,
        "status": "pending",
        "expires_at": expires_at.isoformat()
    }


# ==================== INVOICE STATUS ====================

class InvoiceStatusRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    invoice_id: str


@router.post("/invoice/status")
async def get_invoice_status(data: InvoiceStatusRequest):
    """Получить статус счёта"""
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Get invoice
    invoice = await db.merchant_invoices.find_one(
        {"id": data.invoice_id, "merchant_id": data.merchant_id},
        {"_id": 0}
    )
    
    if not invoice:
        # Try find by trade
        trade = await db.trades.find_one(
            {"payment_link_id": data.invoice_id, "merchant_id": data.merchant_id},
            {"_id": 0}
        )
        if not trade:
            raise HTTPException(status_code=404, detail={
                "success": False,
                "error": "INVOICE_NOT_FOUND"
            })
        
        return {
            "success": True,
            "invoice_id": data.invoice_id,
            "status": trade.get("status"),
            "amount_rub": trade.get("client_amount_rub") or trade.get("amount_rub"),  # Запрошенная сумма клиента
            "client_amount_rub": trade.get("client_amount_rub"),  # Сумма пополнения клиента
            "client_paid_rub": trade.get("client_pays_rub"),  # Сколько клиент заплатил
            "merchant_receives_rub": trade.get("merchant_receives_rub"),  # Сколько получит мерчант
            "trade_id": trade.get("id"),
            "completed_at": trade.get("completed_at")
        }
    
    return {
        "success": True,
        "invoice_id": invoice.get("id"),
        "status": invoice.get("status"),
        "amount_rub": invoice.get("amount_rub"),  # Запрошенная сумма клиента (1000)
        "client_amount_rub": invoice.get("amount_rub"),  # То же самое для ясности
        "client_paid_rub": invoice.get("client_pays_rub"),
        "merchant_receives_rub": invoice.get("merchant_receives_rub"),
        "trade_id": invoice.get("trade_id"),
        "paid_at": invoice.get("paid_at"),
        "completed_at": invoice.get("completed_at")
    }


# ==================== BALANCE ====================

class BalanceRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str


@router.post("/balance")
async def get_balance(data: BalanceRequest):
    """Получить баланс мерчанта"""
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Get exchange rate
    payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = payout_settings.get("base_rate", 78.5) if payout_settings else 78.5
    
    # Stats - считаем client_amount_rub (что получили клиенты) и merchant_receives_rub (что получил мерчант)
    pipeline = [
        {"$match": {"merchant_id": data.merchant_id, "status": "completed"}},
        {"$group": {
            "_id": None,
            "total_client_rub": {"$sum": "$client_amount_rub"},  # Сумма пополнений клиентов
            "total_merchant_rub": {"$sum": "$merchant_receives_rub"},  # Что получил мерчант
            "total_merchant_usdt": {"$sum": "$merchant_receives_usdt"},
            "count": {"$sum": 1}
        }}
    ]
    agg = await db.trades.aggregate(pipeline).to_list(1)
    stats = agg[0] if agg else {"total_client_rub": 0, "total_merchant_rub": 0, "total_merchant_usdt": 0, "count": 0}
    
    balance_usdt = merchant.get("balance_usdt", 0)
    
    return {
        "success": True,
        "balance_usdt": round(balance_usdt, 4),
        # Баланс клиента на сайте мерчанта (сумма всех пополнений)
        "total_client_rub": round(stats.get("total_client_rub", 0), 2),
        # Баланс мерчанта в системе (минус комиссия)
        "total_received_rub": round(stats.get("total_merchant_rub", 0), 2),
        "total_received_usdt": round(stats.get("total_merchant_usdt", 0), 4),
        "transactions_count": stats.get("count", 0),
        "exchange_rate": base_rate
    }


# ==================== TRANSACTIONS ====================

class TransactionsRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    status: Optional[str] = None
    limit: int = 50
    offset: int = 0


@router.post("/transactions")
async def get_transactions(data: TransactionsRequest):
    """Получить список транзакций"""
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    query = {"merchant_id": data.merchant_id}
    if data.status:
        query["status"] = data.status
    
    trades = await db.trades.find(
        query,
        {"_id": 0, "id": 1, "client_amount_rub": 1, "amount_rub": 1, 
         "client_pays_rub": 1, "merchant_receives_rub": 1, 
         "status": 1, "created_at": 1, "completed_at": 1}
    ).sort("created_at", -1).skip(data.offset).limit(data.limit).to_list(data.limit)
    
    total = await db.trades.count_documents(query)
    
    return {
        "success": True,
        "transactions": trades,
        "total": total
    }



# ==================== OPERATORS ====================

class OperatorsRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    amount_rub: float


@router.post("/operators")
async def get_operators(data: OperatorsRequest):
    """
    Получить список доступных операторов для указанной суммы.
    Возвращает операторов с их курсами, лимитами и способами оплаты.
    """
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Get base rate
    rate_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = rate_settings.get("base_rate", 78) if rate_settings else 78
    
    # Calculate required USDT
    required_usdt = data.amount_rub / base_rate
    
    # Get active offers with enough balance
    offers = await db.offers.find({
        "status": "active",
        "available_usdt": {"$gte": required_usdt * 0.9}  # 90% tolerance
    }, {"_id": 0}).to_list(100)
    
    operators = []
    for offer in offers:
        # Get trader info
        trader = await db.traders.find_one(
            {"id": offer["trader_id"]},
            {"_id": 0, "login": 1, "nickname": 1, "success_rate": 1, "trades_count": 1, "is_online": 1}
        )
        if not trader:
            continue
        
        # Calculate amount to pay
        to_pay_rub = round(required_usdt * offer["price_rub"], 2)
        commission_percent = round((offer["price_rub"] - base_rate) / base_rate * 100, 2)
        
        # Get requisites
        requisites = []
        for req_id in offer.get("requisite_ids", []):
            req = await db.requisites.find_one({"id": req_id}, {"_id": 0, "id": 1, "type": 1, "data": 1})
            if req:
                requisites.append({
                    "id": req["id"],
                    "type": req["type"],
                    "bank_name": req.get("data", {}).get("bank_name", ""),
                })
        
        operators.append({
            "operator_id": offer["id"],
            "trader_id": offer["trader_id"],
            "nickname": trader.get("nickname") or trader.get("login"),
            "is_online": trader.get("is_online", False),
            "success_rate": trader.get("success_rate", 100),
            "trades_count": trader.get("trades_count", 0),
            "price_rub": offer["price_rub"],
            "to_pay_rub": to_pay_rub,
            "commission_percent": max(0, commission_percent),
            "min_amount_rub": round(offer.get("min_amount", 1) * offer["price_rub"], 2),
            "max_amount_rub": round(offer.get("available_usdt", 0) * offer["price_rub"], 2),
            "requisites": requisites
        })
    
    # Sort by price (cheapest first)
    operators.sort(key=lambda x: x["to_pay_rub"])
    
    return {
        "success": True,
        "amount_rub": data.amount_rub,
        "base_rate": base_rate,
        "operators": operators
    }


# ==================== REQUISITES ====================

class RequisitesRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    payment_id: str


@router.post("/invoice/requisites")
async def get_invoice_requisites(data: RequisitesRequest):
    """
    Получить реквизиты для оплаты счёта.
    Мерчант показывает эти реквизиты клиенту на своём сайте.
    """
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Find trade by payment_id (invoice_id)
    trade = await db.trades.find_one(
        {"payment_link_id": data.payment_id, "merchant_id": data.merchant_id},
        {"_id": 0}
    )
    
    if not trade:
        # Try to find invoice
        invoice = await db.merchant_invoices.find_one(
            {"id": data.payment_id, "merchant_id": data.merchant_id},
            {"_id": 0}
        )
        if not invoice:
            raise HTTPException(status_code=404, detail={"success": False, "error": "INVOICE_NOT_FOUND"})
        
        return {
            "success": True,
            "status": invoice.get("status", "pending"),
            "amount_rub": invoice.get("amount_rub"),
            "requisites": None,
            "message": "Счёт создан, но сделка ещё не начата. Клиент должен выбрать оператора."
        }
    
    # Get requisites from trade
    requisites_data = []
    for req in trade.get("requisites", []):
        requisites_data.append({
            "type": req.get("type"),
            "card_number": req.get("data", {}).get("card_number"),
            "phone": req.get("data", {}).get("phone"),
            "bank_name": req.get("data", {}).get("bank_name"),
            "card_holder": req.get("data", {}).get("card_holder"),
        })
    
    return {
        "success": True,
        "payment_id": data.payment_id,
        "trade_id": trade["id"],
        "status": trade["status"],
        "amount_rub": trade.get("amount_rub"),
        "client_amount_rub": trade.get("client_amount_rub"),
        "expires_at": trade.get("expires_at"),
        "requisites": requisites_data,
        "trader_login": trade.get("trader_login")
    }


# ==================== MARK PAID ====================

class MarkPaidRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    payment_id: str


@router.post("/invoice/mark-paid")
async def mark_invoice_paid(data: MarkPaidRequest):
    """
    Отметить счёт как оплаченный.
    Вызывается когда клиент на сайте мерчанта нажал "Я оплатил".
    """
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Find trade
    trade = await db.trades.find_one(
        {"payment_link_id": data.payment_id, "merchant_id": data.merchant_id},
        {"_id": 0}
    )
    
    if not trade:
        raise HTTPException(status_code=404, detail={"success": False, "error": "TRADE_NOT_FOUND"})
    
    if trade["status"] != "pending":
        raise HTTPException(status_code=400, detail={
            "success": False, 
            "error": "INVALID_STATUS",
            "message": f"Сделка в статусе '{trade['status']}', ожидался 'pending'"
        })
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.trades.update_one(
        {"id": trade["id"]},
        {"$set": {
            "status": "paid",
            "paid_at": now
        }}
    )
    
    # Send webhook
    await send_merchant_webhook(data.merchant_id, data.payment_id, "paid", {
        "trade_id": trade["id"],
        "paid_at": now
    })
    
    return {
        "success": True,
        "payment_id": data.payment_id,
        "trade_id": trade["id"],
        "status": "paid",
        "paid_at": now,
        "message": "Ожидайте подтверждения от оператора"
    }


# ==================== DISPUTES ====================

class OpenDisputeRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    payment_id: str
    reason: str = "Оплата не подтверждена оператором"


@router.post("/disputes/open")
async def open_dispute(data: OpenDisputeRequest):
    """
    Открыть спор по платежу.
    Спор можно открыть через 10 минут после отметки "оплачено".
    """
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Find trade
    trade = await db.trades.find_one(
        {"payment_link_id": data.payment_id, "merchant_id": data.merchant_id},
        {"_id": 0}
    )
    
    if not trade:
        raise HTTPException(status_code=404, detail={"success": False, "error": "TRADE_NOT_FOUND"})
    
    if trade["status"] not in ["paid", "pending"]:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "error": "INVALID_STATUS",
            "message": f"Спор можно открыть только для статусов 'pending' или 'paid'"
        })
    
    # Check 10 minute cooldown
    if trade.get("paid_at"):
        paid_at = datetime.fromisoformat(trade["paid_at"].replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - paid_at).total_seconds()
        if elapsed < 600:  # 10 minutes
            remaining = int(600 - elapsed)
            raise HTTPException(status_code=400, detail={
                "success": False,
                "error": "DISPUTE_COOLDOWN",
                "message": f"Спор можно открыть через {remaining} секунд"
            })
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.trades.update_one(
        {"id": trade["id"]},
        {"$set": {
            "status": "disputed",
            "disputed_at": now,
            "dispute_reason": data.reason,
            "dispute_opened_by": "merchant_client"
        }}
    )
    
    # Send webhook
    await send_merchant_webhook(data.merchant_id, data.payment_id, "disputed", {
        "trade_id": trade["id"],
        "reason": data.reason,
        "disputed_at": now
    })
    
    return {
        "success": True,
        "payment_id": data.payment_id,
        "trade_id": trade["id"],
        "status": "disputed",
        "reason": data.reason,
        "disputed_at": now
    }


class DisputeMessagesRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    payment_id: str


@router.post("/disputes/messages")
async def get_dispute_messages(data: DisputeMessagesRequest):
    """Получить сообщения спора"""
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Find trade
    trade = await db.trades.find_one(
        {"payment_link_id": data.payment_id, "merchant_id": data.merchant_id},
        {"_id": 0, "id": 1, "status": 1}
    )
    
    if not trade:
        raise HTTPException(status_code=404, detail={"success": False, "error": "TRADE_NOT_FOUND"})
    
    messages = await db.trade_messages.find(
        {"trade_id": trade["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    return {
        "success": True,
        "trade_id": trade["id"],
        "status": trade["status"],
        "messages": messages
    }


class SendDisputeMessageRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    payment_id: str
    message: str
    sender_name: str = "Клиент"


@router.post("/disputes/send-message")
async def send_dispute_message(data: SendDisputeMessageRequest):
    """Отправить сообщение в спор от имени клиента мерчанта"""
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Find trade
    trade = await db.trades.find_one(
        {"payment_link_id": data.payment_id, "merchant_id": data.merchant_id},
        {"_id": 0, "id": 1, "status": 1}
    )
    
    if not trade:
        raise HTTPException(status_code=404, detail={"success": False, "error": "TRADE_NOT_FOUND"})
    
    if trade["status"] != "disputed":
        raise HTTPException(status_code=400, detail={
            "success": False,
            "error": "NOT_IN_DISPUTE",
            "message": "Сообщения можно отправлять только в споре"
        })
    
    now = datetime.now(timezone.utc).isoformat()
    
    message_doc = {
        "id": f"msg_{secrets.token_hex(8)}",
        "trade_id": trade["id"],
        "sender_type": "client",
        "sender_role": "client",
        "sender_name": data.sender_name,
        "content": data.message,
        "created_at": now
    }
    
    await db.trade_messages.insert_one(message_doc)
    
    return {
        "success": True,
        "message_id": message_doc["id"],
        "created_at": now
    }


# ==================== WEBHOOK HELPER ====================

async def send_merchant_webhook(merchant_id: str, payment_id: str, status: str, extra_data: dict = None):
    """Отправить webhook мерчанту"""
    import httpx
    
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    if not merchant:
        return
    
    webhook_url = merchant.get("webhook_url")
    if not webhook_url:
        return
    
    # Find invoice for order_id
    invoice = await db.merchant_invoices.find_one({"id": payment_id}, {"_id": 0})
    
    payload = {
        "event": status,
        "payment_id": payment_id,
        "order_id": invoice.get("external_order_id", payment_id) if invoice else payment_id,
        "status": status,
        "amount_rub": invoice.get("amount_rub") if invoice else None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if extra_data:
        payload.update(extra_data)
    
    # Generate signature
    api_secret = merchant.get("api_secret", "")
    payload["sign"] = generate_signature(api_secret, {k: v for k, v in payload.items() if k != "sign"})
    
    # Save to webhook history
    webhook_record = {
        "id": f"whk_{secrets.token_hex(8)}",
        "merchant_id": merchant_id,
        "payment_id": payment_id,
        "event": status,
        "webhook_url": webhook_url,
        "payload": payload,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.webhook_history.insert_one(webhook_record)
    
    # Send webhook
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(webhook_url, json=payload)
            success = response.status_code == 200
            
            await db.webhook_history.update_one(
                {"id": webhook_record["id"]},
                {"$set": {
                    "status": "delivered" if success else "failed",
                    "response_code": response.status_code,
                    "delivered_at": datetime.now(timezone.utc).isoformat()
                }}
            )
    except Exception as e:
        await db.webhook_history.update_one(
            {"id": webhook_record["id"]},
            {"$set": {"status": "failed", "error": str(e)}}
        )
