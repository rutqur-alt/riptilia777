"""
TON Wallet API Routes for Reptiloid Exchange
Provides user-facing API endpoints for TON deposits and withdrawals
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
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
    user: dict = Depends(get_current_user_from_token)
):
    """Get user's transaction history"""
    try:
        result = await get_user_transactions(user['id'], limit, offset)
        return {
            "success": True,
            "transactions": result.get('transactions', []),
            "count": result.get('count', 0)
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
    Request TON withdrawal.
    - Amounts < 50 TON: Automatic processing
    - Amounts >= 50 TON: Requires moderator/admin approval
    """
    try:
        # Get user's current balance
        balance = await get_user_ton_balance(user['id'])
        available = balance['available_ton']
        
        # Check balance
        if data.amount > available:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient balance. Available: {available} TON"
            )
        
        # Check daily limit based on role
        daily_limit = 50.0  # Default for traders
        if user.get('role') == 'merchant':
            daily_limit = 200.0
        elif user.get('role') in ['admin', 'mod']:
            daily_limit = 1000.0
        
        # Request withdrawal
        result = await request_withdrawal(
            user_id=user['id'],
            amount=data.amount,
            to_address=data.to_address,
            comment=data.comment or ''
        )
        
        requires_approval = data.amount >= 50.0
        
        return {
            "success": True,
            "withdrawal": {
                "tx_id": result.get('txId'),
                "amount": data.amount,
                "to_address": data.to_address,
                "fee": result.get('fee', 0.05),
                "status": "pending_approval" if requires_approval else result.get('status', 'processing'),
                "requires_approval": requires_approval
            },
            "message": "Withdrawal requires moderator approval" if requires_approval else "Withdrawal processing"
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
        result = await get_hot_wallet_balance()
        balance = result.get('balance', 0)
        return {
            "success": True,
            "hot_wallet": {
                "address": result.get('address', ''),
                "balance_ton": balance,
                "balance_usd": balance,
                "network": "testnet"
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
    """Approve a pending withdrawal"""
    try:
        # Find the withdrawal request
        withdrawal = await mongodb.withdrawal_requests.find_one(
            {"id": tx_id, "status": "pending"},
            {"_id": 0}
        )
        
        if not withdrawal:
            raise HTTPException(status_code=404, detail="Withdrawal not found or already processed")
        
        amount = float(withdrawal.get('amount', 0))
        
        # Check moderator limits
        if user.get('role') == 'mod' and amount > 50:
            raise HTTPException(
                status_code=403, 
                detail="Moderators can only approve withdrawals up to 50 USDT"
            )
        
        # Update status
        await mongodb.withdrawal_requests.update_one(
            {"id": tx_id},
            {"$set": {
                "status": "approved",
                "approved_by": user['id'],
                "approved_at": datetime.now().isoformat()
            }}
        )
        
        # Log the action
        await create_audit_log(
            admin_user_id=user['id'],
            action='approve_withdraw',
            target_user_id=withdrawal.get('user_id'),
            target_tx_id=tx_id,
            new_value={'amount': amount, 'status': 'approved'},
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": f"Withdrawal {tx_id} approved",
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
    """Reject a pending withdrawal and refund user"""
    try:
        # Find the withdrawal request
        withdrawal = await mongodb.withdrawal_requests.find_one(
            {"id": tx_id, "status": "pending"},
            {"_id": 0}
        )
        
        if not withdrawal:
            raise HTTPException(status_code=404, detail="Withdrawal not found")
        
        amount = float(withdrawal.get('amount', 0))
        target_user_id = withdrawal.get('user_id')
        
        # Update withdrawal status
        await mongodb.withdrawal_requests.update_one(
            {"id": tx_id},
            {"$set": {
                "status": "rejected",
                "rejected_by": user['id'],
                "rejected_at": datetime.now().isoformat(),
                "rejection_reason": reason
            }}
        )
        
        # Refund user balance (check if trader or merchant)
        trader = await mongodb.traders.find_one({"id": target_user_id})
        if trader:
            await mongodb.traders.update_one(
                {"id": target_user_id},
                {"$inc": {"balance_usdt": amount}}
            )
        else:
            await mongodb.merchants.update_one(
                {"id": target_user_id},
                {"$inc": {"balance_usdt": amount}}
            )
        
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
            "message": f"Withdrawal {tx_id} rejected and {amount} USDT refunded",
            "reason": reason
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
