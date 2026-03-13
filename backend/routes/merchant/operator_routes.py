from fastapi import APIRouter, HTTPException
from core.database import db
from .models import OperatorsRequest
from .utils import verify_merchant

router = APIRouter()

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
        "is_active": True,
        "available_usdt": {"$gte": required_usdt * 0.9}  # 90% tolerance
    }, {"_id": 0}).to_list(100)
    
    operators = []
    for offer in offers:
        # Get trader info
        trader = await db.traders.find_one(
            {"id": offer["trader_id"]},
            {"_id": 0, "login": 1, "nickname": 1, "is_online": 1, "rating": 1, "completed_trades": 1}
        )
        if not trader:
            continue
            
        # Calculate price for client
        # client_pays = amount_rub * (price_rub / base_rate)
        # But here we just return the rate
        
        operators.append({
            "operator_id": offer["trader_id"],
            "operator_name": trader.get("nickname", trader.get("login")),
            "rating": trader.get("rating", 5.0),
            "completed_trades": trader.get("completed_trades", 0),
            "is_online": trader.get("is_online", False),
            "methods": offer.get("methods", []),
            "min_limit": offer.get("min_amount_rub", 500),
            "max_limit": offer.get("max_amount_rub", 100000),
            "rate": offer.get("price_rub", 90.0)
        })
    
    return {
        "success": True,
        "operators": operators
    }
