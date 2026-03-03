"""
BITARBITR P2P Platform - USDT Router
Handles USDT deposits, withdrawals and wallet operations
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import secrets
import logging

router = APIRouter(tags=["USDT"])
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Global dependencies
_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"
_fetch_rate = None


def init_router(database, jwt_secret: str, jwt_algorithm: str = "HS256", fetch_rate_func=None):
    """Initialize router"""
    global _db, _jwt_secret, _jwt_algorithm, _fetch_rate
    _db = database
    _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm
    _fetch_rate = fetch_rate_func


def generate_id(prefix: str = "") -> str:
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{prefix}{date_part}_{secrets.token_hex(3).upper()}"


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
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


async def get_or_create_usdt_wallet(user_id: str):
    """Get or create USDT wallet for user"""
    wallet = await _db.usdt_wallets.find_one({"user_id": user_id}, {"_id": 0})
    
    if not wallet:
        wallet = {
            "id": generate_id("usdtw"),
            "user_id": user_id,
            "balance_usdt": 0.0,
            "pending_balance_usdt": 0.0,
            "total_deposited_usdt": 0.0,
            "total_withdrawn_usdt": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await _db.usdt_wallets.insert_one(wallet)
    
    return wallet


# ================== MODELS ==================

class WithdrawalRequest(BaseModel):
    amount_usdt: Optional[float] = None
    amount: Optional[float] = None  # alias
    address: Optional[str] = None
    ton_address: Optional[str] = None  # alias
    verification_token: Optional[str] = None  # from security verification
    
    def get_amount(self) -> float:
        return self.amount_usdt or self.amount or 0
    
    def get_address(self) -> str:
        return self.address or self.ton_address or ""


# ================== ENDPOINTS ==================

@router.get("/usdt/wallet")
async def get_usdt_wallet(user: dict = Depends(get_current_user)):
    """Get user's USDT wallet"""
    wallet = await get_or_create_usdt_wallet(user["id"])
    
    # Get transaction history
    deposits = await _db.usdt_deposits.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    withdrawals = await _db.usdt_withdrawals.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Current rate
    usdt_rate = 75.0
    if _fetch_rate:
        try:
            usdt_rate = await _fetch_rate()
        except Exception:
            pass
    
    # Get platform TON address from auto-withdraw config
    platform_ton_address = ""
    auto_config = await _db.auto_withdraw_config.find_one({"active": True}, {"_id": 0})
    if auto_config:
        platform_ton_address = auto_config.get("wallet_address", "")
    
    # Fallback to platform_settings
    if not platform_ton_address:
        settings = await _db.platform_settings.find_one({"type": "auto_withdraw"}, {"_id": 0})
        if settings:
            platform_ton_address = settings.get("wallet_address", "")
    
    return {
        "wallet": wallet,
        "deposits": deposits,
        "withdrawals": withdrawals,
        "usdt_rub_rate": usdt_rate,
        "platform_ton_address": platform_ton_address,
        "min_deposit": 0,
        "min_withdrawal": 0,
        "withdrawal_fee_percent": 0,
        "withdrawal_min_fee": 0,
        "network_fee": 0
    }


