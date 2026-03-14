from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from routes.ton_finance import (
    get_ton_service_health,
    get_deposit_address,
    get_user_ton_balance,
    get_user_transactions
)
from .dependencies import get_current_user_from_token

router = APIRouter()

@router.get("/wallet/health")
async def wallet_health():
    """Check TON service health"""
    health = await get_ton_service_health()
    return health


@router.get("/wallet/deposit-address")
async def get_user_deposit_address(user: dict = Depends(get_current_user_from_token)):
    """
    Get deposit address and memo for current user.
    User should send USDT to this address with the provided comment (deposit_code).
    """
    try:
        # Get user's short deposit code from database
        user_id = user['id']
        role = user.get('role', 'trader')
        
        collection = db.traders if role == 'trader' else db.merchants
        user_doc = await collection.find_one({"id": user_id}, {"_id": 0, "deposit_code": 1})
        
        deposit_code = user_doc.get('deposit_code') if user_doc else None
        
        # If no deposit code exists, generate one
        if not deposit_code:
            import random
            for _ in range(100):
                code = str(random.randint(100000, 999999))
                existing = await db.traders.find_one({"deposit_code": code})
                if not existing:
                    existing = await db.merchants.find_one({"deposit_code": code})
                if not existing:
                    deposit_code = code
                    await collection.update_one({"id": user_id}, {"$set": {"deposit_code": code}})
                    break
        
        # Get hot wallet address from TON service
        result = await get_deposit_address(user_id)
        
        return {
            "success": True,
            "deposit_info": {
                "address": result['address'],
                "comment": deposit_code,  # Use short 6-digit code
                "network": result['network'],
                "instructions": [
                    f"1. Отправьте USDT (сеть TON) на адрес: {result['address']}",
                    f"2. ОБЯЗАТЕЛЬНО укажите комментарий: {deposit_code}",
                    "3. Дождитесь подтверждения сети (1-2 минуты)",
                    "4. Баланс зачислится автоматически"
                ]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TON service unavailable: {str(e)}")


@router.get("/wallet/balance")
async def get_wallet_balance(user: dict = Depends(get_current_user_from_token)):
    """Get current user's USDT balance"""
    try:
        result = await get_user_ton_balance(user['id'])
        return {
            "success": True,
            "balance": {
                "usdt": result.get('balance_usdt', 0),
                "frozen_usdt": result.get('frozen_usd', 0),
                "available_usdt": result.get('available_usd', 0),
                # Legacy fields for compatibility
                "ton": result.get('balance_usdt', 0),
                "usd": result.get('balance_usdt', 0),
                "frozen_ton": result.get('frozen_usd', 0),
                "frozen_usd": result.get('frozen_usd', 0),
                "available_ton": result.get('available_usd', 0),
                "available_usd": result.get('available_usd', 0)
            }
        }
    except Exception as e:
        if "User not found" in str(e) or "not found" in str(e).lower():
            return {
                "success": True,
                "balance": {
                    "usdt": 0.0,
                    "frozen_usdt": 0.0,
                    "available_usdt": 0.0,
                    "ton": 0.0,
                    "usd": 0.0,
                    "frozen_ton": 0.0,
                    "frozen_usd": 0.0,
                    "available_ton": 0.0,
                    "available_usd": 0.0
                }
            }
        raise HTTPException(status_code=500, detail=f"TON service error: {str(e)}")


@router.get("/wallet/transactions")
async def get_wallet_transactions(
    limit: int = 50,
    offset: int = 0,
    type: str = None,
    status: str = None,
    user: dict = Depends(get_current_user_from_token)
):
    """Get user's transaction history with optional filters"""
    try:
        result = await get_user_transactions(user['id'], limit, offset)
        transactions = result.get('transactions', [])
        
        # Apply filters
        if type and type != 'all':
            transactions = [t for t in transactions if t.get('type') == type]
        if status and status != 'all':
            transactions = [t for t in transactions if t.get('status') == status]
        
        return {
            "success": True,
            "transactions": transactions,
            "count": len(transactions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
