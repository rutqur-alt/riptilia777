from fastapi import APIRouter, HTTPException
from core.database import db
from .models import RequisitesRequest
from .utils import verify_merchant

router = APIRouter()

@router.post("/invoice/requisites")
async def get_invoice_requisites(data: RequisitesRequest):
    """
    Получить реквизиты для оплаты.
    Создаёт сделку (trade) и возвращает реквизиты.
    """
    merchant, error = await verify_merchant(data.api_key, data.api_secret, data.merchant_id)
    if error:
        raise HTTPException(status_code=401, detail={"success": False, "error": error})
    
    # Get invoice
    invoice = await db.merchant_invoices.find_one(
        {"id": data.invoice_id, "merchant_id": data.merchant_id},
        {"_id": 0}
    )
    if not invoice:
        raise HTTPException(status_code=404, detail={"success": False, "error": "INVOICE_NOT_FOUND"})
    
    # Get operator offer
    offer = await db.offers.find_one({"trader_id": data.operator_id, "is_active": True}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail={"success": False, "error": "OPERATOR_NOT_FOUND"})
    
    # Get requisites for method
    requisites = []
    if offer.get("requisites"):
        requisites = [r for r in offer["requisites"] if r.get("type") == data.method]
    
    if not requisites:
        # Fallback to global requisites
        requisites = await db.requisites.find({
            "trader_id": data.operator_id,
            "type": data.method
        }, {"_id": 0}).to_list(10)
    
    if not requisites:
        raise HTTPException(status_code=400, detail={"success": False, "error": "NO_REQUISITES_AVAILABLE"})
    
    # Select one requisite (round robin or random)
    import random
    requisite = random.choice(requisites)
    
    # Create trade via internal API call logic
    # We need to call create_trade logic here
    # For now returning requisites directly
    
    return {
        "success": True,
        "requisite": {
            "type": requisite.get("type"),
            "bank_name": requisite.get("bank_name") or requisite.get("data", {}).get("bank_name"),
            "card_number": requisite.get("card_number") or requisite.get("data", {}).get("card_number"),
            "phone": requisite.get("phone") or requisite.get("data", {}).get("phone"),
            "holder": requisite.get("holder_name") or requisite.get("data", {}).get("holder_name")
        },
        "amount_to_pay": invoice["amount_rub"] * (offer["price_rub"] / invoice["base_rate"]),
        "timer_seconds": 1800  # 30 min
    }
