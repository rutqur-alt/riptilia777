from fastapi import APIRouter, HTTPException
from core.database import db
from .models import BalanceRequest
from .utils import verify_merchant

router = APIRouter()

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
