from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field
from typing import Optional
import os

from core.database import db as mongodb
from routes.ton_finance import create_audit_log
from .dependencies import require_roles

router = APIRouter()

class BalanceAdjustRequest(BaseModel):
    user_id: str
    amount: float = Field(..., description="Positive to add, negative to subtract")
    reason: str = Field(..., min_length=5, description="Reason for adjustment")

class BalanceNotification(BaseModel):
    user_id: str
    amount: float
    reason: str


@router.post("/admin/users/adjust-balance")
async def adjust_user_balance(
    data: BalanceAdjustRequest,
    request: Request,
    user: dict = Depends(require_roles(["admin"]))
):
    """Adjust user balance (admin only, requires reason)"""
    try:
        # Find user
        trader = await mongodb.traders.find_one({"id": data.user_id})
        is_trader = bool(trader)
        
        if trader:
            old_balance = trader.get("balance_usdt", 0)
            new_balance = old_balance + data.amount
            
            if new_balance < 0:
                raise HTTPException(status_code=400, detail="Баланс не может быть отрицательным")
            
            await mongodb.traders.update_one(
                {"id": data.user_id},
                {"$set": {"balance_usdt": new_balance}}
            )
        else:
            merchant = await mongodb.merchants.find_one({"id": data.user_id})
            if not merchant:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            
            old_balance = merchant.get("balance_usdt", 0)
            new_balance = old_balance + data.amount
            
            if new_balance < 0:
                raise HTTPException(status_code=400, detail="Баланс не может быть отрицательным")
            
            await mongodb.merchants.update_one(
                {"id": data.user_id},
                {"$set": {"balance_usdt": new_balance}}
            )
        
        # Audit log
        await create_audit_log(
            admin_user_id=user['id'],
            action='adjust_balance',
            target_user_id=data.user_id,
            old_value={"balance": old_balance},
            new_value={"balance": new_balance, "adjustment": data.amount},
            details=data.reason,
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": f"Баланс изменен: {old_balance} → {new_balance} USDT",
            "old_balance": old_balance,
            "new_balance": new_balance,
            "adjustment": data.amount
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/internal/notify-balance-update")
async def notify_balance_update(
    data: BalanceNotification,
    x_internal_key: Optional[str] = Header(None)
):
    """Internal endpoint called by ton-service when balance changes"""
    # Verify internal key
    expected_key = os.environ.get('TON_SERVICE_API_KEY', 'ton-service-secret-key')
    if x_internal_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid internal key")
    
    try:
        from routes.websockets import ws_manager
        await ws_manager.broadcast(f"user_{data.user_id}", {
            "type": "balance_update",
            "amount": data.amount,
            "reason": data.reason
        })
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
