"""
BITARBITR P2P Platform - Wallet Router
Handles wallet operations: balance, deposits, withdrawals
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import secrets

router = APIRouter(tags=["Wallet"])
security = HTTPBearer()

# Global dependencies
_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"


def init_router(database, jwt_secret: str, jwt_algorithm: str = "HS256"):
    """Initialize router with database connection"""
    global _db, _jwt_secret, _jwt_algorithm
    _db = database
    _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm


def generate_id(prefix: str = "") -> str:
    """Generate unique ID"""
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{prefix}{date_part}_{secrets.token_hex(3).upper()}"


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT"""
    from jose import jwt, JWTError
    
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    token = credentials.credentials
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await _db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# ================== MODELS ==================

class WithdrawRequest(BaseModel):
    address: str
    amount_usdt: float


class MockDepositRequest(BaseModel):
    amount_usdt: float


# ================== ENDPOINTS ==================

@router.get("/wallet")
async def get_wallet(user: dict = Depends(get_current_user)):
    """Get user wallet balance"""
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    return {
        "id": wallet.get("id", f"wal_{user['id']}"),
        "user_id": user["id"],
        "address": wallet.get("address"),
        "available_balance_usdt": wallet.get("available_balance_usdt", 0),
        "locked_balance_usdt": wallet.get("locked_balance_usdt", 0),
        "pending_balance_usdt": wallet.get("pending_balance_usdt", 0),
        "earned_balance_usdt": wallet.get("earned_balance_usdt", 0),
        "total_deposited_usdt": wallet.get("total_deposited_usdt", 0),
        "total_withdrawn_usdt": wallet.get("total_withdrawn_usdt", 0),
    }


@router.post("/wallet/deposit")
async def request_deposit(user: dict = Depends(get_current_user)):
    """Get deposit address"""
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    return {
        "success": True,
        "address": wallet.get("address"),
        "min_deposit_usdt": 0.0001,
        "note": "Deposits are confirmed after 1 blockchain confirmation"
    }


@router.post("/wallet/mock-deposit")
async def mock_deposit(data: MockDepositRequest, user: dict = Depends(get_current_user)):
    """Mock deposit for testing (max 100 USDT)"""
    if data.amount_usdt <= 0 or data.amount_usdt > 100:
        raise HTTPException(status_code=400, detail="Invalid amount (0-100 USDT)")
    
    await _db.wallets.update_one(
        {"user_id": user["id"]},
        {"$inc": {
            "available_balance_usdt": data.amount_usdt,
            "total_deposited_usdt": data.amount_usdt
        }}
    )
    
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    tx = {
        "id": generate_id("tx"),
        "wallet_id": wallet["id"],
        "type": "deposit",
        "amount_usdt": data.amount_usdt,
        "status": "completed",
        "tx_hash": f"mock_{secrets.token_hex(32)}",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await _db.transactions.insert_one(tx)
    
    return {"success": True, "amount_usdt": data.amount_usdt, "tx_id": tx["id"]}


@router.post("/wallet/withdraw")
async def request_withdrawal(data: WithdrawRequest, user: dict = Depends(get_current_user)):
    """Request withdrawal to external address"""
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    if data.amount_usdt <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    
    if wallet["available_balance_usdt"] < data.amount_usdt:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    await _db.wallets.update_one(
        {"user_id": user["id"]},
        {"$inc": {
            "available_balance_usdt": -data.amount_usdt,
            "total_withdrawn_usdt": data.amount_usdt
        }}
    )
    
    tx = {
        "id": generate_id("tx"),
        "wallet_id": wallet["id"],
        "type": "withdrawal",
        "amount_usdt": data.amount_usdt,
        "address": data.address,
        "status": "completed",
        "tx_hash": f"mock_{secrets.token_hex(32)}",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await _db.transactions.insert_one(tx)
    
    return {"success": True, "tx_id": tx["id"], "amount_usdt": data.amount_usdt}


@router.get("/wallet/transactions")
async def get_transactions(user: dict = Depends(get_current_user)):
    """Get wallet transaction history"""
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    txs = await _db.transactions.find(
        {"wallet_id": wallet["id"]}, 
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"transactions": txs}


@router.get("/wallet/usdt")
async def get_usdt_wallet(user: dict = Depends(get_current_user)):
    """Get USDT wallet details"""
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    return {
        "address": wallet.get("address"),
        "available_balance": wallet.get("available_balance_usdt", 0),
        "locked_balance": wallet.get("locked_balance_usdt", 0),
        "pending_balance": wallet.get("pending_balance_usdt", 0),
        "earned_balance": wallet.get("earned_balance_usdt", 0),
        "total_deposited": wallet.get("total_deposited_usdt", 0),
        "total_withdrawn": wallet.get("total_withdrawn_usdt", 0)
    }


@router.post("/wallet/usdt/deposit")
async def request_usdt_deposit(user: dict = Depends(get_current_user)):
    """Request USDT deposit - get deposit address"""
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    address = wallet.get("address")
    if not address:
        address = f"UQ{secrets.token_hex(32)}"
        await _db.wallets.update_one(
            {"user_id": user["id"]},
            {"$set": {"address": address}}
        )
    
    return {
        "success": True,
        "address": address,
        "network": "TON",
        "min_deposit": 0,
        "confirmations_required": 1,
        "note": "Send only USDT on TON network to this address"
    }


@router.post("/wallet/usdt/withdraw")
async def request_usdt_withdrawal(data: WithdrawRequest, user: dict = Depends(get_current_user)):
    """Request USDT withdrawal"""
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    if data.amount_usdt <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    
    available = wallet.get("available_balance_usdt", 0)
    if available < data.amount_usdt:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient balance. Available: {available} USDT"
        )
    
    await _db.wallets.update_one(
        {"user_id": user["id"]},
        {"$inc": {
            "available_balance_usdt": -data.amount_usdt,
            "pending_balance_usdt": data.amount_usdt
        }}
    )
    
    withdrawal = {
        "id": generate_id("wd"),
        "user_id": user["id"],
        "address": data.address,
        "amount_usdt": data.amount_usdt,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await _db.withdrawals.insert_one(withdrawal)
    
    return {
        "success": True,
        "withdrawal_id": withdrawal["id"],
        "amount_usdt": data.amount_usdt,
        "address": data.address,
        "status": "pending",
        "note": "Withdrawal will be processed within 24 hours"
    }
