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
    
    # Get stats
    completed = await db.trades.count_documents({
        "merchant_id": data.merchant_id, 
        "status": "completed"
    })
    
    # Sum of completed amounts (merchant_receives_rub)
    pipeline = [
        {"$match": {"merchant_id": data.merchant_id, "status": "completed"}},
        {"$group": {"_id": None, "total_rub": {"$sum": "$merchant_receives_rub"}}}
    ]
    agg = await db.trades.aggregate(pipeline).to_list(1)
    total_received = agg[0]["total_rub"] if agg else 0
    
    balance_usdt = merchant.get("balance_usdt", 0)
    balance_rub = round(balance_usdt * base_rate, 2)
    
    return {
        "success": True,
        "merchant_id": merchant["id"],
        "merchant_name": merchant.get("merchant_name") or merchant.get("login"),
        "balance_usdt": round(balance_usdt, 2),
        "balance_rub": balance_rub,
        "commission_rate": merchant.get("commission_rate", 10.0),
        "total_received_rub": round(total_received, 2),
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
        "expires_at": expires_at.isoformat(),
        "payment_url": f"/shop/pay/{invoice_id}"
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
            "amount_rub": trade.get("amount_rub"),
            "client_paid_rub": trade.get("client_pays_rub"),
            "merchant_receives_rub": trade.get("merchant_receives_rub"),
            "trade_id": trade.get("id"),
            "completed_at": trade.get("completed_at")
        }
    
    return {
        "success": True,
        "invoice_id": invoice.get("id"),
        "status": invoice.get("status"),
        "amount_rub": invoice.get("amount_rub"),
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
    
    # Stats - считаем merchant_receives_rub
    pipeline = [
        {"$match": {"merchant_id": data.merchant_id, "status": "completed"}},
        {"$group": {
            "_id": None,
            "total_rub": {"$sum": "$merchant_receives_rub"},
            "total_usdt": {"$sum": "$merchant_receives_usdt"},
            "count": {"$sum": 1}
        }}
    ]
    agg = await db.trades.aggregate(pipeline).to_list(1)
    stats = agg[0] if agg else {"total_rub": 0, "total_usdt": 0, "count": 0}
    
    balance_usdt = merchant.get("balance_usdt", 0)
    balance_rub = round(balance_usdt * base_rate, 2)
    
    return {
        "success": True,
        "balance_usdt": round(balance_usdt, 4),
        "balance_rub": balance_rub,
        "total_received_rub": round(stats.get("total_rub", 0), 2),
        "total_received_usdt": round(stats.get("total_usdt", 0), 4),
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
        {"_id": 0, "id": 1, "amount_rub": 1, "client_pays_rub": 1, 
         "merchant_receives_rub": 1, "merchant_receives_usdt": 1,
         "status": 1, "created_at": 1, "completed_at": 1}
    ).sort("created_at", -1).skip(data.offset).limit(data.limit).to_list(data.limit)
    
    total = await db.trades.count_documents(query)
    
    return {
        "success": True,
        "transactions": trades,
        "total": total
    }
