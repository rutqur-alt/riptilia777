from fastapi import APIRouter, HTTPException
from core.database import db
from .models import AuthRequest
from .utils import verify_merchant

router = APIRouter()

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