@router.get("/usdt/rate")
async def get_usdt_rate():
    """Get current USDT/RUB rate"""
    rate = 75.0
    if _fetch_rate:
        try:
            rate = await _fetch_rate()
        except:
            pass
    
    return {
        "usdt_rub": rate,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


@router.post("/usdt/deposit/create-request")
async def create_deposit_request(user: dict = Depends(get_current_user)):
    """Create USDT deposit request"""
    # Cancel previous pending requests
    await _db.deposit_requests.update_many(
        {"user_id": user["id"], "status": "pending"},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Get platform TON address from auto-withdraw config
    platform_ton_address = ""
    auto_config = await _db.auto_withdraw_config.find_one({"active": True}, {"_id": 0})
    if auto_config:
        platform_ton_address = auto_config.get("wallet_address", "")
    
    if not platform_ton_address:
        settings = await _db.platform_settings.find_one({"type": "auto_withdraw"}, {"_id": 0})
        if settings:
            platform_ton_address = settings.get("wallet_address", "")
    
    # Generate unique request ID and comment
    request_id = f"DEP{secrets.token_hex(4).upper()}"
    deposit_comment = f"D{secrets.token_hex(3).upper()}"
    
    # Create request
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    
    request = {
        "id": generate_id("depreq"),
        "request_id": request_id,
        "user_id": user["id"],
        "deposit_comment": deposit_comment,
        "ton_address": platform_ton_address,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat()
    }
    
    await _db.deposit_requests.insert_one(request)
    
    return {
        "success": True,
        "request_id": request_id,
        "deposit_comment": deposit_comment,
        "ton_address": platform_ton_address,
        "expires_at": expires_at.isoformat(),
        "status": "pending",
        "instructions": "Send USDT with this comment in memo field"
    }


@router.get("/usdt/deposit/requests")
async def get_deposit_requests(
    status: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get user's deposit requests"""
    query = {"user_id": user["id"]}
    if status:
        query["status"] = status
    
    requests = await _db.deposit_requests.find(
        query, {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    return {"requests": requests}


@router.get("/usdt/deposit/active-request")
async def get_active_deposit_request(user: dict = Depends(get_current_user)):
    """Get user's active deposit request"""
    request = await _db.deposit_requests.find_one(
        {
            "user_id": user["id"],
            "status": "pending",
            "expires_at": {"$gte": datetime.now(timezone.utc).isoformat()}
        },
        {"_id": 0}
    )
    
    # Get platform TON address from auto-withdraw config
    platform_ton_address = ""
    auto_config = await _db.auto_withdraw_config.find_one({"active": True}, {"_id": 0})
    if auto_config:
        platform_ton_address = auto_config.get("wallet_address", "")
    
    if not platform_ton_address:
        settings = await _db.platform_settings.find_one({"type": "auto_withdraw"}, {"_id": 0})
        if settings:
            platform_ton_address = settings.get("wallet_address", "")
    
    if request:
        # Add platform address to request if not already there
        if not request.get("ton_address"):
            request["ton_address"] = platform_ton_address
    
    return {
        "active_request": request,
        "platform_ton_address": platform_ton_address
    }


@router.post("/usdt/withdrawal/create")
async def create_withdrawal(
    data: WithdrawalRequest,
    user: dict = Depends(get_current_user)
):
    """Create USDT withdrawal request - immediately deducts from balance"""
    amount = data.get_amount()
    address = data.get_address()
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    
    if not address:
        raise HTTPException(status_code=400, detail="Address is required")
    
    # Check balance in MAIN wallet (wallets collection, not usdt_wallets)
    wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    
    if not wallet:
        raise HTTPException(status_code=400, detail="Wallet not found")
    
    available_balance = wallet.get("available_balance_usdt", 0) or 0
    
    if available_balance < amount:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно средств. Доступно: {available_balance:.2f} USDT"
        )
    
    # Create withdrawal
    withdrawal = {
        "id": generate_id("wd_"),
        "user_id": user["id"],
        "amount_usdt": amount,
        "address": address,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # ATOMIC operation: deduct ONLY if balance >= amount (prevents negative balance)
    update_result = await _db.wallets.update_one(
        {
            "user_id": user["id"],
            "available_balance_usdt": {"$gte": amount}  # Atomic check
        },
        {
            "$inc": {
                "available_balance_usdt": -amount,
                "pending_withdrawal_usdt": amount,
                "total_withdrawn_usdt": amount
            }
        }
    )
    
    # If no document was modified, balance was insufficient (race condition protection)
    if update_result.modified_count == 0:
        # Re-check current balance for accurate error message
        wallet = await _db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
        current_balance = wallet.get("available_balance_usdt", 0) if wallet else 0
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно средств. Доступно: {current_balance:.2f} USDT"
        )
    
    await _db.usdt_withdrawals.insert_one(withdrawal)
    
    # Check if user is trusted for auto-withdrawal
    is_trusted = user.get("is_trusted", False) or user.get("withdrawal_auto_approve", False)
    
    if is_trusted:
        # Try auto-withdrawal
        try:
            from server import send_usdt_withdrawal, get_hot_wallet_balance
            
            hot_balance = await get_hot_wallet_balance()
            
            if hot_balance >= amount:
                # Auto-process withdrawal
                result = await send_usdt_withdrawal(address, amount, withdrawal["id"])
                
                if result.get("success"):
                    # Update withdrawal status
                    await _db.usdt_withdrawals.update_one(
                        {"id": withdrawal["id"]},
                        {"$set": {
                            "status": "completed",
                            "tx_hash": result.get("tx_hash"),
                            "processed_at": datetime.now(timezone.utc).isoformat(),
                            "auto_processed": True
                        }}
                    )
                    
                    # Update wallet - move from pending to withdrawn
                    await _db.wallets.update_one(
                        {"user_id": user["id"]},
                        {"$inc": {
                            "pending_withdrawal_usdt": -amount,
                            "total_withdrawn_usdt": amount
                        }}
                    )
                    
                    logger.info(f"Auto-withdrawal processed for trusted user {user['id']}: {amount} USDT")
                    
                    return {
                        "success": True,
                        "withdrawal_id": withdrawal["id"],
                        "amount_usdt": amount,
                        "status": "completed",
                        "tx_hash": result.get("tx_hash"),
                        "auto_processed": True,
                        "message": "Вывод автоматически обработан"
                    }
                else:
                    logger.warning(f"Auto-withdrawal failed for {user['id']}: {result.get('error')}")
            else:
                logger.warning(f"Auto-withdrawal skipped - insufficient hot wallet balance: {hot_balance} < {amount}")
        except Exception as e:
            logger.error(f"Auto-withdrawal error: {e}")
    
    return {
        "success": True,
        "withdrawal_id": withdrawal["id"],
        "amount_usdt": amount,
        "status": "pending"
    }


@router.post("/usdt/withdrawal/{withdrawal_id}/cancel")
async def cancel_withdrawal(
    withdrawal_id: str,
    user: dict = Depends(get_current_user)
):
    """Cancel pending withdrawal - returns funds to balance"""
    withdrawal = await _db.usdt_withdrawals.find_one(
        {"id": withdrawal_id, "user_id": user["id"]},
        {"_id": 0}
    )
    
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    if withdrawal["status"] != "pending":
        raise HTTPException(status_code=400, detail="Можно отменить только ожидающие заявки")
    
    # Return funds to balance (from pending_withdrawal back to available)
    await _db.wallets.update_one(
        {"user_id": user["id"]},
        {"$inc": {
            "available_balance_usdt": withdrawal["amount_usdt"],
            "pending_withdrawal_usdt": -withdrawal["amount_usdt"]
        }}
    )
    
    # Update status
    await _db.usdt_withdrawals.update_one(
        {"id": withdrawal_id},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"success": True, "message": "Заявка отменена, средства возвращены на баланс"}
