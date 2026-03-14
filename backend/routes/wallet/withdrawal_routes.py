from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
import uuid

from core.database import db as mongodb
from routes.ton_finance import (
    get_hot_wallet_balance,
    send_usdt_withdrawal
)
from .dependencies import get_current_user_from_token

router = APIRouter()

class WithdrawRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount in TON")
    to_address: str = Field(..., min_length=48, description="TON wallet address")
    two_fa_code: Optional[str] = Field(None, description="2FA code if enabled")
    comment: Optional[str] = Field("", description="Optional comment")


@router.post("/wallet/withdraw")
async def withdraw_ton(
    data: WithdrawRequest,
    request: Request,
    user: dict = Depends(get_current_user_from_token)
):
    """
    Request USDT withdrawal.
    1. Проверяет баланс
    2. Замораживает средства (balance -> frozen)
    3. Создает запись в withdrawal_requests со статусом pending
    4. Создает запись в истории транзакций
    """
    
    try:
        user_id = user['id']
        five_seconds_ago = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        
        # Check for duplicate request (anti double-click)
        recent_request = await mongodb.withdrawal_requests.find_one({
            "user_id": user_id,
            "amount": data.amount,
            "created_at": {"$gte": five_seconds_ago},
            "status": "pending"
        })
        
        if recent_request:
            raise HTTPException(
                status_code=429, 
                detail="Заявка уже создана. Подождите несколько секунд."
            )
        
        # Get user's current balance from MongoDB FIRST
        trader = await mongodb.traders.find_one({"id": user_id})
        is_trader = bool(trader)
        is_trusted = False
        
        if trader:
            current_balance = trader.get("balance_usdt", 0) or 0
            frozen_balance = trader.get("frozen_usdt", 0) or 0
            is_trusted = trader.get("is_trusted", False)
        else:
            merchant = await mongodb.merchants.find_one({"id": user_id})
            if not merchant:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            current_balance = merchant.get("balance_usdt", 0) or 0
            frozen_balance = merchant.get("frozen_usdt", 0) or 0
            is_trusted = merchant.get("is_trusted", False)
        
        available_balance = current_balance - frozen_balance
        
        # Check balance BEFORE creating anything
        if data.amount > available_balance:
            raise HTTPException(
                status_code=400, 
                detail=f"Недостаточно средств. Доступно: {available_balance:.2f} USDT"
            )
        
        if data.amount <= 0:
            raise HTTPException(status_code=400, detail="Сумма должна быть положительной")
        
        # Withdrawal fee (goes to platform)
        WITHDRAWAL_FEE = 1.0  # 1 USDT
        total_amount = data.amount + WITHDRAWAL_FEE  # Amount + fee
        
        # Check if user has enough for amount + fee
        if total_amount > available_balance:
            raise HTTPException(
                status_code=400, 
                detail=f"Недостаточно средств. Нужно: {total_amount:.2f} USDT (включая комиссию {WITHDRAWAL_FEE} USDT). Доступно: {available_balance:.2f} USDT"
            )
        
        # All checks passed - now create request ID
        request_id = f"wd_{uuid.uuid4().hex[:12]}"
        
        # FREEZE the total amount (amount + fee)
        # balance_usdt = total balance (includes frozen)
        # frozen_usdt = frozen amount (subset of total)
        # available = balance_usdt - frozen_usdt
        if is_trader:
            result = await mongodb.traders.update_one(
                {"id": user_id, "balance_usdt": {"$gte": frozen_balance + total_amount}},  # Check total >= frozen + amount + fee
                {"$inc": {"frozen_usdt": total_amount}}  # Freeze amount + fee
            )
        else:
            result = await mongodb.merchants.update_one(
                {"id": user_id, "balance_usdt": {"$gte": frozen_balance + total_amount}},
                {"$inc": {"frozen_usdt": total_amount}}  # Freeze amount + fee
            )
        
        # Check if balance was actually frozen
        if result.modified_count == 0:
            raise HTTPException(
                status_code=400, 
                detail="Не удалось заморозить средства. Проверьте баланс."
            )
        
        # Balance frozen successfully - now create withdrawal request
        # Trusted users get auto-approved status
        withdrawal_status = "approved" if is_trusted else "pending"
        requires_approval = not is_trusted
        
        withdrawal_doc = {
            "id": request_id,
            "user_id": user_id,
            "user_login": user.get('login', ''),
            "amount": data.amount,
            "fee": WITHDRAWAL_FEE,
            "total_frozen": total_amount,
            "to_address": data.to_address,
            "comment": data.comment or '',
            "status": withdrawal_status,
            "requires_approval": requires_approval,
            "auto_approved": is_trusted,
            "created_at": now,
            "updated_at": now
        }
        await mongodb.withdrawal_requests.insert_one(withdrawal_doc)
        
        # Create transaction history record
        tx_doc = {
            "id": f"tx_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "type": "withdrawal",
            "amount": data.amount,
            "fee": WITHDRAWAL_FEE,
            "currency": "USDT",
            "to_address": data.to_address,
            "status": withdrawal_status,
            "withdrawal_id": request_id,
            "created_at": now,
            "description": f"Запрос на вывод {data.amount} USDT (комиссия {WITHDRAWAL_FEE} USDT)" + (" [авто-одобрен]" if is_trusted else "")
        }
        await mongodb.transactions.insert_one(tx_doc)
        
        # Get updated balances
        if is_trader:
            updated = await mongodb.traders.find_one({"id": user_id}, {"balance_usdt": 1, "frozen_usdt": 1})
        else:
            updated = await mongodb.merchants.find_one({"id": user_id}, {"balance_usdt": 1, "frozen_usdt": 1})
        
        new_balance_val = updated.get("balance_usdt", 0) or 0
        new_frozen_val = updated.get("frozen_usdt", 0) or 0
        
        # For trusted users - automatically send USDT
        tx_hash = None
        send_error = None
        if is_trusted:
            try:
                # Check hot wallet balance first
                hw_data = await get_hot_wallet_balance()
                hot_wallet_balance = float(hw_data.get('usdt_balance', 0) or hw_data.get('balance', 0))
                
                if hot_wallet_balance >= data.amount:
                    # Send USDT to user
                    send_result = await send_usdt_withdrawal(
                        to_address=data.to_address,
                        amount=data.amount,
                        comment=f"Withdrawal {request_id[:8]}"
                    )
                    tx_hash = send_result.get('tx_hash')
                    
                    if tx_hash:
                        # Update withdrawal request with tx_hash and completed status
                        await mongodb.withdrawal_requests.update_one(
                            {"id": request_id},
                            {"$set": {
                                "status": "completed",
                                "tx_hash": tx_hash,
                                "completed_at": datetime.now(timezone.utc).isoformat()
                            }}
                        )
                        
                        # Update transaction record
                        await mongodb.transactions.update_one(
                            {"withdrawal_id": request_id},
                            {"$set": {
                                "status": "completed",
                                "tx_hash": tx_hash,
                                "completed_at": datetime.now(timezone.utc).isoformat()
                            }}
                        )
                        
                        # Deduct frozen balance (already frozen, now confirm deduction)
                        if is_trader:
                            await mongodb.traders.update_one(
                                {"id": user_id},
                                {"$inc": {"balance_usdt": -total_amount, "frozen_usdt": -total_amount}}
                            )
                        else:
                            await mongodb.merchants.update_one(
                                {"id": user_id},
                                {"$inc": {"balance_usdt": -total_amount, "frozen_usdt": -total_amount}}
                            )
                        
                        # Track platform fee
                        await mongodb.platform_fees.insert_one({
                            "type": "withdrawal_fee",
                            "amount": WITHDRAWAL_FEE,
                            "currency": "USDT",
                            "from_user_id": user_id,
                            "withdrawal_id": request_id,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        })
                        
                        # Re-fetch updated balances
                        if is_trader:
                            updated = await mongodb.traders.find_one({"id": user_id}, {"balance_usdt": 1, "frozen_usdt": 1})
                        else:
                            updated = await mongodb.merchants.find_one({"id": user_id}, {"balance_usdt": 1, "frozen_usdt": 1})
                        new_balance_val = updated.get("balance_usdt", 0) or 0
                        new_frozen_val = updated.get("frozen_usdt", 0) or 0
                else:
                    send_error = f"Недостаточно USDT в кошельке биржи ({hot_wallet_balance:.2f})"
            except Exception as e:
                send_error = str(e)
        
        # Different messages for trusted and regular users
        if is_trusted:
            if tx_hash:
                message = f"✅ Вывод выполнен! TX: {tx_hash[:16]}..."
                withdrawal_status = "completed"
            elif send_error:
                message = f"⚠️ Заявка одобрена, но отправка не удалась: {send_error}. Администратор отправит вручную."
            else:
                message = "Заявка на вывод автоматически одобрена. Средства будут отправлены в ближайшее время."
        else:
            message = "Заявка на вывод создана. Ожидает одобрения администратора."
        
        return {
            "success": True,
            "withdrawal": {
                "id": request_id,
                "amount": data.amount,
                "to_address": data.to_address,
                "status": withdrawal_status,
                "requires_approval": requires_approval,
                "auto_approved": is_trusted,
                "frozen_amount": data.amount,
                "tx_hash": tx_hash
            },
            "message": message,
            "new_balance": {
                "available": new_balance_val - new_frozen_val,
                "frozen": new_frozen_val
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
