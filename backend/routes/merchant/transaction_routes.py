from fastapi import APIRouter, HTTPException
from core.database import db
from .models import TransactionsRequest
from .utils import verify_merchant

router = APIRouter()

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
