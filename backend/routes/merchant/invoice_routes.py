from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone, timedelta
import secrets
from core.database import db
from .models import CreateInvoiceRequest
from .utils import verify_merchant, verify_signature

router = APIRouter()

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
