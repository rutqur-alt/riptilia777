from fastapi import APIRouter, HTTPException
from core.database import db
from .models import InvoiceStatusRequest
from .utils import verify_merchant

router = APIRouter()

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
