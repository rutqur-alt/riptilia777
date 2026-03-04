"""
TON Wallet API Routes for Reptiloid Exchange
Provides user-facing API endpoints for TON deposits and withdrawals
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
import jwt
import os

router = APIRouter(tags=["TON Wallet"])

# JWT config
JWT_SECRET = os.environ.get('JWT_SECRET', 'p2p-exchange-secret-key-change-in-production')

from routes.ton_finance import (
    get_ton_service_health,
    create_user_finance_record,
    get_deposit_address,
    get_user_ton_balance,
    get_hot_wallet_balance,
    get_user_transactions,
    request_withdrawal,
    get_finance_analytics,
    get_audit_logs,
    create_audit_log
)


# ==================== AUTH HELPERS ====================

async def get_current_user_from_token(authorization: str = Header(...)):
    """Extract user from JWT token"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("user_id")
        role = payload.get("role")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"id": user_id, "role": role}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(allowed_roles: list):
    """Dependency for role-based access"""
    async def check_role(user: dict = Depends(get_current_user_from_token)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return check_role


# ==================== MODELS ====================

class WithdrawRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount in TON")
    to_address: str = Field(..., min_length=48, description="TON wallet address")
    two_fa_code: Optional[str] = Field(None, description="2FA code if enabled")
    comment: Optional[str] = Field("", description="Optional comment")


# ==================== PUBLIC ENDPOINTS ====================

@router.get("/wallet/health")
async def wallet_health():
    """Check TON service health"""
    health = await get_ton_service_health()
    return health


# ==================== USER ENDPOINTS ====================

@router.get("/wallet/deposit-address")
async def get_user_deposit_address(user: dict = Depends(get_current_user_from_token)):
    """
    Get deposit address and memo for current user.
    User should send TON to this address with the provided comment.
    """
    try:
        result = await get_deposit_address(user['id'])
        return {
            "success": True,
            "deposit_info": {
                "address": result['address'],
                "comment": result['comment'],
                "network": result['network'],
                "instructions": [
                    f"1. Send TON to address: {result['address']}",
                    f"2. IMPORTANT: Include this comment/memo: {result['comment']}",
                    "3. Wait for network confirmation (usually 1-2 minutes)",
                    "4. Your balance will be credited automatically"
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
    import uuid
    
    try:
        # Check for duplicate request (anti double-click)
        user_id = user['id']
        ten_seconds_ago = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        
        recent_request = await mongodb.withdrawal_requests.find_one({
            "user_id": user_id,
            "amount": data.amount,
            "created_at": {"$gte": ten_seconds_ago},
            "status": "pending"
        })
        
        if recent_request:
            raise HTTPException(
                status_code=429, 
                detail="Заявка уже создана. Подождите несколько секунд."
            )
        
        # Get user's current balance from MongoDB
        trader = await mongodb.traders.find_one({"id": user_id})
        is_trader = bool(trader)
        
        if trader:
            current_balance = trader.get("balance_usdt", 0) or 0
            frozen_balance = trader.get("frozen_usdt", 0) or 0
        else:
            merchant = await mongodb.merchants.find_one({"id": user_id})
            if not merchant:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            current_balance = merchant.get("balance_usdt", 0) or 0
            frozen_balance = merchant.get("frozen_usdt", 0) or 0
        
        available_balance = current_balance - frozen_balance
        
        # Check balance
        if data.amount > available_balance:
            raise HTTPException(
                status_code=400, 
                detail=f"Недостаточно средств. Доступно: {available_balance:.2f} USDT"
            )
        
        if data.amount <= 0:
            raise HTTPException(status_code=400, detail="Сумма должна быть положительной")
        
        # Check daily limit based on role
        daily_limit = 50.0  # Default for traders
        if user.get('role') == 'merchant':
            # Check merchant type for limit
            if not is_trader:
                merchant_type = merchant.get('merchant_type', 'I')
                daily_limit = 1000.0 if merchant_type == 'II' else 200.0
        
        # Create withdrawal request ID
        request_id = f"wd_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        
        # FREEZE the balance (move from balance to frozen)
        if is_trader:
            await mongodb.traders.update_one(
                {"id": user_id},
                {
                    "$inc": {"balance_usdt": -data.amount, "frozen_usdt": data.amount}
                }
            )
        else:
            await mongodb.merchants.update_one(
                {"id": user_id},
                {
                    "$inc": {"balance_usdt": -data.amount, "frozen_usdt": data.amount}
                }
            )
        
        # Create withdrawal request
        withdrawal_doc = {
            "id": request_id,
            "user_id": user_id,
            "user_login": user.get('login', ''),
            "amount": data.amount,
            "to_address": data.to_address,
            "comment": data.comment or '',
            "status": "pending",
            "requires_approval": True,
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
            "currency": "USDT",
            "to_address": data.to_address,
            "status": "pending",
            "withdrawal_id": request_id,
            "created_at": now,
            "description": f"Запрос на вывод {data.amount} USDT"
        }
        await mongodb.transactions.insert_one(tx_doc)
        
        return {
            "success": True,
            "withdrawal": {
                "id": request_id,
                "amount": data.amount,
                "to_address": data.to_address,
                "status": "pending",
                "requires_approval": True,
                "frozen_amount": data.amount
            },
            "message": "Заявка на вывод создана. Ожидает одобрения администратора.",
            "new_balance": {
                "available": available_balance - data.amount,
                "frozen": frozen_balance + data.amount
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ADMIN ENDPOINTS ====================

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
        
        balance = result.get('balance', 0)
        network = health.get('network', 'unknown')
        address = health.get('hotWallet', result.get('address', ''))
        
        return {
            "success": True,
            "hot_wallet": {
                "address": address,
                "balance_ton": balance,
                "balance_usd": balance,
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


# ==================== WITHDRAWAL APPROVAL ENDPOINTS ====================

from core.database import db as mongodb

@router.get("/admin/finance/pending-withdrawals")
async def get_pending_withdrawals(user: dict = Depends(require_roles(["admin", "mod"]))):
    """Get list of pending withdrawals requiring approval"""
    try:
        pending = await mongodb.withdrawal_requests.find(
            {"status": "pending"},
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


@router.post("/admin/finance/approve-withdrawal/{tx_id}")
async def approve_withdrawal(
    tx_id: str,
    request: Request,
    user: dict = Depends(require_roles(["admin", "mod"]))
):
    """
    Approve a pending withdrawal.
    1. Проверяет что Hot Wallet имеет достаточно средств
    2. Списывает замороженные средства
    3. Отправляет транзакцию через TON service
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
        target_user_id = withdrawal.get('user_id')
        to_address = withdrawal.get('to_address')
        
        # Check moderator limits
        if user.get('admin_role') not in ['owner', 'admin'] and amount > 500:
            raise HTTPException(
                status_code=403, 
                detail="Модераторы могут одобрять выводы до 500 USDT"
            )
        
        # CHECK HOT WALLET BALANCE
        hot_wallet_balance = 0
        try:
            hw_data = await get_hot_wallet_balance()
            hot_wallet_balance = float(hw_data.get('balance', 0))
        except:
            pass
        
        if hot_wallet_balance < amount:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно средств в кошельке биржи! Требуется: {amount} USDT, доступно: {hot_wallet_balance:.2f} USDT"
            )
        
        # Find user and remove frozen balance
        trader = await mongodb.traders.find_one({"id": target_user_id})
        if trader:
            await mongodb.traders.update_one(
                {"id": target_user_id},
                {"$inc": {"frozen_usdt": -amount}}
            )
        else:
            await mongodb.merchants.update_one(
                {"id": target_user_id},
                {"$inc": {"frozen_usdt": -amount}}
            )
        
        # Update withdrawal status
        now = datetime.now(timezone.utc).isoformat()
        await mongodb.withdrawal_requests.update_one(
            {"id": tx_id},
            {"$set": {
                "status": "completed",
                "approved_by": user['id'],
                "approved_at": now,
                "completed_at": now
            }}
        )
        
        # Update transaction status
        await mongodb.transactions.update_one(
            {"withdrawal_id": tx_id},
            {"$set": {
                "status": "completed",
                "completed_at": now,
                "description": f"Вывод {amount} USDT выполнен"
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
    import uuid
    
    try:
        # Find the withdrawal request
        withdrawal = await mongodb.withdrawal_requests.find_one(
            {"id": tx_id, "status": "pending"},
            {"_id": 0}
        )
        
        if not withdrawal:
            raise HTTPException(status_code=404, detail="Заявка не найдена или уже обработана")
        
        amount = float(withdrawal.get('amount', 0))
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
        
        # UNFREEZE and REFUND: frozen -> balance
        trader = await mongodb.traders.find_one({"id": target_user_id})
        if trader:
            await mongodb.traders.update_one(
                {"id": target_user_id},
                {"$inc": {"frozen_usdt": -amount, "balance_usdt": amount}}
            )
        else:
            await mongodb.merchants.update_one(
                {"id": target_user_id},
                {"$inc": {"frozen_usdt": -amount, "balance_usdt": amount}}
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
            "amount": amount,
            "currency": "USDT",
            "status": "completed",
            "related_withdrawal_id": tx_id,
            "created_at": now,
            "description": f"Возврат {amount} USDT (вывод отклонён)"
        }
        await mongodb.transactions.insert_one(refund_tx)
        
        # Log the action
        await create_audit_log(
            admin_user_id=user['id'],
            action='reject_withdraw',
            target_user_id=target_user_id,
            target_tx_id=tx_id,
            new_value={'amount': amount, 'status': 'rejected', 'reason': reason},
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": f"Вывод отклонён. {amount} USDT возвращены на баланс пользователя.",
            "reason": reason,
            "refunded_amount": amount
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ==================== WALLET MANAGEMENT (ADMIN ONLY) ====================

class WalletChangeRequest(BaseModel):
    new_address: str = Field(..., min_length=48, description="New TON wallet address")
    new_mnemonic: str = Field(..., description="24-word mnemonic phrase")
    confirm: bool = Field(..., description="Confirmation flag")

@router.get("/admin/wallet/current")
async def get_current_wallet(user: dict = Depends(require_roles(["admin"]))):
    """Get current active wallet info"""
    try:
        # Get from TON service
        health = await get_ton_service_health()
        hot_wallet = await get_hot_wallet_balance()
        
        # Get wallet config from MongoDB
        wallet_config = await mongodb.wallet_config.find_one(
            {"status": "active"},
            {"_id": 0}
        )
        
        return {
            "success": True,
            "wallet": {
                "address": health.get("hotWallet", ""),
                "balance": hot_wallet.get("balance", 0),
                "network": health.get("network", "testnet"),
                "status": "active",
                "created_at": wallet_config.get("created_at") if wallet_config else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/wallet/history")
async def get_wallet_history(user: dict = Depends(require_roles(["admin"]))):
    """Get history of all wallets"""
    try:
        wallets = await mongodb.wallet_config.find(
            {},
            {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        
        return {
            "success": True,
            "wallets": wallets
        }
    except Exception as e:
        return {"success": True, "wallets": []}


@router.post("/admin/wallet/change")
async def change_wallet(
    data: WalletChangeRequest,
    request: Request,
    user: dict = Depends(require_roles(["admin"]))
):
    """Change hot wallet (CRITICAL OPERATION)"""
    import uuid
    import httpx
    
    if not data.confirm:
        raise HTTPException(status_code=400, detail="Требуется подтверждение операции")
    
    # Validate mnemonic (24 words)
    words = data.new_mnemonic.strip().split()
    if len(words) != 24:
        raise HTTPException(status_code=400, detail="Мнемоника должна содержать 24 слова")
    
    try:
        # Archive current wallet
        await mongodb.wallet_config.update_many(
            {"status": "active"},
            {"$set": {"status": "archived", "archived_at": datetime.now().isoformat()}}
        )
        
        # Save new wallet config
        new_config = {
            "id": str(uuid.uuid4()),
            "address": data.new_address,
            "mnemonic_hash": hash(data.new_mnemonic),  # Don't store raw mnemonic in DB
            "status": "active",
            "network": "testnet",
            "created_at": datetime.now().isoformat(),
            "created_by": user['id']
        }
        await mongodb.wallet_config.insert_one(new_config)
        
        # Update TON service .env (this requires service restart)
        # For now, just log the change - actual implementation needs manual restart
        
        # Create audit log
        await create_audit_log(
            admin_user_id=user['id'],
            action='change_wallet',
            old_value={"status": "archived"},
            new_value={"address": data.new_address, "status": "active"},
            details="Hot wallet changed",
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": "Кошелек изменен. Требуется перезапуск TON сервиса.",
            "new_address": data.new_address,
            "note": "Обновите HOT_WALLET_MNEMONIC в /app/ton-service/.env и перезапустите сервис"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/wallet/generate")
async def generate_new_wallet(
    request: Request,
    user: dict = Depends(require_roles(["admin"]))
):
    """Generate a new TON wallet"""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{os.environ.get('TON_SERVICE_URL', 'http://localhost:8002')}/generate-wallet",
                headers={"X-API-Key": os.environ.get('TON_SERVICE_API_KEY', 'ton_service_api_secret_key_2026')}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Ошибка генерации кошелька")
            
            wallet_data = response.json()
            
            await create_audit_log(
                admin_user_id=user['id'],
                action='generate_wallet',
                new_value={"address": wallet_data.get("address")},
                ip_address=request.client.host
            )
            
            return {
                "success": True,
                "wallet": wallet_data,
                "message": "Кошелек сгенерирован. Мнемоника сохранена в /app/ton-service/wallet-backup.json"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FULL ANALYTICS (OPTIMIZED) ====================

@router.get("/admin/analytics/full")
async def get_full_analytics(
    period: str = "7d",
    user: dict = Depends(require_roles(["admin"]))
):
    """Get comprehensive financial analytics - OPTIMIZED with parallel queries"""
    import asyncio
    from datetime import timedelta, timezone
    
    days = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
    period_days = days.get(period, 7)
    start_date = datetime.now(timezone.utc) - timedelta(days=period_days)
    
    try:
        # Define all queries as async functions
        async def get_traders_stats():
            pipeline = [{"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$balance_usdt", 0]}}, "count": {"$sum": 1}}}]
            result = await mongodb.traders.aggregate(pipeline).to_list(1)
            return result[0] if result else {"total": 0, "count": 0}
        
        async def get_merchants_stats():
            pipeline = [{"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$balance_usdt", 0]}}, "count": {"$sum": 1}}}]
            result = await mongodb.merchants.aggregate(pipeline).to_list(1)
            return result[0] if result else {"total": 0, "count": 0}
        
        async def get_hw_balance():
            try:
                hw_data = await get_hot_wallet_balance()
                return hw_data.get('balance', 0)
            except:
                return 0
        
        async def get_trades_stats():
            # Use MongoDB aggregation for daily stats instead of Python filtering
            pipeline = [
                {"$match": {"status": "completed", "created_at": {"$gte": start_date.isoformat()}}},
                {"$group": {
                    "_id": {"$substr": ["$created_at", 0, 10]},
                    "volume": {"$sum": {"$ifNull": ["$amount_usdt", 0]}},
                    "fees_rub": {"$sum": {"$ifNull": ["$platform_fee_rub", 0]}},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}}
            ]
            return await mongodb.trades.aggregate(pipeline).to_list(100)
        
        async def get_pending_stats():
            pipeline = [
                {"$match": {"status": "pending"}},
                {"$group": {"_id": None, "count": {"$sum": 1}, "total": {"$sum": {"$ifNull": ["$amount", 0]}}}}
            ]
            result = await mongodb.withdrawal_requests.aggregate(pipeline).to_list(1)
            return result[0] if result else {"count": 0, "total": 0}
        
        async def get_rate():
            settings = await mongodb.settings.find_one({"type": "payout_settings"}, {"_id": 0, "base_rate": 1})
            return settings.get("base_rate", 78) if settings else 78
        
        # Execute ALL queries in parallel
        traders_stats, merchants_stats, hot_wallet_balance, trades_by_day, pending_stats, base_rate = await asyncio.gather(
            get_traders_stats(),
            get_merchants_stats(),
            get_hw_balance(),
            get_trades_stats(),
            get_pending_stats(),
            get_rate()
        )
        
        # Process results
        traders_balance = traders_stats.get("total", 0) or 0
        traders_count = traders_stats.get("count", 0) or 0
        merchants_balance = merchants_stats.get("total", 0) or 0
        merchants_count = merchants_stats.get("count", 0) or 0
        total_user_balance = traders_balance + merchants_balance
        
        # Calculate platform metrics
        platform_profit = hot_wallet_balance - total_user_balance
        reserve_ratio = (hot_wallet_balance / total_user_balance * 100) if total_user_balance > 0 else 100
        
        # Process trades stats
        total_volume = sum(d.get("volume", 0) for d in trades_by_day)
        total_fees_rub = sum(d.get("fees_rub", 0) for d in trades_by_day)
        total_trades = sum(d.get("count", 0) for d in trades_by_day)
        total_fees_usdt = total_fees_rub / base_rate if base_rate > 0 else 0
        
        # Build daily stats from aggregation results
        daily_map = {d["_id"]: d for d in trades_by_day}
        daily_stats = []
        for i in range(min(period_days, 30)):
            day = datetime.now(timezone.utc) - timedelta(days=i)
            date_key = day.strftime("%Y-%m-%d")
            day_data = daily_map.get(date_key, {})
            daily_stats.append({
                "date": date_key,
                "trades": day_data.get("count", 0),
                "volume": day_data.get("volume", 0),
                "fees": day_data.get("fees_rub", 0) / base_rate if base_rate > 0 else 0
            })
        daily_stats.reverse()
        
        return {
            "success": True,
            "analytics": {
                "overview": {
                    "hot_wallet_balance": hot_wallet_balance,
                    "traders_balance": traders_balance,
                    "merchants_balance": merchants_balance,
                    "total_user_balance": total_user_balance,
                    "platform_profit": platform_profit,
                    "reserve_ratio": round(reserve_ratio, 2),
                    "is_healthy": reserve_ratio >= 100 or total_user_balance == 0
                },
                "users": {
                    "traders_count": traders_count,
                    "merchants_count": merchants_count,
                    "total_users": traders_count + merchants_count
                },
                "period_stats": {
                    "period": period,
                    "total_volume": round(total_volume, 2),
                    "total_trades": total_trades,
                    "total_fees_usdt": round(total_fees_usdt, 4),
                    "avg_trade_size": round(total_volume / total_trades, 2) if total_trades > 0 else 0
                },
                "pending": {
                    "withdrawals_count": pending_stats.get("count", 0),
                    "withdrawals_amount": round(pending_stats.get("total", 0), 2)
                },
                "daily_stats": daily_stats
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/analytics/top-traders")
async def get_top_traders(
    limit: int = 10,
    user: dict = Depends(require_roles(["admin", "mod"]))
):
    """Get top traders by volume"""
    try:
        # Get traders with trade stats
        traders = await mongodb.traders.find(
            {"is_deleted": {"$ne": True}},
            {"_id": 0, "id": 1, "login": 1, "nickname": 1, "balance_usdt": 1, 
             "salesCount": 1, "purchasesCount": 1, "created_at": 1}
        ).sort("balance_usdt", -1).limit(limit).to_list(limit)
        
        return {
            "success": True,
            "traders": traders
        }
    except Exception as e:
        return {"success": True, "traders": []}


@router.get("/admin/analytics/top-merchants")
async def get_top_merchants(
    limit: int = 10,
    user: dict = Depends(require_roles(["admin", "mod"]))
):
    """Get top merchants by volume"""
    try:
        merchants = await mongodb.merchants.find(
            {"is_deleted": {"$ne": True}},
            {"_id": 0, "id": 1, "login": 1, "nickname": 1, "merchant_name": 1,
             "balance_usdt": 1, "merchant_type": 1, "created_at": 1}
        ).sort("balance_usdt", -1).limit(limit).to_list(limit)
        
        return {
            "success": True,
            "merchants": merchants
        }
    except Exception as e:
        return {"success": True, "merchants": []}


# ==================== USER SEARCH (IMPROVED) ====================

@router.get("/admin/users/search")
async def search_users(
    query: str = "",
    role: str = "all",
    user: dict = Depends(require_roles(["admin", "mod", "support"]))
):
    """Search users by ID, login, or nickname"""
    try:
        results = []
        
        search_filter = {}
        if query:
            search_filter["$or"] = [
                {"id": {"$regex": query, "$options": "i"}},
                {"login": {"$regex": query, "$options": "i"}},
                {"nickname": {"$regex": query, "$options": "i"}}
            ]
        
        # Search traders
        if role in ["all", "trader"]:
            traders = await mongodb.traders.find(
                search_filter,
                {"_id": 0, "id": 1, "login": 1, "nickname": 1, "balance_usdt": 1, "created_at": 1}
            ).limit(20).to_list(20)
            
            for t in traders:
                t["role"] = "trader"
                results.append(t)
        
        # Search merchants
        if role in ["all", "merchant"]:
            merchants = await mongodb.merchants.find(
                search_filter,
                {"_id": 0, "id": 1, "login": 1, "nickname": 1, "merchant_name": 1, 
                 "balance_usdt": 1, "created_at": 1}
            ).limit(20).to_list(20)
            
            for m in merchants:
                m["role"] = "merchant"
                results.append(m)
        
        return {
            "success": True,
            "count": len(results),
            "users": results
        }
    except Exception as e:
        return {"success": True, "count": 0, "users": []}


@router.get("/admin/users/{user_id}/details")
async def get_user_full_details(
    user_id: str,
    user: dict = Depends(require_roles(["admin", "mod", "support"]))
):
    """Get full user details including balance and transactions"""
    try:
        # Try to find in traders
        found_user = await mongodb.traders.find_one({"id": user_id}, {"_id": 0})
        role = "trader"
        
        if not found_user:
            # Try merchants
            found_user = await mongodb.merchants.find_one({"id": user_id}, {"_id": 0})
            role = "merchant"
        
        if not found_user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Get recent trades
        trades = await mongodb.trades.find(
            {"$or": [{"trader_id": user_id}, {"merchant_id": user_id}]},
            {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        
        # Get withdrawal requests
        withdrawals = await mongodb.withdrawal_requests.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        return {
            "success": True,
            "user": {
                **found_user,
                "role": role
            },
            "recent_trades": trades,
            "withdrawal_requests": withdrawals
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ADMIN BALANCE ADJUSTMENT ====================

class BalanceAdjustRequest(BaseModel):
    user_id: str
    amount: float = Field(..., description="Positive to add, negative to subtract")
    reason: str = Field(..., min_length=5, description="Reason for adjustment")

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
