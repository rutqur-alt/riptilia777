from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from core.database import db
from .models import MarkPaidRequest
from .utils import verify_merchant

router = APIRouter()

@router.post("/invoice/paid")
async def mark_invoice_paid(data: MarkPaidRequest):
    """
    Отметить счёт как оплаченный (клиент нажал "Я оплатил").
    """
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Get invoice
    invoice = await db.merchant_invoices.find_one(
        {"id": data.invoice_id, "merchant_id": data.merchant_id}
    )
    if not invoice:
        raise HTTPException(status_code=404, detail={"success": False, "error": "INVOICE_NOT_FOUND"})
    
    if invoice["status"] != "pending":
        return {"success": True, "status": invoice["status"], "message": "Already processed"}
    
    # Update status
    await db.merchant_invoices.update_one(
        {"id": data.invoice_id},
        {"$set": {
            "status": "paid",
            "paid_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Update trade if exists
    if invoice.get("trade_id"):
        await db.trades.update_one(
            {"id": invoice["trade_id"]},
            {"$set": {"status": "paid"}}
        )
        
        # Notify trader via WS
        try:
            from routes.ws_routes import ws_manager
            trade = await db.trades.find_one({"id": invoice["trade_id"]})
            if trade:
                await ws_manager.broadcast(f"user_{trade['trader_id']}", {
                    "type": "trade_update",
                    "trade_id": trade["id"],
                    "status": "paid"
                })
        except ImportError:
            pass
    
    return {
        "success": True,
        "status": "paid"
    }
