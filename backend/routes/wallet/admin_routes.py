from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
import uuid

from core.database import db as mongodb
from routes.ton_finance import (
    get_finance_analytics,
    get_hot_wallet_balance,
    get_ton_service_health,
    get_audit_logs,
    create_audit_log,
    get_user_ton_balance,
    get_user_transactions,
    send_usdt_withdrawal
)
from .dependencies import require_roles

router = APIRouter()

@router.get("/admin/finance/analytics")
async def get_admin_finance_analytics(user: dict = Depends(require_roles(["admin", "mod"]))):
    """Get financial analytics dashboard data"""
    try:
        analytics = await get_finance_analytics()
        return {
            "success": True,
            "analytics": analytics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/finance/hot-wallet")
async def get_admin_hot_wallet_balance(user: dict = Depends(require_roles(["admin"]))):
    """Get hot wallet balance (admin only)"""
    try:
        # Get balance and health info from TON service
        result = await get_hot_wallet_balance()
        health = await get_ton_service_health()
        
        ton_balance = result.get('ton_balance', 0) or 0
        usdt_balance = result.get('usdt_balance', 0) or result.get('balance', 0) or 0
        network = health.get('network', 'unknown')
        address = health.get('hotWallet', result.get('address', ''))
        
        return {
            "success": True,
            "hot_wallet": {
                "address": address,
                "balance_ton": ton_balance,
                "balance_usdt": usdt_balance,
                "balance_usd": usdt_balance,  # backward compatibility
                "network": network
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/finance/audit-logs")
async def get_admin_audit_logs(
    limit: int = 100,
    user: dict = Depends(require_roles(["admin"]))
):
    """Get audit logs"""
    try:
        logs = await get_audit_logs(limit)
        return {
            "success": True,
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/finance/user/{user_id}")
async def get_admin_user_finance(
    user_id: str,
    user: dict = Depends(require_roles(["admin", "mod", "support"]))
):
    """Get any user's finance details (for support/admin)"""
    try:
        balance = await get_user_ton_balance(user_id)
        transactions = await get_user_transactions(user_id, 20)
        
        return {
            "success": True,
            "user_id": user_id,
            "balance": balance,
            "recent_transactions": transactions.get('transactions', [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/finance/pending-withdrawals")
async def get_pending_withdrawals(user: dict = Depends(require_roles(["admin", "mod"]))):
    """Get list of pending and approved withdrawals requiring execution"""
    try:
        pending = await mongodb.withdrawal_requests.find(
            {"status": {"$in": ["pending", "approved"]}},
            {"_id": 0}
        ).sort("created_at", 1).to_list(100)
        
        return {
            "success": True,
            "pending_withdrawals": pending
        }
    except Exception as e:
        return {
            "success": True,
            "pending_withdrawals": []
        }


@router.get("/admin/finance/withdrawal-history")
async def get_withdrawal_history(
    limit: int = 100,
    status: str = None,
    user: dict = Depends(require_roles(["admin", "mod"]))
):
    """Get full withdrawal history for admin"""
    try:
        query = {}
        if status and status != "all":
            query["status"] = status
        
        withdrawals = await mongodb.withdrawal_requests.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).to_list(limit)
        
        # Enhance with user info
        for w in withdrawals:
            user_id = w.get('user_id')
            if user_id:
                trader = await mongodb.traders.find_one({"id": user_id}, {"_id": 0, "login": 1, "nickname": 1})
                if trader:
                    w['user_login'] = trader.get('login') or trader.get('nickname')
                    w['user_type'] = 'trader'
                else:
                    merchant = await mongodb.merchants.find_one({"id": user_id}, {"_id": 0, "login": 1, "merchant_name": 1})
                    if merchant:
                        w['user_login'] = merchant.get('login') or merchant.get('merchant_name')
                        w['user_type'] = 'merchant'
        
        return {
            "success": True,
            "withdrawals": withdrawals,
            "total": len(withdrawals)
        }
    except Exception as e:
        return {
            "success": True,
            "withdrawals": [],
            "total": 0
        }


@router.get("/admin/finance/deposit-history")
async def get_deposit_history(
    limit: int = 100,
    user: dict = Depends(require_roles(["admin", "mod"]))
):
    """Get full deposit history for admin"""
    try:
        deposits = await mongodb.transactions.find(
            {"type": "deposit"},
            {"_id": 0}
        ).sort("created_at", -1).to_list(limit)
        
        # Enhance with user info
        for d in deposits:
            user_id = d.get('user_id')
            if user_id:
                trader = await mongodb.traders.find_one({"id": user_id}, {"_id": 0, "login": 1, "nickname": 1})
                if trader:
                    d['user_login'] = trader.get('login') or trader.get('nickname')
                    d['user_type'] = 'trader'
                else:
                    merchant = await mongodb.merchants.find_one({"id": user_id}, {"_id": 0, "login": 1, "merchant_name": 1})
                    if merchant:
                        d['user_login'] = merchant.get('login') or merchant.get('merchant_name')
                        d['user_type'] = 'merchant'
        
        return {
            "success": True,
            "deposits": deposits,
            "total": len(deposits)
        }
    except Exception as e:
        return {
            "success": True,
            "deposits": [],
            "total": 0
        }


@router.post("/admin/finance/approve-withdrawal/{tx_id}")
async def approve_withdrawal(
    tx_id: str,
    request: Request,
    user: dict = Depends(require_roles(["admin", "mod"]))
):
    """
    Approve a pending/approved withdrawal and execute the transfer.
    1. Проверяет что Hot Wallet имеет достаточно средств
    2. Списывает замороженные средства
    3. Отправляет транзакцию через TON service
    """
    try:
        # Find the withdrawal request (can be pending or approved)
        withdrawal = await mongodb.withdrawal_requests.find_one(
            {"id": tx_id, "status": {"$in": ["pending", "approved"]}},
            {"_id": 0}
        )
        
        if not withdrawal:
            raise HTTPException(status_code=404, detail="Заявка не найдена или уже обработана")
        
        amount = float(withdrawal.get('amount', 0))
        fee = float(withdrawal.get('fee', 1.0))  # Default fee 1 USDT
        total_frozen = float(withdrawal.get('total_frozen', amount + fee))
        target_user_id = withdrawal.get('user_id')
        to_address = withdrawal.get('to_address')
        
        # Check moderator limits
        if user.get('admin_role') not in ['owner', 'admin'] and amount > 500:
            raise HTTPException(
                status_code=403, 
                detail="Модераторы могут одобрять выводы до 500 USDT"
            )
        
        # CHECK HOT WALLET BALANCE (only need to send the amount, fee stays on platform)
        hot_wallet_balance = 0
        try:
            hw_data = await get_hot_wallet_balance()
            hot_wallet_balance = float(hw_data.get('usdt_balance', 0) or hw_data.get('balance', 0))
        except:
            pass
        
        if hot_wallet_balance < amount:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно средств в кошельке биржи! Требуется: {amount} USDT, доступно: {hot_wallet_balance:.2f} USDT"
            )
        
        # Find user and deduct total_frozen from both balance and frozen
        # Fee goes to platform (stays in hot wallet or tracked separately)
        trader = await mongodb.traders.find_one({"id": target_user_id})
        if trader:
            await mongodb.traders.update_one(
                {"id": target_user_id},
                {"$inc": {"balance_usdt": -total_frozen, "frozen_usdt": -total_frozen}}  # Remove amount + fee
            )
        else:
            await mongodb.merchants.update_one(
                {"id": target_user_id},
                {"$inc": {"balance_usdt": -total_frozen, "frozen_usdt": -total_frozen}}  # Remove amount + fee
            )
        
        # Track platform fee earnings
        await mongodb.platform_fees.insert_one({
            "type": "withdrawal_fee",
            "amount": fee,
            "currency": "USDT",
            "from_user_id": target_user_id,
            "withdrawal_id": tx_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # SEND USDT TO USER via TON Service
        tx_hash = None
        send_error = None
        try:
            send_result = await send_usdt_withdrawal(
                to_address=to_address,
                amount=amount,
                comment=f"Withdrawal {tx_id[:8]}"
            )
            tx_hash = send_result.get('tx_hash')
        except Exception as e:
            send_error = str(e)
            # Rollback balance changes if send failed
            if trader:
                await mongodb.traders.update_one(
                    {"id": target_user_id},
                    {"$inc": {"balance_usdt": total_frozen, "frozen_usdt": total_frozen}}
                )
            else:
                await mongodb.merchants.update_one(
                    {"id": target_user_id},
                    {"$inc": {"balance_usdt": total_frozen, "frozen_usdt": total_frozen}}
                )
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка отправки USDT: {send_error}. Баланс восстановлен."
            )
        
        # Update withdrawal status with tx_hash
        now = datetime.now(timezone.utc).isoformat()
        await mongodb.withdrawal_requests.update_one(
            {"id": tx_id},
            {"$set": {
                "status": "completed",
                "approved_by": user['id'],
                "approved_at": now,
                "completed_at": now,
                "tx_hash": tx_hash
            }}
        )
        
        # Update transaction status with tx_hash
        await mongodb.transactions.update_one(
            {"withdrawal_id": tx_id},
            {"$set": {
                "status": "completed",
                "completed_at": now,
                "tx_hash": tx_hash,
                "description": f"Вывод {amount} USDT выполнен (комиссия {fee} USDT)"
            }}
        )
        
        # Log the action
        await create_audit_log(
            admin_user_id=user['id'],
            action='approve_withdraw',
            target_user_id=target_user_id,
            target_tx_id=tx_id,
            new_value={'amount': amount, 'status': 'completed', 'to_address': to_address},
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": f"Вывод {amount} USDT одобрен и выполнен",
            "amount": amount
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/finance/reject-withdrawal/{tx_id}")
async def reject_withdrawal(
    tx_id: str,
    request: Request,
    reason: str = "Отклонено администратором",
    user: dict = Depends(require_roles(["admin", "mod"]))
):
    """
    Reject a pending withdrawal and unfreeze user balance.
    1. Возвращает замороженные средства на баланс
    2. Обновляет статус на rejected
    3. Создает запись в истории (возврат)
    """
    
    try:
        # Find the withdrawal request
        withdrawal = await mongodb.withdrawal_requests.find_one(
            {"id": tx_id, "status": "pending"},
            {"_id": 0}
        )
        
        if not withdrawal:
            raise HTTPException(status_code=404, detail="Заявка не найдена или уже обработана")
        
        amount = float(withdrawal.get('amount', 0))
        fee = float(withdrawal.get('fee', 1.0))
        total_frozen = float(withdrawal.get('total_frozen', amount + fee))
        target_user_id = withdrawal.get('user_id')
        now = datetime.now(timezone.utc).isoformat()
        
        # Update withdrawal status
        await mongodb.withdrawal_requests.update_one(
            {"id": tx_id},
            {"$set": {
                "status": "rejected",
                "rejected_by": user['id'],
                "rejected_at": now,
                "rejection_reason": reason
            }}
        )
        
        # UNFREEZE total amount (amount + fee)
        # Return everything to user since withdrawal was rejected
        trader = await mongodb.traders.find_one({"id": target_user_id})
        if trader:
            await mongodb.traders.update_one(
                {"id": target_user_id},
                {"$inc": {"frozen_usdt": -total_frozen}}  # Unfreeze amount + fee
            )
        else:
            await mongodb.merchants.update_one(
                {"id": target_user_id},
                {"$inc": {"frozen_usdt": -total_frozen}}  # Unfreeze amount + fee
            )
        
        # Update transaction status
        await mongodb.transactions.update_one(
            {"withdrawal_id": tx_id},
            {"$set": {
                "status": "rejected",
                "rejected_at": now,
                "description": f"Вывод отклонён: {reason}. Средства возвращены."
            }}
        )
        
        # Create refund transaction record
        refund_tx = {
            "id": f"tx_{uuid.uuid4().hex[:12]}",
            "user_id": target_user_id,
            "type": "refund",
            "amount": total_frozen,
            "currency": "USDT",
            "status": "completed",
            "related_withdrawal_id": tx_id,
            "created_at": now,
            "description": f"Возврат {total_frozen} USDT (вывод отклонён)"
        }
        await mongodb.transactions.insert_one(refund_tx)
        
        # Log the action
        await create_audit_log(
            admin_user_id=user['id'],
            action='reject_withdraw',
            target_user_id=target_user_id,
            target_tx_id=tx_id,
            new_value={'amount': amount, 'fee': fee, 'total_refunded': total_frozen, 'status': 'rejected', 'reason': reason},
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": f"Вывод отклонён. {total_frozen} USDT возвращены на баланс пользователя.",
            "reason": reason,
            "refunded_amount": total_frozen
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
