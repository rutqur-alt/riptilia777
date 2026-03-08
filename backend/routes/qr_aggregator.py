"""
QR Aggregator Routes v2
Fully rewritten per TZ requirements:
- Two separate integrations: NSPK (QR) and TransGrant (CNG)
- Provider balance in USDT
- Provider deposit via USDT (same as regular users)
- Provider withdrawal (same as regular users)
- Separate statistics per integration
- Commission settings per integration
- Strict TrustGain API integration per https://docs.trustgain.io/
"""
import os
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, Body
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import uuid
import hmac
import hashlib
import json
import logging
import asyncio

from core.database import db
from core.auth import get_current_user, require_role, require_admin_level, create_token, hash_password, verify_password

router = APIRouter(tags=["QR Aggregator"])
logger = logging.getLogger(__name__)

# ==================== Pydantic Models ====================

class QRProviderCreate(BaseModel):
    login: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    display_name: str = Field(..., min_length=2, max_length=100)
    # NSPK (QR) integration settings
    nspk_api_key: str = Field(default="")
    nspk_secret_key: str = Field(default="")
    nspk_api_url: str = Field(default="https://api.trustgain.io")
    nspk_merchant_id: str = Field(default="")
    nspk_gateway_id: str = Field(default="")
    nspk_enabled: bool = Field(default=True)
    nspk_commission_percent: float = Field(default=5.0, ge=0, le=50)
    # TransGrant (CNG) integration settings
    transgrant_api_key: str = Field(default="")
    transgrant_secret_key: str = Field(default="")
    transgrant_api_url: str = Field(default="https://api.trustgain.io")
    transgrant_merchant_id: str = Field(default="")
    transgrant_gateway_id: str = Field(default="")
    transgrant_enabled: bool = Field(default=False)
    transgrant_commission_percent: float = Field(default=7.0, ge=0, le=50)
    # General
    weight: int = Field(default=100, ge=1, le=1000)
    max_concurrent_operations: int = Field(default=10, ge=1, le=100)

class QRProviderUpdate(BaseModel):
    display_name: Optional[str] = None
    # NSPK
    nspk_api_key: Optional[str] = None
    nspk_secret_key: Optional[str] = None
    nspk_api_url: Optional[str] = None
    nspk_merchant_id: Optional[str] = None
    nspk_gateway_id: Optional[str] = None
    nspk_enabled: Optional[bool] = None
    nspk_commission_percent: Optional[float] = None
    # TransGrant
    transgrant_api_key: Optional[str] = None
    transgrant_secret_key: Optional[str] = None
    transgrant_api_url: Optional[str] = None
    transgrant_merchant_id: Optional[str] = None
    transgrant_gateway_id: Optional[str] = None
    transgrant_enabled: Optional[bool] = None
    transgrant_commission_percent: Optional[float] = None
    # General
    weight: Optional[int] = None
    max_concurrent_operations: Optional[int] = None
    is_active: Optional[bool] = None

class QRProviderLogin(BaseModel):
    login: str
    password: str

class QRAggregatorSettings(BaseModel):
    is_enabled: bool = True
    health_check_interval: int = Field(default=45, ge=10, le=300)
    # NSPK settings
    nspk_min_amount: float = Field(default=100, ge=0)
    nspk_max_amount: float = Field(default=500000, ge=0)
    nspk_commission_percent: float = Field(default=5.0, ge=0, le=50)
    # TransGrant settings
    transgrant_min_amount: float = Field(default=100, ge=0)
    transgrant_max_amount: float = Field(default=300000, ge=0)
    transgrant_commission_percent: float = Field(default=7.0, ge=0, le=50)

class WithdrawRequest(BaseModel):
    amount: float = Field(..., gt=0)
    to_address: str = Field(..., min_length=48)

# ==================== Helper Functions ====================

def _mask_key(key: str) -> str:
    """Mask API key for display"""
    if not key or len(key) < 12:
        return "***" if key else ""
    return key[:6] + "..." + key[-4:]

def _mask_secret(key: str) -> str:
    """Mask secret key for display"""
    if not key or len(key) < 8:
        return "****" if key else ""
    return "*" * (len(key) - 4) + key[-4:]

async def _get_qr_provider_user(user: dict = Depends(get_current_user)):
    """Dependency: ensure user is a qr_provider"""
    if user.get("role") != "qr_provider":
        raise HTTPException(status_code=403, detail="QR Provider access required")
    provider = await db.qr_providers.find_one({"id": user["id"]}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider

async def _get_base_rate() -> float:
    """Get base USDT/RUB exchange rate"""
    payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    return payout_settings.get("base_rate", 78.0) if payout_settings else 78.0

# ==================== QR Provider Auth ====================

@router.post("/qr-provider/login")
async def qr_provider_login(data: QRProviderLogin):
    """Login as QR Provider"""
    provider = await db.qr_providers.find_one({"login": data.login}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    if not verify_password(data.password, provider.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    if not provider.get("is_active", False):
        raise HTTPException(status_code=403, detail="Аккаунт деактивирован")

    token = create_token(provider["id"], "qr_provider")

    await db.qr_providers.update_one(
        {"id": provider["id"]},
        {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}}
    )

    return {
        "token": token,
        "user": {
            "id": provider["id"],
            "login": provider["login"],
            "display_name": provider["display_name"],
            "role": "qr_provider",
            "is_active": provider.get("is_active", False),
        }
    }

# ==================== QR Provider Personal Cabinet ====================

@router.get("/qr-provider/me")
async def get_qr_provider_profile(provider: dict = Depends(_get_qr_provider_user)):
    """Get current QR provider profile (sensitive keys masked)"""
    safe = {k: v for k, v in provider.items() if k not in (
        "password_hash", "nspk_secret_key", "transgrant_secret_key"
    )}
    # Mask API keys
    for prefix in ("nspk", "transgrant"):
        key_field = f"{prefix}_api_key"
        if safe.get(key_field):
            safe[key_field] = _mask_key(safe[key_field])
    return safe

@router.get("/qr-provider/stats")
async def get_qr_provider_stats(provider: dict = Depends(_get_qr_provider_user)):
    """Get provider statistics - SEPARATE per integration (NSPK + TransGrant)"""
    provider_id = provider["id"]
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    stats = {}
    for method in ("nspk", "transgrant"):
        # Today
        today_ops = await db.qr_provider_operations.count_documents({
            "provider_id": provider_id, "payment_method": method,
            "created_at": {"$gte": today_start}
        })
        today_completed = await db.qr_provider_operations.count_documents({
            "provider_id": provider_id, "payment_method": method,
            "status": "completed", "created_at": {"$gte": today_start}
        })
        today_vol_cur = db.qr_provider_operations.aggregate([
            {"$match": {"provider_id": provider_id, "payment_method": method,
                        "status": "completed", "created_at": {"$gte": today_start}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount_rub"}}}
        ])
        today_vol_list = await today_vol_cur.to_list(1)
        today_volume = today_vol_list[0]["total"] if today_vol_list else 0

        # All-time
        total_ops = await db.qr_provider_operations.count_documents({
            "provider_id": provider_id, "payment_method": method
        })
        total_completed = await db.qr_provider_operations.count_documents({
            "provider_id": provider_id, "payment_method": method, "status": "completed"
        })
        total_vol_cur = db.qr_provider_operations.aggregate([
            {"$match": {"provider_id": provider_id, "payment_method": method, "status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount_rub"}}}
        ])
        total_vol_list = await total_vol_cur.to_list(1)
        total_volume = total_vol_list[0]["total"] if total_vol_list else 0

        success_rate = (total_completed / total_ops * 100) if total_ops > 0 else 100.0

        stats[method] = {
            "today": {
                "operations": today_ops,
                "completed": today_completed,
                "volume_rub": round(today_volume, 2),
            },
            "total": {
                "operations": total_ops,
                "completed": total_completed,
                "volume_rub": round(total_volume, 2),
            },
            "success_rate": round(success_rate, 1),
        }

    # Active operations count
    active_ops = await db.qr_provider_operations.count_documents({
        "provider_id": provider_id, "status": {"$in": ["pending", "processing"]}
    })

    return {
        "nspk": stats["nspk"],
        "transgrant": stats["transgrant"],
        "active_operations": active_ops,
        "balance_usdt": provider.get("balance_usdt", 0),
        "frozen_usdt": provider.get("frozen_usdt", 0),
        "is_active": provider.get("is_active", False),
        "nspk_api_available": provider.get("nspk_api_available", False),
        "transgrant_api_available": provider.get("transgrant_api_available", False),
    }

@router.get("/qr-provider/operations")
async def get_qr_provider_operations(
    status: Optional[str] = None,
    method: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    provider: dict = Depends(_get_qr_provider_user)
):
    """Get provider's operations history (filterable by method: nspk/transgrant)"""
    query = {"provider_id": provider["id"]}
    if status:
        query["status"] = status
    if method:
        query["payment_method"] = method

    total = await db.qr_provider_operations.count_documents(query)
    skip = (page - 1) * limit

    operations = await db.qr_provider_operations.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {
        "operations": operations,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

# ==================== Provider Wallet (USDT Balance) ====================

@router.get("/qr-provider/wallet")
async def get_qr_provider_wallet(provider: dict = Depends(_get_qr_provider_user)):
    """Get provider wallet info - balance in USDT"""
    provider_id = provider["id"]

    # Calculate total earnings
    earnings_cursor = db.qr_provider_operations.aggregate([
        {"$match": {"provider_id": provider_id, "status": "completed"}},
        {"$group": {"_id": None, "total_earnings": {"$sum": "$provider_earning_usdt"}}}
    ])
    earnings_list = await earnings_cursor.to_list(1)
    total_earnings = earnings_list[0]["total_earnings"] if earnings_list else 0

    balance_usdt = provider.get("balance_usdt", 0)
    frozen_usdt = provider.get("frozen_usdt", 0)

    return {
        "balance_usdt": round(balance_usdt, 2),
        "frozen_usdt": round(frozen_usdt, 2),
        "available_usdt": round(balance_usdt - frozen_usdt, 2),
        "total_earnings_usdt": round(total_earnings, 2),
        "is_active": provider.get("is_active", False),
        "nspk_enabled": provider.get("nspk_enabled", False),
        "transgrant_enabled": provider.get("transgrant_enabled", False),
    }

@router.get("/qr-provider/deposit-address")
async def get_qr_provider_deposit_address(provider: dict = Depends(_get_qr_provider_user)):
    """
    Get deposit address for provider - same flow as regular users.
    Provider sends USDT to hot wallet with deposit_code as comment.
    """
    provider_id = provider["id"]
    import random, string

    deposit_code = provider.get("deposit_code")
    if not deposit_code:
        # Generate unique 6-digit deposit code
        for _ in range(20):
            code = ''.join(random.choices(string.digits, k=6))
            existing = await db.qr_providers.find_one({"deposit_code": code})
            if not existing:
                # Also check traders/merchants to avoid collision
                ex2 = await db.traders.find_one({"deposit_code": code})
                ex3 = await db.merchants.find_one({"deposit_code": code})
                if not ex2 and not ex3:
                    deposit_code = code
                    await db.qr_providers.update_one(
                        {"id": provider_id},
                        {"$set": {"deposit_code": code}}
                    )
                    break

    # Get hot wallet address from TON service
    try:
        from routes.ton_finance import get_deposit_address
        result = await get_deposit_address(provider_id)
        wallet_address = result.get("address", "")
    except Exception as e:
        logger.error(f"[QR Provider] Failed to get deposit address: {e}")
        # Fallback - get from settings
        settings = await db.settings.find_one({"type": "ton_settings"}, {"_id": 0})
        wallet_address = settings.get("hot_wallet_address", "") if settings else ""

    return {
        "deposit_info": {
            "address": wallet_address,
            "comment": deposit_code,
            "instructions": [
                f"1. Отправьте USDT (TRC-20 или TON) на адрес выше",
                f"2. ОБЯЗАТЕЛЬНО укажите комментарий: {deposit_code}",
                "3. Депозит будет зачислен автоматически после подтверждения",
            ],
        }
    }

@router.post("/qr-provider/withdraw")
async def qr_provider_withdraw(data: WithdrawRequest, provider: dict = Depends(_get_qr_provider_user)):
    """
    Request USDT withdrawal - same flow as regular users.
    1. Check balance
    2. Freeze funds
    3. Create withdrawal request (pending)
    """
    provider_id = provider["id"]
    now = datetime.now(timezone.utc).isoformat()

    # Anti double-click
    five_seconds_ago = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    recent = await db.withdrawal_requests.find_one({
        "user_id": provider_id, "amount": data.amount,
        "created_at": {"$gte": five_seconds_ago}, "status": "pending"
    })
    if recent:
        raise HTTPException(status_code=429, detail="Заявка уже создана. Подождите.")

    balance_usdt = provider.get("balance_usdt", 0)
    frozen_usdt = provider.get("frozen_usdt", 0)
    available = balance_usdt - frozen_usdt

    WITHDRAWAL_FEE = 1.0  # 1 USDT fee
    total_needed = data.amount + WITHDRAWAL_FEE

    if total_needed > available:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно средств. Нужно: {total_needed:.2f} USDT (включая комиссию {WITHDRAWAL_FEE} USDT). Доступно: {available:.2f} USDT"
        )

    # Freeze funds
    result = await db.qr_providers.update_one(
        {"id": provider_id, "balance_usdt": {"$gte": frozen_usdt + total_needed}},
        {"$inc": {"frozen_usdt": total_needed}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Недостаточно средств")

    request_id = f"wd_{uuid.uuid4().hex[:12]}"

    withdrawal_doc = {
        "id": request_id,
        "user_id": provider_id,
        "user_role": "qr_provider",
        "amount": data.amount,
        "fee": WITHDRAWAL_FEE,
        "total": total_needed,
        "to_address": data.to_address,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    await db.withdrawal_requests.insert_one(withdrawal_doc)

    # Transaction record
    tx_doc = {
        "id": f"tx_{uuid.uuid4().hex[:12]}",
        "user_id": provider_id,
        "user_role": "qr_provider",
        "type": "withdrawal",
        "amount": -total_needed,
        "status": "pending",
        "description": f"Вывод {data.amount} USDT на {data.to_address[:10]}...",
        "withdrawal_request_id": request_id,
        "created_at": now,
    }
    await db.transactions.insert_one(tx_doc)

    logger.info(f"[QR Provider] Withdrawal request created: {request_id}, amount={data.amount} USDT")

    return {
        "status": "success",
        "request_id": request_id,
        "amount": data.amount,
        "fee": WITHDRAWAL_FEE,
        "total": total_needed,
    }

@router.get("/qr-provider/finances")
async def get_qr_provider_finances(provider: dict = Depends(_get_qr_provider_user)):
    """QR Provider: Financial overview with separate stats per integration"""
    provider_id = provider["id"]

    # Separate stats per method
    finances = {}
    for method in ("nspk", "transgrant"):
        pipeline = [
            {"$match": {"provider_id": provider_id, "payment_method": method, "status": "completed"}},
            {"$group": {
                "_id": None,
                "total_amount_rub": {"$sum": "$amount_rub"},
                "total_earning_usdt": {"$sum": "$provider_earning_usdt"},
                "count": {"$sum": 1},
            }}
        ]
        agg = await db.qr_provider_operations.aggregate(pipeline).to_list(1)
        total_ops = await db.qr_provider_operations.count_documents({
            "provider_id": provider_id, "payment_method": method
        })
        completed = agg[0]["count"] if agg else 0
        finances[method] = {
            "total_operations": total_ops,
            "completed_operations": completed,
            "turnover_rub": round(agg[0]["total_amount_rub"], 2) if agg else 0,
            "earnings_usdt": round(agg[0]["total_earning_usdt"], 4) if agg else 0,
            "success_rate": round((completed / total_ops * 100) if total_ops > 0 else 100, 1),
        }

    # Recent transactions (deposits + withdrawals + operations)
    recent_txs = await db.transactions.find(
        {"user_id": provider_id}, {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)

    # Withdrawal history
    withdrawals = await db.withdrawal_requests.find(
        {"user_id": provider_id}, {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)

    return {
        "balance_usdt": round(provider.get("balance_usdt", 0), 2),
        "frozen_usdt": round(provider.get("frozen_usdt", 0), 2),
        "available_usdt": round(provider.get("balance_usdt", 0) - provider.get("frozen_usdt", 0), 2),
        "nspk": finances["nspk"],
        "transgrant": finances["transgrant"],
        "recent_transactions": recent_txs,
        "withdrawal_history": withdrawals,
    }

# ==================== Admin: QR Provider Management ====================

@router.get("/admin/qr-providers")
async def admin_list_qr_providers(user: dict = Depends(require_admin_level(50))):
    """Admin: List all QR providers"""
    providers = await db.qr_providers.find(
        {}, {"_id": 0, "password_hash": 0, "nspk_secret_key": 0, "transgrant_secret_key": 0}
    ).to_list(100)

    for p in providers:
        for prefix in ("nspk", "transgrant"):
            key_field = f"{prefix}_api_key"
            if p.get(key_field):
                p[key_field] = _mask_key(p[key_field])

    return {"providers": providers, "total": len(providers)}

@router.post("/admin/qr-providers")
async def admin_create_qr_provider(data: QRProviderCreate, user: dict = Depends(require_admin_level(80))):
    """Admin: Create a new QR provider"""
    existing = await db.qr_providers.find_one({"login": data.login})
    if existing:
        raise HTTPException(status_code=400, detail="Провайдер с таким логином уже существует")

    provider_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    provider_doc = {
        "id": provider_id,
        "login": data.login,
        "password_hash": hash_password(data.password),
        "display_name": data.display_name,
        # NSPK integration
        "nspk_api_key": data.nspk_api_key,
        "nspk_secret_key": data.nspk_secret_key,
        "nspk_api_url": data.nspk_api_url,
        "nspk_merchant_id": data.nspk_merchant_id,
        "nspk_gateway_id": data.nspk_gateway_id,
        "nspk_enabled": data.nspk_enabled,
        "nspk_commission_percent": data.nspk_commission_percent,
        "nspk_api_available": False,
        # TransGrant integration
        "transgrant_api_key": data.transgrant_api_key,
        "transgrant_secret_key": data.transgrant_secret_key,
        "transgrant_api_url": data.transgrant_api_url,
        "transgrant_merchant_id": data.transgrant_merchant_id,
        "transgrant_gateway_id": data.transgrant_gateway_id,
        "transgrant_enabled": data.transgrant_enabled,
        "transgrant_commission_percent": data.transgrant_commission_percent,
        "transgrant_api_available": False,
        # Balance in USDT
        "balance_usdt": 0,
        "frozen_usdt": 0,
        # General
        "weight": data.weight,
        "max_concurrent_operations": data.max_concurrent_operations,
        "active_operations_count": 0,
        "is_active": True,
        "success_rate": 100.0,
        "total_operations": 0,
        "completed_operations": 0,
        "last_health_check": None,
        "last_seen": None,
        "deposit_code": None,
        "created_at": now,
        "updated_at": now,
    }

    await db.qr_providers.insert_one(provider_doc)

    safe_doc = {k: v for k, v in provider_doc.items()
                if k not in ("password_hash", "nspk_secret_key", "transgrant_secret_key", "_id")}
    logger.info(f"[QR Aggregator] Provider created: {provider_id} ({data.login})")

    return {"status": "success", "provider": safe_doc}

@router.get("/admin/qr-providers/{provider_id}")
async def admin_get_qr_provider(provider_id: str, user: dict = Depends(require_admin_level(50))):
    """Admin: Get QR provider details"""
    provider = await db.qr_providers.find_one({"id": provider_id}, {"_id": 0, "password_hash": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    for prefix in ("nspk", "transgrant"):
        sk = f"{prefix}_secret_key"
        ak = f"{prefix}_api_key"
        if provider.get(sk):
            provider[sk] = _mask_secret(provider[sk])
        if provider.get(ak):
            provider[ak] = _mask_key(provider[ak])

    return provider

@router.put("/admin/qr-providers/{provider_id}")
async def admin_update_qr_provider(provider_id: str, data: QRProviderUpdate, user: dict = Depends(require_admin_level(80))):
    """Admin: Update QR provider"""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    update_data = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value

    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.qr_providers.update_one({"id": provider_id}, {"$set": update_data})

    logger.info(f"[QR Aggregator] Provider updated: {provider_id}, fields: {list(update_data.keys())}")
    return {"status": "success", "updated_fields": list(update_data.keys())}

@router.delete("/admin/qr-providers/{provider_id}")
async def admin_delete_qr_provider(provider_id: str, user: dict = Depends(require_admin_level(100))):
    """Admin: Delete QR provider (owner only)"""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    active_ops = await db.qr_provider_operations.count_documents({
        "provider_id": provider_id, "status": {"$in": ["pending", "processing"]}
    })
    if active_ops > 0:
        raise HTTPException(status_code=400, detail=f"У провайдера есть {active_ops} активных операций.")

    if provider.get("balance_usdt", 0) > 0:
        raise HTTPException(status_code=400, detail="У провайдера есть баланс. Сначала выведите средства.")

    await db.qr_providers.delete_one({"id": provider_id})
    logger.info(f"[QR Aggregator] Provider deleted: {provider_id}")
    return {"status": "success"}

@router.post("/admin/qr-providers/{provider_id}/toggle")
async def admin_toggle_qr_provider(provider_id: str, user: dict = Depends(require_admin_level(80))):
    """Admin: Toggle provider active status"""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    new_status = not provider.get("is_active", False)
    await db.qr_providers.update_one(
        {"id": provider_id},
        {"$set": {"is_active": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    logger.info(f"[QR Aggregator] Provider {provider_id} {'activated' if new_status else 'deactivated'}")
    return {"status": "success", "is_active": new_status}

@router.post("/admin/qr-providers/{provider_id}/reset-password")
async def admin_reset_qr_provider_password(provider_id: str, user: dict = Depends(require_admin_level(80))):
    """Admin: Reset QR provider password"""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    import secrets, string
    chars = string.ascii_letters + string.digits + "!@#$%"
    new_password = ''.join(secrets.choice(chars) for _ in range(12))

    await db.qr_providers.update_one(
        {"id": provider_id},
        {"$set": {"password_hash": hash_password(new_password), "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    logger.info(f"[QR Aggregator] Password reset for provider: {provider_id}")
    return {"status": "success", "new_password": new_password}

@router.put("/admin/qr-providers/{provider_id}/api-keys")
async def admin_update_qr_provider_api_keys(provider_id: str, request: Request, user: dict = Depends(require_admin_level(80))):
    """Admin: Update QR provider API keys for NSPK or TransGrant integration"""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    body = await request.json()
    update_data = {}

    # NSPK fields
    for field in ("nspk_api_key", "nspk_secret_key", "nspk_api_url", "nspk_merchant_id", "nspk_gateway_id"):
        if field in body and body[field]:
            update_data[field] = body[field]

    # TransGrant fields
    for field in ("transgrant_api_key", "transgrant_secret_key", "transgrant_api_url", "transgrant_merchant_id", "transgrant_gateway_id"):
        if field in body and body[field]:
            update_data[field] = body[field]

    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.qr_providers.update_one({"id": provider_id}, {"$set": update_data})

    logger.info(f"[QR Aggregator] API keys updated for provider: {provider_id}, fields: {list(update_data.keys())}")
    return {"status": "success", "updated_fields": list(update_data.keys())}

@router.get("/admin/qr-providers/{provider_id}/api-keys")
async def admin_get_qr_provider_api_keys(provider_id: str, user: dict = Depends(require_admin_level(80))):
    """Admin: Get QR provider API keys (masked) - separate per integration"""
    provider = await db.qr_providers.find_one({"id": provider_id}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    return {
        "nspk": {
            "api_key": provider.get("nspk_api_key", ""),
            "secret_key": _mask_secret(provider.get("nspk_secret_key", "")),
            "api_url": provider.get("nspk_api_url", "https://api.trustgain.io"),
            "merchant_id": provider.get("nspk_merchant_id", ""),
            "gateway_id": provider.get("nspk_gateway_id", ""),
        },
        "transgrant": {
            "api_key": provider.get("transgrant_api_key", ""),
            "secret_key": _mask_secret(provider.get("transgrant_secret_key", "")),
            "api_url": provider.get("transgrant_api_url", "https://api.trustgain.io"),
            "merchant_id": provider.get("transgrant_merchant_id", ""),
            "gateway_id": provider.get("transgrant_gateway_id", ""),
        },
    }

@router.post("/admin/qr-providers/{provider_id}/health-check")
async def admin_health_check_provider(provider_id: str, user: dict = Depends(require_admin_level(50))):
    """Admin: Manually trigger health check for both integrations"""
    provider = await db.qr_providers.find_one({"id": provider_id}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    from services.trustgain_client import TrustGainClient
    results = {}

    for prefix in ("nspk", "transgrant"):
        api_key = provider.get(f"{prefix}_api_key", "")
        secret_key = provider.get(f"{prefix}_secret_key", "")
        api_url = provider.get(f"{prefix}_api_url", "https://api.trustgain.io")

        if not api_key or api_key.startswith("demo") or len(api_key) < 10:
            results[prefix] = False
            continue

        client = TrustGainClient(api_url=api_url, api_key=api_key, secret_key=secret_key)
        is_healthy = await client.check_health()
        await client.close()
        results[prefix] = is_healthy

    now = datetime.now(timezone.utc).isoformat()
    await db.qr_providers.update_one(
        {"id": provider_id},
        {"$set": {
            "nspk_api_available": results.get("nspk", False),
            "transgrant_api_available": results.get("transgrant", False),
            "last_health_check": now,
        }}
    )

    return {"status": "success", "nspk_available": results.get("nspk"), "transgrant_available": results.get("transgrant"), "checked_at": now}

# ==================== Admin: QR Aggregator Settings ====================

@router.get("/admin/qr-aggregator/settings")
async def admin_get_qr_settings(user: dict = Depends(require_admin_level(50))):
    """Admin: Get QR Aggregator settings (separate per integration)"""
    settings = await db.qr_aggregator_settings.find_one({"type": "main"}, {"_id": 0})
    if not settings:
        settings = {
            "type": "main",
            "is_enabled": True,
            "health_check_interval": 45,
            "nspk_min_amount": 100,
            "nspk_max_amount": 500000,
            "nspk_commission_percent": 5.0,
            "transgrant_min_amount": 100,
            "transgrant_max_amount": 300000,
            "transgrant_commission_percent": 7.0,
        }
        await db.qr_aggregator_settings.insert_one(settings)
    return settings

@router.put("/admin/qr-aggregator/settings")
async def admin_update_qr_settings(data: QRAggregatorSettings, user: dict = Depends(require_admin_level(80))):
    """Admin: Update QR Aggregator settings (separate commissions per integration)"""
    update = data.model_dump()
    update["type"] = "main"
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.qr_aggregator_settings.update_one(
        {"type": "main"}, {"$set": update}, upsert=True
    )
    return {"status": "success"}



class AdminAdjustBalance(BaseModel):
    amount: float = Field(..., description="Amount to add (positive) or subtract (negative)")
    reason: str = Field(default="admin_adjustment", description="Reason for adjustment")

@router.post("/admin/qr-providers/{provider_id}/adjust-balance")
async def admin_adjust_provider_balance(provider_id: str, data: AdminAdjustBalance, user: dict = Depends(require_admin_level(80))):
    """Admin: Adjust provider balance (add or subtract USDT)"""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    current_balance = provider.get("balance_usdt", 0)
    current_frozen = provider.get("frozen_usdt", 0)
    available = current_balance - current_frozen
    
    # If subtracting, check we don't go below frozen
    if data.amount < 0 and abs(data.amount) > available:
        raise HTTPException(status_code=400, detail=f"Cannot subtract {abs(data.amount)} USDT. Available: {round(available, 4)} USDT (frozen: {round(current_frozen, 4)})")
    
    new_balance = round(current_balance + data.amount, 6)
    if new_balance < 0:
        raise HTTPException(status_code=400, detail="Balance cannot go negative")
    
    await db.qr_providers.update_one(
        {"id": provider_id},
        {"$set": {"balance_usdt": new_balance, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Log the adjustment
    log_entry = {
        "id": str(uuid.uuid4()),
        "provider_id": provider_id,
        "type": "admin_adjustment",
        "amount": data.amount,
        "reason": data.reason,
        "old_balance": current_balance,
        "new_balance": new_balance,
        "admin_id": user.get("id"),
        "admin_login": user.get("login"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.qr_provider_balance_logs.insert_one(log_entry)
    
    logger.info(f"[QR Admin] Balance adjusted for {provider_id}: {current_balance} -> {new_balance} ({data.amount:+.4f}) by {user.get('login')}, reason: {data.reason}")
    
    return {
        "status": "success",
        "old_balance": round(current_balance, 4),
        "new_balance": round(new_balance, 4),
        "adjustment": data.amount,
        "available": round(new_balance - current_frozen, 4),
    }

@router.post("/admin/qr-providers/{provider_id}/reconcile-frozen")
async def admin_reconcile_frozen(provider_id: str, user: dict = Depends(require_admin_level(80))):
    """Admin: Reconcile frozen balance - recalculate from actual active trades"""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Calculate actual frozen from active trades
    active_trades = await db.trades.find({
        "provider_id": provider_id,
        "status": {"$in": ["pending", "paid"]},
        "$or": [{"trader_id": "qr_aggregator"}, {"qr_aggregator_trade": True}]
    }).to_list(500)
    
    actual_frozen = sum(t.get("total_freeze_usdt", 0) for t in active_trades)
    old_frozen = provider.get("frozen_usdt", 0)
    
    active_ops = await db.qr_provider_operations.count_documents({
        "provider_id": provider_id,
        "status": {"$in": ["pending", "processing"]}
    })
    
    await db.qr_providers.update_one(
        {"id": provider_id},
        {"$set": {
            "frozen_usdt": round(actual_frozen, 6),
            "active_operations_count": len(active_trades),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    
    # Fix stale pending operations
    fixed_ops = 0
    pending_ops = await db.qr_provider_operations.find({
        "provider_id": provider_id,
        "status": "pending"
    }).to_list(100)
    for op in pending_ops:
        trade = await db.trades.find_one({"id": op.get("trade_id")})
        if trade and trade.get("status") in ("cancelled", "completed"):
            await db.qr_provider_operations.update_one(
                {"id": op["id"]},
                {"$set": {"status": trade["status"], "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            fixed_ops += 1
    
    logger.info(f"[QR Admin] Reconciled frozen for {provider_id}: {old_frozen} -> {actual_frozen}, fixed {fixed_ops} stale ops")
    
    return {
        "status": "success",
        "old_frozen": round(old_frozen, 4),
        "new_frozen": round(actual_frozen, 4),
        "active_trades": len(active_trades),
        "fixed_operations": fixed_ops,
        "available": round(provider.get("balance_usdt", 0) - actual_frozen, 4),
    }

@router.get("/admin/qr-providers/{provider_id}/balance-logs")
async def admin_get_balance_logs(provider_id: str, user: dict = Depends(require_admin_level(50))):
    """Admin: Get provider balance adjustment history"""
    logs = await db.qr_provider_balance_logs.find(
        {"provider_id": provider_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"logs": logs}


@router.get("/admin/qr-aggregator/stats")
async def admin_get_qr_aggregator_stats(user: dict = Depends(require_admin_level(50))):
    """Admin: Get QR Aggregator overall statistics"""
    total_providers = await db.qr_providers.count_documents({})
    active_providers = await db.qr_providers.count_documents({"is_active": True})

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    stats = {}
    for method in ("nspk", "transgrant"):
        total_ops = await db.qr_provider_operations.count_documents({"payment_method": method})
        completed_ops = await db.qr_provider_operations.count_documents({"payment_method": method, "status": "completed"})
        today_ops = await db.qr_provider_operations.count_documents({
            "payment_method": method, "created_at": {"$gte": today_start}
        })
        today_completed = await db.qr_provider_operations.count_documents({
            "payment_method": method, "status": "completed", "created_at": {"$gte": today_start}
        })

        vol_cur = db.qr_provider_operations.aggregate([
            {"$match": {"payment_method": method, "status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount_rub"}}}
        ])
        vol_list = await vol_cur.to_list(1)
        total_volume = vol_list[0]["total"] if vol_list else 0

        today_vol_cur = db.qr_provider_operations.aggregate([
            {"$match": {"payment_method": method, "status": "completed", "created_at": {"$gte": today_start}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount_rub"}}}
        ])
        today_vol_list = await today_vol_cur.to_list(1)
        today_volume = today_vol_list[0]["total"] if today_vol_list else 0

        stats[method] = {
            "total_operations": total_ops,
            "completed": completed_ops,
            "today_operations": today_ops,
            "today_completed": today_completed,
            "total_volume_rub": round(total_volume, 2),
            "today_volume_rub": round(today_volume, 2),
        }

    # Total deposits across active providers
    deposit_cursor = db.qr_providers.aggregate([
        {"$match": {"is_active": True}},
        {"$group": {"_id": None, "total": {"$sum": "$balance_usdt"}}}
    ])
    deposit_list = await deposit_cursor.to_list(1)
    total_deposit_usdt = deposit_list[0]["total"] if deposit_list else 0

    return {
        "providers": {"total": total_providers, "active": active_providers},
        "nspk": stats["nspk"],
        "transgrant": stats["transgrant"],
        "total_deposit_usdt": round(total_deposit_usdt, 2),
    }

# ==================== Webhook Handling ====================

@router.post("/qr-aggregator/webhook/{provider_id}")
async def handle_trustgain_webhook(provider_id: str, request: Request, background_tasks: BackgroundTasks):
    """Handle incoming webhook from TrustGain"""
    provider = await db.qr_providers.find_one({"id": provider_id}, {"_id": 0})
    if not provider:
        logger.error(f"[QR Webhook] Unknown provider: {provider_id}")
        raise HTTPException(status_code=404, detail="Provider not found")

    body = await request.body()
    body_str = body.decode("utf-8")

    # Verify webhook signature per docs:
    # Header: Payments-Signature: "t=<timestamp>,s=<signature>"
    sig_header = request.headers.get("Payments-Signature", "")

    # Determine which integration's secret to use based on webhook data
    try:
        webhook_data = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Try to find matching operation to determine method
    op_id = webhook_data.get("id") or webhook_data.get("payload", {}).get("id") or webhook_data.get("operation_id")
    operation = None
    secret_key = ""

    if op_id:
        operation = await db.qr_provider_operations.find_one({
            "provider_id": provider_id, "trustgain_operation_id": op_id
        }, {"_id": 0})
        if operation:
            method = operation.get("payment_method", "nspk")
            secret_key = provider.get(f"{method}_secret_key", "")

    # If no operation found, try both secrets
    if not secret_key:
        secret_key = provider.get("nspk_secret_key", "") or provider.get("transgrant_secret_key", "")

    if secret_key and sig_header:
        from services.trustgain_client import TrustGainClient
        if not TrustGainClient.verify_webhook_signature(secret_key, sig_header, body_str):
            logger.error(f"[QR Webhook] Invalid signature for provider {provider_id}")
            raise HTTPException(status_code=400, detail="Invalid signature")

    logger.info(f"[QR Webhook] Received for provider {provider_id}: event={webhook_data.get('event', 'unknown')}")

    # Store webhook
    webhook_record = {
        "id": str(uuid.uuid4()),
        "provider_id": provider_id,
        "data": webhook_data,
        "signature": sig_header,
        "processed": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.qr_provider_webhooks.insert_one(webhook_record)

    background_tasks.add_task(process_webhook, provider_id, webhook_data, webhook_record["id"])
    return {"status": "ok"}


async def process_webhook(provider_id: str, webhook_data: dict, webhook_record_id: str):
    """Process a TrustGain webhook - update operation status"""
    try:
        # New format: {id, created_at, event, payload}
        # Legacy format: {operation_id, operation_amount, operation_status, ...}
        payload = webhook_data.get("payload", webhook_data)
        operation_id = payload.get("id") or payload.get("operation_id")
        status = payload.get("status") or payload.get("operation_status", "")

        if not operation_id:
            logger.warning(f"[QR Webhook] No operation_id in webhook for provider {provider_id}")
            await db.qr_provider_webhooks.update_one(
                {"id": webhook_record_id}, {"$set": {"processed": True, "error": "no_operation_id"}}
            )
            return

        operation = await db.qr_provider_operations.find_one({
            "provider_id": provider_id, "trustgain_operation_id": operation_id
        }, {"_id": 0})

        if not operation:
            logger.warning(f"[QR Webhook] Operation not found: {operation_id}")
            await db.qr_provider_webhooks.update_one(
                {"id": webhook_record_id}, {"$set": {"processed": True, "error": "operation_not_found"}}
            )
            return

        # Map TrustGain statuses to our statuses per docs
        status_map = {
            "auto_approved": "completed",
            "manually_approved": "completed",
            "created": "pending",
            "in_progress": "processing",
            "paid": "paid",
            "expired": "expired",
            "cancelled": "cancelled",
            "rejected": "rejected",
        }

        mapped_status = status_map.get(status.lower(), status.lower())

        update_data = {
            "status": mapped_status,
            "webhook_data": webhook_data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        approved_amount = payload.get("approved_amount")
        if approved_amount and mapped_status == "completed":
            update_data["approved_amount_rub"] = float(approved_amount)
            update_data["completed_at"] = datetime.now(timezone.utc).isoformat()

        await db.qr_provider_operations.update_one(
            {"id": operation["id"]}, {"$set": update_data}
        )

        # Update active operations count
        if mapped_status in ("completed", "rejected", "expired", "cancelled"):
            await db.qr_providers.update_one(
                {"id": provider_id, "active_operations_count": {"$gt": 0}},
                {"$inc": {"active_operations_count": -1}}
            )

        # Complete trade
        if mapped_status == "completed" and operation.get("trade_id"):
            await _complete_qr_trade(operation, provider_id)

        # Cancel trade
        if mapped_status in ("rejected", "expired", "cancelled") and operation.get("trade_id"):
            await _cancel_qr_trade(operation)

        # Update provider stats
        if mapped_status == "completed":
            await db.qr_providers.update_one(
                {"id": provider_id},
                {"$inc": {"completed_operations": 1, "total_operations": 1}}
            )
        elif mapped_status in ("rejected", "expired", "cancelled"):
            await db.qr_providers.update_one(
                {"id": provider_id},
                {"$inc": {"total_operations": 1}}
            )

        await db.qr_provider_webhooks.update_one(
            {"id": webhook_record_id}, {"$set": {"processed": True}}
        )

        logger.info(f"[QR Webhook] Processed: op={operation_id}, status={mapped_status}")

    except Exception as e:
        logger.error(f"[QR Webhook] Error: {e}")
        await db.qr_provider_webhooks.update_one(
            {"id": webhook_record_id}, {"$set": {"processed": True, "error": str(e)}}
        )


async def _complete_qr_trade(operation: dict, provider_id: str):
    """
    Complete a QR aggregator trade when payment is confirmed by TrustGain.
    
    Distribution logic:
    - Exchange trade (no merchant): volume_usdt -> buyer wallet, platform_commission -> platform
    - Merchant trade: (volume - merchant_fee) -> merchant, merchant_fee -> platform, platform_commission -> platform
    
    Provider balance: unfreeze total_freeze, deduct total_freeze from balance
    """
    trade_id = operation.get("trade_id")
    if not trade_id:
        return

    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade or trade["status"] in ("completed", "cancelled"):
        return

    now = datetime.now(timezone.utc).isoformat()
    base_rate = await _get_base_rate()

    # Mark trade completed
    if trade["status"] == "pending":
        await db.trades.update_one(
            {"id": trade_id}, {"$set": {"status": "paid", "paid_at": now}}
        )

    result = await db.trades.update_one(
        {"id": trade_id, "status": {"$in": ["paid", "pending"]}},
        {"$set": {"status": "completed", "completed_at": now}}
    )
    if result.modified_count == 0:
        return

    amount_usdt = trade.get("amount_usdt", 0)
    amount_rub = operation.get("amount_rub", 0)
    platform_commission_usdt = trade.get("platform_commission_usdt", 0)
    total_freeze_usdt = trade.get("total_freeze_usdt", 0)

    # If old trade without new fields, calculate from scratch
    if total_freeze_usdt == 0 and amount_usdt > 0:
        platform_markup_pct = trade.get("platform_markup_pct", 5.0)
        platform_commission_usdt = round(amount_usdt * platform_markup_pct / 100, 6)
        total_freeze_usdt = round(amount_usdt + platform_commission_usdt, 6)

    # ---- DISTRIBUTION ----
    platform_total_usdt = platform_commission_usdt  # Platform always gets its markup commission

    if trade.get("merchant_id"):
        # MERCHANT TRADE: client pays on merchant site
        merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0})
        if merchant:
            merchant_commission_rate = merchant.get("commission_rate", 5.0)  # e.g. 5%
            original_amount_rub = amount_rub

            if trade.get("invoice_id"):
                invoice = await db.merchant_invoices.find_one({"id": trade["invoice_id"]}, {"_id": 0})
                if invoice:
                    original_amount_rub = invoice.get("original_amount_rub", amount_rub)

            # Merchant commission in USDT
            merchant_commission_usdt = round(amount_usdt * merchant_commission_rate / 100, 6)
            merchant_receives_usdt = round(amount_usdt - merchant_commission_usdt, 6)

            # Platform gets: platform_markup_commission + merchant_commission
            platform_total_usdt = round(platform_commission_usdt + merchant_commission_usdt, 6)

            await db.trades.update_one(
                {"id": trade_id},
                {"$set": {
                    "original_amount_rub": original_amount_rub,
                    "merchant_receives_usdt": merchant_receives_usdt,
                    "merchant_commission_usdt": merchant_commission_usdt,
                    "platform_receives_usdt": platform_total_usdt,
                    "qr_aggregator_trade": True,
                }}
            )

            # Credit merchant
            await db.merchants.update_one(
                {"id": trade["merchant_id"]},
                {"$inc": {"balance_usdt": merchant_receives_usdt}}
            )

            logger.info(f"[QR Trade] Merchant {trade['merchant_id']} credited {merchant_receives_usdt:.4f} USDT "
                       f"(volume={amount_usdt}, merchant_fee={merchant_commission_usdt})")
    else:
        # EXCHANGE TRADE: user buys in order book
        # Buyer gets amount_usdt credited to their wallet
        buyer_id = trade.get("buyer_id")
        if buyer_id:
            # Credit buyer's USDT balance
            buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0})
            if not buyer:
                buyer = await db.traders.find_one({"id": buyer_id}, {"_id": 0})

            if buyer:
                # Credit via traders collection (main balance)
                await db.traders.update_one(
                    {"id": buyer_id},
                    {"$inc": {"balance_usdt": amount_usdt}}
                )
                logger.info(f"[QR Trade] Buyer {buyer_id} credited {amount_usdt:.4f} USDT")

        await db.trades.update_one(
            {"id": trade_id},
            {"$set": {
                "platform_receives_usdt": platform_total_usdt,
                "buyer_receives_usdt": amount_usdt,
                "qr_aggregator_trade": True,
            }}
        )

    # ---- PROVIDER BALANCE: unfreeze + deduct ----
    # Atomic: unfreeze and deduct from balance, prevent negative values
    result = await db.qr_providers.update_one(
        {"id": provider_id, "frozen_usdt": {"$gte": total_freeze_usdt}, "balance_usdt": {"$gte": total_freeze_usdt}},
        {"$inc": {
            "frozen_usdt": -total_freeze_usdt,
            "balance_usdt": -total_freeze_usdt,
            "active_operations_count": -1,
        }}
    )
    if result.modified_count == 0:
        # Fallback: force correct values (never go negative)
        provider_now = await db.qr_providers.find_one({"id": provider_id})
        if provider_now:
            new_frozen = max(0, provider_now.get("frozen_usdt", 0) - total_freeze_usdt)
            new_balance = max(0, provider_now.get("balance_usdt", 0) - total_freeze_usdt)
            new_active = max(0, provider_now.get("active_operations_count", 0) - 1)
            await db.qr_providers.update_one(
                {"id": provider_id},
                {"$set": {"frozen_usdt": new_frozen, "balance_usdt": new_balance, "active_operations_count": new_active}}
            )
        logger.warning(f"[QR Trade] Balance correction for provider {provider_id} on complete (trade {trade_id})")
    else:
        logger.info(f"[QR Trade] Provider {provider_id}: unfrozen and deducted {total_freeze_usdt:.4f} USDT")

    # ---- PLATFORM BALANCE: credit platform earnings ----
    await db.settings.update_one(
        {"type": "platform_balance"},
        {"$inc": {"balance_usdt": platform_total_usdt}},
        upsert=True
    )
    logger.info(f"[QR Trade] Platform credited {platform_total_usdt:.4f} USDT")

    # Update invoice / payment link
    if trade.get("invoice_id"):
        await db.merchant_invoices.update_one(
            {"id": trade["invoice_id"]}, {"$set": {"status": "completed", "completed_at": now}}
        )
    if trade.get("payment_link_id"):
        await db.payment_links.update_one(
            {"id": trade["payment_link_id"]}, {"$set": {"status": "completed"}}
        )

    # Record provider operation details
    method = operation.get("payment_method", "nspk")
    await db.qr_provider_operations.update_one(
        {"id": operation["id"]},
        {"$set": {
            "platform_commission_usdt": platform_commission_usdt,
            "total_freeze_usdt": total_freeze_usdt,
            "platform_total_usdt": platform_total_usdt,
            "distribution_completed": True,
        }}
    )

    # System message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "sender_role": "system",
        "content": "Оплата подтверждена (QR). Сделка завершена автоматически.",
        "created_at": now
    }
    await db.trade_messages.insert_one(system_msg)

    # Send merchant webhook
    try:
        from routes.trades import send_merchant_webhook_on_trade
        # Re-read trade to get merchant_receives_usdt calculated above
        updated_trade = await db.trades.find_one({"id": trade_id}, {"_id": 0}) or trade
        await send_merchant_webhook_on_trade(updated_trade, "completed", {
            "trade_id": trade_id,
            "completed_at": now,
            "qr_aggregator": True,
            "rate": base_rate,
            "merchant_amount_usdt": updated_trade.get("merchant_receives_usdt"),
            "merchant_receives_rub": round(updated_trade.get("merchant_receives_usdt", 0) * base_rate, 2) if updated_trade.get("merchant_receives_usdt") else None,
        })
    except Exception as e:
        logger.error(f"[QR Trade] Webhook send error: {e}")

    logger.info(f"[QR Trade] Trade {trade_id} completed via QR Aggregator ({method})")


async def _cancel_qr_trade(operation: dict):
    """Cancel a QR aggregator trade and UNFREEZE provider funds"""
    trade_id = operation.get("trade_id")
    if not trade_id:
        return

    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade or trade["status"] in ("completed", "cancelled"):
        return

    now = datetime.now(timezone.utc).isoformat()
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {"status": "cancelled", "cancelled_at": now, "cancel_reason": "qr_payment_failed"}}
    )

    # UNFREEZE provider funds - balance stays the same, only frozen decreases
    # Use atomic operation to prevent frozen going negative
    provider_id = trade.get("provider_id")
    total_freeze_usdt = trade.get("total_freeze_usdt", 0)
    if provider_id and total_freeze_usdt > 0:
        # Atomic: only decrement if frozen >= total_freeze_usdt
        result = await db.qr_providers.update_one(
            {"id": provider_id, "frozen_usdt": {"$gte": total_freeze_usdt}},
            {"$inc": {"frozen_usdt": -total_freeze_usdt, "active_operations_count": -1}}
        )
        if result.modified_count == 0:
            # Frozen already released or insufficient - force set to max(0, frozen - freeze)
            provider = await db.qr_providers.find_one({"id": provider_id})
            if provider:
                new_frozen = max(0, provider.get("frozen_usdt", 0) - total_freeze_usdt)
                new_active = max(0, provider.get("active_operations_count", 0) - 1)
                await db.qr_providers.update_one(
                    {"id": provider_id},
                    {"$set": {"frozen_usdt": new_frozen, "active_operations_count": new_active}}
                )
            logger.warning(f"[QR Trade] Frozen correction for provider {provider_id} on cancel (trade {trade.get('id')})")
        else:
            logger.info(f"[QR Trade] Unfrozen {total_freeze_usdt:.4f} USDT for provider {provider_id} (trade cancelled)")

    if trade.get("invoice_id"):
        await db.merchant_invoices.update_one(
            {"id": trade["invoice_id"]}, {"$set": {"status": "cancelled"}}
        )

    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "sender_role": "system",
        "content": "QR-оплата не прошла. Сделка отменена.",
        "created_at": now
    }
    await db.trade_messages.insert_one(system_msg)
    logger.info(f"[QR Trade] Trade {trade_id} cancelled")



# ==================== QR Aggregator Dispute System ====================

class QRDisputeRequest(BaseModel):
    reason: str = Field(default="", max_length=500)

@router.post("/qr-aggregator/trades/{trade_id}/dispute")
async def open_qr_dispute(trade_id: str, data: QRDisputeRequest = Body(...), user: dict = Depends(get_current_user)):
    """Open dispute on QR aggregator trade (authenticated user)"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if not trade.get("is_qr_aggregator"):
        raise HTTPException(status_code=400, detail="Not a QR aggregator trade")
    if trade["status"] == "disputed":
        raise HTTPException(status_code=400, detail="Already disputed")
    if trade["status"] in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail="Trade already finished")

    user_id = user["id"]
    user_role = user.get("role", "")
    valid_ids = [trade.get("trader_id"), trade.get("buyer_id"), trade.get("merchant_id"), trade.get("provider_id")]
    valid_ids = [x for x in valid_ids if x]
    is_admin = user.get("admin_role") in ("admin", "owner", "mod_p2p")
    if user_id not in valid_ids and not is_admin:
        raise HTTPException(status_code=403, detail="Not a participant")

    if user_id == trade.get("provider_id") or user_role == "qr_provider":
        opener = "QR provider"
    elif user_id == trade.get("merchant_id") or user_role == "merchant":
        opener = "merchant"
    elif is_admin:
        opener = "admin"
    else:
        opener = "buyer"

    reason = data.reason or "Payment issue"
    now = datetime.now(timezone.utc).isoformat()

    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "disputed", "disputed_at": now,
            "dispute_reason": reason, "disputed_by": user_id,
            "disputed_by_role": opener, "has_dispute": True,
            "is_qr_aggregator_dispute": True,
        }}
    )
    conv = await _create_qr_dispute_conversation(trade, reason, opener, user_id)

    system_msg = {
        "id": str(uuid.uuid4()), "trade_id": trade_id,
        "sender_id": "system", "sender_type": "system",
        "is_system": True, "sender_role": "system",
        "content": f"Dispute opened by {opener}. Reason: {reason}. Admin will join.",
        "created_at": now
    }
    await db.trade_messages.insert_one(system_msg)
    logger.info(f"[QR Dispute] Trade {trade_id} disputed by {opener} ({user_id}): {reason}")
    return {"status": "dispute_opened", "conversation_id": conv["id"], "trade_id": trade_id}


@router.post("/qr-aggregator/trades/{trade_id}/dispute-public")
async def open_qr_dispute_public(trade_id: str, data: QRDisputeRequest = Body(...)):
    """Open dispute on QR trade without auth (client clicks Payment Failed)"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if not trade.get("is_qr_aggregator"):
        raise HTTPException(status_code=400, detail="Not a QR aggregator trade")
    if trade["status"] == "disputed":
        return {"status": "already_disputed", "message": "Already disputed"}
    if trade["status"] in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail="Trade already finished")

    reason = data.reason or "Payment failed"
    opener = "client"
    now = datetime.now(timezone.utc).isoformat()

    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "disputed", "disputed_at": now,
            "dispute_reason": reason, "disputed_by": "client",
            "disputed_by_role": opener, "has_dispute": True,
            "is_qr_aggregator_dispute": True,
        }}
    )
    conv = await _create_qr_dispute_conversation(trade, reason, opener, "client")

    system_msg = {
        "id": str(uuid.uuid4()), "trade_id": trade_id,
        "sender_id": "system", "sender_type": "system",
        "is_system": True, "sender_role": "system",
        "content": f"Dispute opened by client. Reason: {reason}. Admin will join.",
        "created_at": now
    }
    await db.trade_messages.insert_one(system_msg)

    try:
        from routes.trades import send_merchant_webhook_on_trade
        await send_merchant_webhook_on_trade(trade, "disputed", {
            "trade_id": trade_id, "reason": reason,
            "disputed_at": now, "disputed_by": opener, "is_qr_aggregator": True,
        })
    except Exception as e:
        logger.error(f"[QR Dispute] Webhook error: {e}")

    logger.info(f"[QR Dispute] Trade {trade_id} disputed publicly (client): {reason}")
    return {"status": "dispute_opened", "conversation_id": conv["id"], "trade_id": trade_id}


async def _create_qr_dispute_conversation(trade: dict, reason: str, opener: str, opened_by: str) -> dict:
    """Create or reuse unified conversation for QR aggregator dispute"""
    trade_id = trade["id"]
    now = datetime.now(timezone.utc).isoformat()

    existing = await db.unified_conversations.find_one(
        {"related_id": trade_id, "type": {"$in": ["p2p_dispute", "p2p_trade", "p2p_merchant"]}},
        {"_id": 0}
    )

    participants = []
    unread = {}

    provider_id = trade.get("provider_id")
    if provider_id:
        provider = await db.qr_providers.find_one({"id": provider_id}, {"_id": 0})
        pname = provider.get("login", provider.get("name", "QR Provider")) if provider else "QR Provider"
        participants.append({"user_id": provider_id, "role": "qr_provider", "name": pname})
        unread[provider_id] = 0

    merchant_id = trade.get("merchant_id")
    if merchant_id:
        merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
        mname = merchant.get("company_name", merchant.get("login", "Merchant")) if merchant else "Merchant"
        participants.append({"user_id": merchant_id, "role": "merchant", "name": mname})
        unread[merchant_id] = 0

    buyer_id = trade.get("buyer_id") or trade.get("client_id")
    if buyer_id and buyer_id != merchant_id:
        buyer = await db.traders.find_one({"id": buyer_id}, {"_id": 0})
        bname = buyer.get("nickname", buyer.get("login", "Buyer")) if buyer else "Buyer"
        participants.append({"user_id": buyer_id, "role": "p2p_buyer", "name": bname})
        unread[buyer_id] = 0

    trader_id = trade.get("trader_id")
    if trader_id and trader_id != "qr_aggregator":
        trader = await db.traders.find_one({"id": trader_id}, {"_id": 0})
        if trader:
            tname = trader.get("nickname", trader.get("login", "Trader"))
            participants.append({"user_id": trader_id, "role": "p2p_seller", "name": tname})
            unread[trader_id] = 0

    moderator = await db.admins.find_one({"admin_role": "mod_p2p", "is_active": True}, {"_id": 0})
    if not moderator:
        moderator = await db.admins.find_one({"admin_role": {"$in": ["admin", "owner"]}}, {"_id": 0})

    if moderator:
        mod_id = moderator["id"]
        mod_name = moderator.get("login", "Moderator")
        participants.append({"user_id": mod_id, "role": "mod_p2p", "name": mod_name, "joined_at": now})
        unread[mod_id] = 0

    amount_usdt = trade.get("amount_usdt", 0)
    title = f"QR Dispute: {amount_usdt:.4f} USDT"

    if existing:
        await db.unified_conversations.update_one(
            {"id": existing["id"]},
            {"$set": {
                "type": "p2p_dispute", "status": "dispute",
                "delete_locked": True, "participants": participants,
                "unread_counts": unread, "dispute_reason": reason,
                "dispute_opened_by": opened_by, "dispute_opened_at": now,
                "is_qr_aggregator_dispute": True, "updated_at": now,
                "title": title,
            }}
        )
        conv = existing
    else:
        conv_id = str(uuid.uuid4())
        conv = {
            "id": conv_id, "type": "p2p_dispute",
            "related_id": trade_id, "title": title,
            "status": "dispute", "delete_locked": True,
            "participants": participants, "unread_counts": unread,
            "dispute_reason": reason, "dispute_opened_by": opened_by,
            "dispute_opened_at": now, "is_qr_aggregator_dispute": True,
            "created_at": now, "updated_at": now,
        }
        await db.unified_conversations.insert_one(conv)

    msgs = [
        {
            "id": str(uuid.uuid4()), "conversation_id": conv["id"],
            "sender_id": "system", "sender_role": "system",
            "sender_name": "System",
            "content": f"QR Aggregator dispute opened by {opener}. Reason: {reason}",
            "is_system": True, "is_deleted": False, "created_at": now
        },
        {
            "id": str(uuid.uuid4()), "conversation_id": conv["id"],
            "sender_id": "system", "sender_role": "system",
            "sender_name": "System",
            "content": "P2P Moderator joined. QR Aggregator Dispute.",
            "is_system": True, "is_deleted": False, "created_at": now
        }
    ]
    await db.unified_messages.insert_many(msgs)
    return conv


@router.get("/qr-aggregator/provider/disputes")
async def get_provider_disputes(user: dict = Depends(get_current_user)):
    """Get list of disputes for QR provider"""
    if user.get("role") != "qr_provider":
        raise HTTPException(status_code=403, detail="QR provider only")

    provider_id = user["id"]
    trades = await db.trades.find(
        {"provider_id": provider_id, "is_qr_aggregator": True,
         "$or": [{"status": "disputed"}, {"has_dispute": True}]},
        {"_id": 0}
    ).sort("disputed_at", -1).to_list(100)

    disputes = []
    for trade in trades:
        tid = trade["id"]
        conv = await db.unified_conversations.find_one(
            {"related_id": tid, "type": "p2p_dispute"},
            {"_id": 0, "id": 1, "unread_counts": 1, "status": 1, "updated_at": 1}
        )
        unread = conv.get("unread_counts", {}).get(provider_id, 0) if conv else 0
        conv_status = conv.get("status", "dispute") if conv else "dispute"

        merchant_name = "Unknown"
        if trade.get("merchant_id"):
            m = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0, "company_name": 1, "login": 1})
            if m:
                merchant_name = m.get("company_name", m.get("login", "Merchant"))

        disputes.append({
            "trade_id": tid, "conversation_id": conv["id"] if conv else None,
            "merchant_name": merchant_name, "merchant_id": trade.get("merchant_id"),
            "provider_id": provider_id,
            "amount_usdt": trade.get("amount_usdt", 0),
            "amount_rub": trade.get("amount_rub", 0),
            "status": trade.get("status"),
            "dispute_reason": trade.get("dispute_reason", ""),
            "disputed_at": trade.get("disputed_at"),
            "disputed_by_role": trade.get("disputed_by_role", ""),
            "dispute_resolved": trade.get("dispute_resolved", False),
            "dispute_resolution": trade.get("dispute_resolution"),
            "unread_count": unread, "conv_status": conv_status,
            "created_at": trade.get("created_at"),
        })

    return {"disputes": disputes, "total": len(disputes)}


@router.get("/qr-aggregator/admin/disputes")
async def get_qr_disputes_admin(
    provider_id: str = None,
    user: dict = Depends(require_admin_level(50))
):
    """Admin: Get all QR aggregator disputes"""
    query = {"is_qr_aggregator": True,
             "$or": [{"status": "disputed"}, {"has_dispute": True}]}
    if provider_id:
        query["provider_id"] = provider_id

    trades = await db.trades.find(query, {"_id": 0}).sort("disputed_at", -1).to_list(200)

    disputes = []
    for trade in trades:
        tid = trade["id"]
        conv = await db.unified_conversations.find_one(
            {"related_id": tid, "type": "p2p_dispute"},
            {"_id": 0, "id": 1, "status": 1, "updated_at": 1}
        )

        provider_name = "Unknown"
        if trade.get("provider_id"):
            p = await db.qr_providers.find_one({"id": trade["provider_id"]}, {"_id": 0, "login": 1, "name": 1})
            if p:
                provider_name = p.get("login", p.get("name", "Provider"))

        merchant_name = "Unknown"
        if trade.get("merchant_id"):
            m = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0, "company_name": 1, "login": 1})
            if m:
                merchant_name = m.get("company_name", m.get("login", "Merchant"))

        disputes.append({
            "trade_id": tid, "conversation_id": conv["id"] if conv else None,
            "provider_name": provider_name, "provider_id": trade.get("provider_id"),
            "merchant_name": merchant_name, "merchant_id": trade.get("merchant_id"),
            "amount_usdt": trade.get("amount_usdt", 0),
            "amount_rub": trade.get("amount_rub", 0),
            "status": trade.get("status"),
            "dispute_reason": trade.get("dispute_reason", ""),
            "disputed_at": trade.get("disputed_at"),
            "disputed_by_role": trade.get("disputed_by_role", ""),
            "dispute_resolved": trade.get("dispute_resolved", False),
            "dispute_resolution": trade.get("dispute_resolution"),
            "is_qr_aggregator_dispute": True,
            "conv_status": conv.get("status") if conv else None,
            "created_at": trade.get("created_at"),
        })

    return {"disputes": disputes, "total": len(disputes)}

# ==================== Order Book (Stakan) Integration ====================

@router.get("/public/qr-offers")
async def get_qr_aggregator_offers():
    """Get QR Aggregator offers for the public order book"""
    settings = await db.qr_aggregator_settings.find_one({"type": "main"}, {"_id": 0})
    if not settings or not settings.get("is_enabled", True):
        return {"offers": []}

    base_rate = await _get_base_rate()
    offers = []

    # Get active providers with balance
    providers = await db.qr_providers.find(
        {"is_active": True, "balance_usdt": {"$gt": 0}}, {"_id": 0}
    ).to_list(100)

    if not providers:
        return {"offers": []}

    for method_key, label, method_name, offer_type in [
        ("nspk", "СБП (QR-код)", "sbp_qr", "sbp"),
        ("transgrant", "Банковская карта", "bank_card", "card"),
    ]:
        enabled_providers = [p for p in providers if p.get(f"{method_key}_enabled", False)]
        if not enabled_providers:
            continue

        total_balance_usdt = sum(p.get("balance_usdt", 0) - p.get("frozen_usdt", 0) for p in enabled_providers)
        if total_balance_usdt <= 0:
            continue

        # Provider markup (from provider settings)
        provider_markups = [p.get(f"{method_key}_commission_percent", 5.0) for p in enabled_providers]
        best_provider_markup = min(provider_markups)

        # Platform markup (from QR aggregator settings)
        platform_markup = settings.get(f"{method_key}_commission_percent", 5.0)

        # Two-level pricing: base * (1 + provider%) * (1 + platform%)
        provider_rate = base_rate * (1 + best_provider_markup / 100)
        price = provider_rate * (1 + platform_markup / 100)
        min_amount = settings.get(f"{method_key}_min_amount", 100)
        max_amount = settings.get(f"{method_key}_max_amount", 500000)

        total_rub = total_balance_usdt * base_rate
        effective_max = min(max_amount, total_rub)

        if effective_max < min_amount:
            continue

        avg_success = sum(p.get("success_rate", 100) for p in enabled_providers) / len(enabled_providers)

        offers.append({
            "id": f"qr_aggregator_{method_key}",
            "trader_id": "qr_aggregator",
        "trader_login": provider.get("display_name", provider.get("login", "QR Оператор")),
            "trader_login": label,
            "trader_display_name": label,
            "type": "sell",
            "payment_methods": [method_name],
            "price_rub": round(price, 2),
            "min_amount": round(min_amount / price, 2),
            "max_amount": round(effective_max / price, 2),
            "available_usdt": round(total_balance_usdt, 2),
            "is_active": True,
            "is_online": True,
            "is_qr_aggregator": True,
            "qr_method": method_key,
            "offer_type": offer_type,  # "sbp" or "card"
            "provider_markup_percent": best_provider_markup,
            "platform_markup_percent": platform_markup,
            "commission_percent": round(((1 + best_provider_markup/100) * (1 + platform_markup/100) - 1) * 100, 2),
            "provider_count": len(enabled_providers),
            "success_rate": round(avg_success, 1),
            "trades_count": 0,
            "requisites": [],
            "payment_details": [],
            "requisite_ids": [],
            "payment_detail_ids": [],
            "conditions": f"Оплата через {'приложение банка по QR-коду' if offer_type == 'sbp' else 'банковскую карту (Visa/MC/МИР)'}. Быстрое зачисление.",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {"offers": offers}




# ==================== QR Aggregator Buy (Direct Purchase) ====================

class QRAggregatorBuyRequest(BaseModel):
    amount_usdt: float = Field(..., gt=0)
    qr_method: str = Field(default="qr")  # "qr" or "sng"
    payment_link_id: Optional[str] = None
    method: Optional[str] = None  # alias for qr_method from frontend

class QRAggregatorBuyPublicRequest(BaseModel):
    amount_usdt: float = Field(..., gt=0)
    method: str = Field(default="qr")
    payment_link_id: Optional[str] = None

@router.post("/qr-aggregator/buy-public")
async def qr_aggregator_buy_public(data: QRAggregatorBuyPublicRequest, background_tasks: BackgroundTasks):
    """
    Public endpoint for QR aggregator purchases from merchant payment pages.
    No authentication required - creates trade for anonymous client.
    """
    # Map method aliases
    method_aliases = {"nspk": "qr", "transgrant": "sng", "qr": "qr", "sng": "sng", "sbp": "qr", "card": "sng"}
    method = method_aliases.get(data.method, data.method)
    if method not in ("qr", "sng"):
        raise HTTPException(status_code=400, detail="Invalid method")

    payment_method_map = {"qr": "nspk", "sng": "transgrant"}
    tg_payment_method = payment_method_map[method]

    base_rate = await _get_base_rate()
    qr_settings = await db.qr_aggregator_settings.find_one({"type": "main"}, {"_id": 0})
    if not qr_settings or not qr_settings.get("is_enabled", True):
        raise HTTPException(status_code=503, detail="QR Агрегатор отключён")

    providers_for_method = await db.qr_providers.find({
        "is_active": True, f"{tg_payment_method}_enabled": True, "balance_usdt": {"$gt": 0},
    }, {"_id": 0}).to_list(100)
    if not providers_for_method:
        raise HTTPException(status_code=503, detail="Нет доступных провайдеров")

    provider_markups = [p.get(f"{tg_payment_method}_commission_percent", 5.0) for p in providers_for_method]
    provider_markup_pct = min(provider_markups)
    platform_markup_pct = qr_settings.get(f"{tg_payment_method}_commission_percent", 5.0)

    provider_rate = base_rate * (1 + provider_markup_pct / 100)
    qr_price = round(provider_rate * (1 + platform_markup_pct / 100), 2)

    # If payment_link_id is provided, calculate amount_rub WITH markup
    # Frontend formula: toPayRub = Math.round((deposit / exchangeRate) * op.price_rub)
    # Where deposit = inv.original_amount_rub || inv.amount_rub
    # IMPORTANT: use original_amount_rub (without marker), not amount_rub (with marker)
    invoice_deposit_rub = None
    if data.payment_link_id:
        # Check both collections (merchant_invoices for Invoice API, payment_links for legacy)
        invoice_doc = await db.merchant_invoices.find_one({"id": data.payment_link_id}, {"_id": 0})
        if not invoice_doc:
            invoice_doc = await db.payment_links.find_one({"id": data.payment_link_id}, {"_id": 0})
        if invoice_doc:
            # Use original_amount_rub (merchant's requested amount, without marker)
            # Fallback to amount_rub if original_amount_rub not set
            invoice_deposit_rub = float(invoice_doc.get("original_amount_rub") or invoice_doc.get("amount_rub") or 0)

    if invoice_deposit_rub and invoice_deposit_rub > 0:
        # Calculate markup amount same as frontend: (deposit / base_rate) * qr_price
        amount_rub = round(invoice_deposit_rub / base_rate * qr_price, 2)
        amount_usdt = round(amount_rub / qr_price, 6)
        logger.info(f"[QR Buy Public] Invoice {data.payment_link_id}: deposit_rub={invoice_deposit_rub}, markup_rub={amount_rub}, usdt={amount_usdt}, qr_price={qr_price}, base_rate={base_rate}")
    else:
        # No invoice - use USDT amount as-is
        amount_usdt = data.amount_usdt
        amount_rub = round(amount_usdt * qr_price, 2)

    platform_commission_usdt = round(amount_usdt * platform_markup_pct / 100, 6)
    total_freeze_usdt = round(amount_usdt + platform_commission_usdt, 6)

    min_amount_rub = qr_settings.get(f"{tg_payment_method}_min_amount", 100)
    total_available_usdt = sum(p.get("balance_usdt", 0) - p.get("frozen_usdt", 0) for p in providers_for_method)
    max_amount_usdt = round(total_available_usdt / (1 + platform_markup_pct / 100), 2) if total_available_usdt > 0 else 0

    if amount_usdt > max_amount_usdt:
        raise HTTPException(status_code=400, detail=f"Максимум: {max_amount_usdt} USDT")
    if amount_rub < min_amount_rub:
        raise HTTPException(status_code=400, detail=f"Минимальная сумма: {min_amount_rub} ₽")

    eligible = [p for p in providers_for_method
        if (p.get("balance_usdt", 0) - p.get("frozen_usdt", 0)) >= total_freeze_usdt
        and p.get("active_operations_count", 0) < p.get("max_concurrent_operations", 10)]
    if not eligible:
        raise HTTPException(status_code=503, detail="Нет доступных провайдеров для данной суммы")

    import random
    weights = [p.get("weight", 100) for p in eligible]
    provider = random.choices(eligible, weights=weights, k=1)[0]

    # Resolve merchant from payment_link
    merchant_id_from_link = None
    invoice_id_from_link = None
    merchant_commission = 0.0
    buyer_id = "anonymous_client"
    # Generate a unique client_id for TrustGain (staging cancels "anonymous_client")
    tg_client_id = str(uuid.uuid4())
    if data.payment_link_id:
        link = await db.payment_links.find_one({"id": data.payment_link_id}, {"_id": 0})
        if link:
            merchant_id_from_link = link.get("merchant_id")
            invoice_id_from_link = data.payment_link_id
            if merchant_id_from_link:
                merchant = await db.merchants.find_one({"id": merchant_id_from_link}, {"_id": 0})
                if merchant:
                    merchant_commission = round(amount_usdt * merchant.get("commission_rate", 5.0) / 100, 6)

    trade_id = f"trd_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    trade_doc = {
        "id": trade_id,
        "offer_id": f"qr_aggregator_{method}",
        "trader_id": "qr_aggregator",
        "buyer_id": buyer_id,
        "buyer_type": "client",
        "amount_usdt": amount_usdt,
        "amount_rub": amount_rub,
        "price_rub": qr_price,
        "base_rate": base_rate,
        "provider_rate": provider_rate,
        "provider_markup_pct": provider_markup_pct,
        "platform_markup_pct": platform_markup_pct,
        "platform_commission_usdt": platform_commission_usdt,
        "total_freeze_usdt": total_freeze_usdt,
        "requisite": {"type": "qr_aggregator", "value": "auto", "name": "СБП (QR-код)" if method == "qr" else "Банковская карта"},
        "requisites": [],
        "merchant_id": merchant_id_from_link,
        "payment_link_id": data.payment_link_id,
        "invoice_id": invoice_id_from_link,
        "trader_commission": platform_commission_usdt,
        "merchant_commission": merchant_commission,
        "total_commission": platform_commission_usdt,
        "status": "pending",
        "qr_aggregator_trade": True,
        "qr_method": method,
        "provider_id": provider["id"],
        "created_at": now,
        "expires_at": expires_at,
    }
    await db.trades.insert_one(trade_doc)

    # FREEZE
    freeze_result = await db.qr_providers.update_one(
        {"id": provider["id"], "$expr": {"$gte": [{"$subtract": ["$balance_usdt", "$frozen_usdt"]}, total_freeze_usdt]}},
        {"$inc": {"frozen_usdt": total_freeze_usdt}}
    )
    if freeze_result.modified_count == 0:
        await db.trades.delete_one({"id": trade_id})
        raise HTTPException(status_code=503, detail="Не удалось заморозить средства провайдера")

    logger.info(f"[QR Buy Public] Frozen {total_freeze_usdt:.2f} USDT from provider {provider['id']}")

    # Create TrustGain operation
    from services.trustgain_client import TrustGainClient

    api_key = provider.get(f"{tg_payment_method}_api_key", "")
    secret_key = provider.get(f"{tg_payment_method}_secret_key", "")
    api_url = provider.get(f"{tg_payment_method}_api_url", "https://api.trustgain.io")
    merchant_id_tg = provider.get(f"{tg_payment_method}_merchant_id", "")
    gateway_id = provider.get(f"{tg_payment_method}_gateway_id", "")

    if not api_key or not merchant_id_tg or not gateway_id:
        await db.qr_providers.update_one({"id": provider["id"]}, {"$inc": {"frozen_usdt": -total_freeze_usdt}})
        await db.trades.delete_one({"id": trade_id})
        raise HTTPException(status_code=503, detail="Провайдер не настроен")

    client = TrustGainClient(api_url=api_url, api_key=api_key, secret_key=secret_key)
    backend_url = os.environ.get("BACKEND_URL", "https://reptiloid.vg")
    webhook_url = f"{backend_url}/api/qr-aggregator/webhook/{provider['id']}"
    idempotency_key = str(uuid.uuid4())

    try:
        result = await client.create_income_operation(
            amount=str(amount_rub),
            merchant_id=merchant_id_tg,
            gateway_id=gateway_id,
            client_id=tg_client_id,
            client_ip="127.0.0.1",
            idempotency_key=idempotency_key,
            webhook_url=webhook_url,
        )
    except Exception as e:
        await db.qr_providers.update_one({"id": provider["id"]}, {"$inc": {"frozen_usdt": -total_freeze_usdt}})
        await db.trades.delete_one({"id": trade_id})
        logger.error(f"[QR Buy Public] TrustGain API error: {e}")
        raise HTTPException(status_code=502, detail=f"Ошибка API провайдера: {str(e)}")
    finally:
        await client.close()

    if not result.get("success"):
        await db.qr_providers.update_one({"id": provider["id"]}, {"$inc": {"frozen_usdt": -total_freeze_usdt}})
        await db.trades.delete_one({"id": trade_id})
        logger.error(f"[QR Buy Public] Failed: {result}")
        raise HTTPException(status_code=502, detail=f"Ошибка: {result.get('error', 'unknown')}")

    operation_data = result.get("data", {})
    trustgain_operation_id = operation_data.get("id", "")
    payment_url = operation_data.get("url", "")

    op_id = str(uuid.uuid4())
    op_doc = {
        "id": op_id,
        "provider_id": provider["id"],
        "trade_id": trade_id,
        "invoice_id": invoice_id_from_link,
        "trustgain_operation_id": trustgain_operation_id,
        "idempotency_key": idempotency_key,
        "amount_rub": amount_rub,
        "payment_method": tg_payment_method,
        "status": "pending",
        "gateway_id": gateway_id,
        "merchant_id": merchant_id_tg,
        "trustgain_data": operation_data,
        "provider_earning_usdt": 0,
        "provider_earning_rub": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.qr_provider_operations.insert_one(op_doc)
    await db.qr_providers.update_one({"id": provider["id"]}, {"$inc": {"active_operations_count": 1}})

    payment_requisite = operation_data.get("payment_requisite", {})
    await db.trades.update_one({"id": trade_id}, {"$set": {
        "qr_operation_id": op_id,
        "trustgain_operation_id": trustgain_operation_id,
        "payment_url": payment_url,
        "payment_requisite": payment_requisite,
    }})

    logger.info(f"[QR Buy Public] Trade {trade_id} created, method={method}, amount={data.amount_usdt} USDT, payment_link={data.payment_link_id}")

    return {
        "id": trade_id,
        "trade_id": trade_id,
        "amount_usdt": amount_usdt,
        "amount_rub": amount_rub,
        "price_rub": qr_price,
        "payment_url": payment_url,
        "payment_requisite": payment_requisite,
        "qr_method": method,
        "status": "pending",
        "expires_at": expires_at,
    }


@router.post("/qr-aggregator/buy")
async def qr_aggregator_buy(data: QRAggregatorBuyRequest, background_tasks: BackgroundTasks, user: dict = Depends(require_role(["trader"]))):
    """
    Direct purchase through QR/SNG aggregator.
    Creates a trade + TrustGain operation in one step.
    No payment method selection needed - each aggregator has exactly one method.
    """
    # Accept both qr_method and method (frontend alias), map various formats
    raw_method = data.method or data.qr_method
    method_aliases = {"nspk": "qr", "transgrant": "sng", "qr": "qr", "sng": "sng", "sbp": "qr", "card": "sng"}
    method = method_aliases.get(raw_method, raw_method)
    if method not in ("qr", "sng"):
        raise HTTPException(status_code=400, detail="Invalid method. Use 'qr', 'sng', 'nspk' or 'transgrant'")

    payment_method_map = {"qr": "nspk", "sng": "transgrant"}
    tg_payment_method = payment_method_map[method]

    # Get base rate
    base_rate = await _get_base_rate()
    
    # Get QR aggregator settings for markup
    qr_settings = await db.qr_aggregator_settings.find_one({"type": "main"}, {"_id": 0})
    if not qr_settings or not qr_settings.get("is_enabled", True):
        raise HTTPException(status_code=503, detail="QR Агрегатор отключён")

    # Two-level markup pricing
    # Step 1: Get provider markup
    providers_for_method = await db.qr_providers.find({
        "is_active": True,
        f"{tg_payment_method}_enabled": True,
        "balance_usdt": {"$gt": 0},
    }, {"_id": 0}).to_list(100)

    if not providers_for_method:
        raise HTTPException(status_code=503, detail="Нет доступных провайдеров")

    # Best (lowest) provider markup
    provider_markups = [p.get(f"{tg_payment_method}_commission_percent", 5.0) for p in providers_for_method]
    provider_markup_pct = min(provider_markups)

    # Step 2: Get platform markup from QR aggregator settings
    platform_markup_pct = qr_settings.get(f"{tg_payment_method}_commission_percent", 5.0)

    # Step 3: Two-level price calculation
    provider_rate = base_rate * (1 + provider_markup_pct / 100)
    qr_price = round(provider_rate * (1 + platform_markup_pct / 100), 2)
    amount_usdt = data.amount_usdt
    amount_rub = round(amount_usdt * qr_price, 2)

    # Step 4: Calculate platform commission in USDT
    # Platform gets: amount_usdt * platform_markup_pct / 100
    platform_commission_usdt = round(data.amount_usdt * platform_markup_pct / 100, 6)
    # Total to freeze from provider: volume + platform commission
    total_freeze_usdt = round(data.amount_usdt + platform_commission_usdt, 6)

    # Check limits
    min_amount_rub = qr_settings.get(f"{tg_payment_method}_min_amount", 100)
    max_amount_rub = qr_settings.get(f"{tg_payment_method}_max_amount", 500000)

    total_available_usdt = sum(
        p.get("balance_usdt", 0) - p.get("frozen_usdt", 0)
        for p in providers_for_method
    )
    max_amount_usdt = round(total_available_usdt / (1 + platform_markup_pct / 100), 2) if total_available_usdt > 0 else 0

    if data.amount_usdt > max_amount_usdt:
        raise HTTPException(status_code=400, detail=f"Максимум: {max_amount_usdt} USDT")
    if amount_rub < min_amount_rub:
        raise HTTPException(status_code=400, detail=f"Минимальная сумма: {min_amount_rub} ₽")

    # Select best provider (must have enough balance for volume + platform commission)
    eligible = []
    for p in providers_for_method:
        available_usdt = p.get("balance_usdt", 0) - p.get("frozen_usdt", 0)
        if available_usdt >= total_freeze_usdt:
            if p.get("active_operations_count", 0) < p.get("max_concurrent_operations", 10):
                eligible.append(p)

    if not eligible:
        raise HTTPException(status_code=503, detail="Нет доступных провайдеров для данной суммы")

    import random
    weights = [p.get("weight", 100) for p in eligible]
    provider = random.choices(eligible, weights=weights, k=1)[0]

    # Resolve merchant info from payment_link_id if present
    merchant_id_from_link = None
    invoice_id_from_link = None
    merchant_commission = 0.0
    if data.payment_link_id:
        link = await db.payment_links.find_one({"id": data.payment_link_id}, {"_id": 0})
        if link:
            merchant_id_from_link = link.get("merchant_id")
            invoice_id_from_link = data.payment_link_id
            if merchant_id_from_link:
                merchant = await db.merchants.find_one({"id": merchant_id_from_link}, {"_id": 0})
                if merchant:
                    merchant_commission = round(amount_usdt * merchant.get("commission_rate", 5.0) / 100, 6)

    # Create trade record first
    trade_id = f"trd_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    trade_doc = {
        "id": trade_id,
        "offer_id": f"qr_aggregator_{method}",
        "trader_id": "qr_aggregator",
        "buyer_id": user["id"],
        "buyer_type": "trader",
        "amount_usdt": amount_usdt,
        "amount_rub": amount_rub,
        "price_rub": qr_price,
        "base_rate": base_rate,
        "provider_rate": provider_rate,
        "provider_markup_pct": provider_markup_pct,
        "platform_markup_pct": platform_markup_pct,
        "platform_commission_usdt": platform_commission_usdt,
        "total_freeze_usdt": total_freeze_usdt,
        "requisite": {"type": "qr_aggregator", "value": "auto", "name": "СБП (QR-код)" if method == "qr" else "Банковская карта"},
        "requisites": [],
        "merchant_id": merchant_id_from_link,
        "payment_link_id": data.payment_link_id,
        "invoice_id": invoice_id_from_link,
        "trader_commission": platform_commission_usdt,
        "merchant_commission": merchant_commission,
        "total_commission": platform_commission_usdt,
        "status": "pending",
        "qr_aggregator_trade": True,
        "qr_method": method,
        "provider_id": provider["id"],
        "created_at": now,
        "expires_at": expires_at,
    }

    await db.trades.insert_one(trade_doc)

    # FREEZE funds from provider: volume + platform commission
    freeze_result = await db.qr_providers.update_one(
        {
            "id": provider["id"],
            "$expr": {"$gte": [{"$subtract": ["$balance_usdt", "$frozen_usdt"]}, total_freeze_usdt]}
        },
        {"$inc": {"frozen_usdt": total_freeze_usdt}}
    )
    if freeze_result.modified_count == 0:
        await db.trades.delete_one({"id": trade_id})
        raise HTTPException(status_code=503, detail="Не удалось заморозить средства провайдера")

    logger.info(f"[QR Buy] Frozen {total_freeze_usdt:.2f} USDT from provider {provider['id']} (volume={data.amount_usdt}, platform_commission={platform_commission_usdt})")

    # Create TrustGain operation
    from services.trustgain_client import TrustGainClient
    import os

    api_key = provider.get(f"{tg_payment_method}_api_key", "")
    secret_key = provider.get(f"{tg_payment_method}_secret_key", "")
    api_url = provider.get(f"{tg_payment_method}_api_url", "https://api.trustgain.io")
    merchant_id_tg = provider.get(f"{tg_payment_method}_merchant_id", "")
    gateway_id = provider.get(f"{tg_payment_method}_gateway_id", "")

    if not api_key or not merchant_id_tg or not gateway_id:
        # Rollback: unfreeze + delete trade
        await db.qr_providers.update_one({"id": provider["id"]}, {"$inc": {"frozen_usdt": -total_freeze_usdt}})
        await db.trades.delete_one({"id": trade_id})
        raise HTTPException(status_code=503, detail="Провайдер не настроен")

    client = TrustGainClient(api_url=api_url, api_key=api_key, secret_key=secret_key)

    backend_url = os.environ.get("BACKEND_URL", "https://reptiloid.vg")
    webhook_url = f"{backend_url}/api/qr-aggregator/webhook/{provider['id']}"
    idempotency_key = str(uuid.uuid4())

    try:
        result = await client.create_income_operation(
            amount=str(amount_rub),
            merchant_id=merchant_id_tg,
            gateway_id=gateway_id,
            client_id=str(user["id"]),
            client_ip="127.0.0.1",
            idempotency_key=idempotency_key,
            webhook_url=webhook_url,
        )
    except Exception as e:
        # Rollback: unfreeze + delete trade
        await db.qr_providers.update_one({"id": provider["id"]}, {"$inc": {"frozen_usdt": -total_freeze_usdt}})
        await db.trades.delete_one({"id": trade_id})
        logger.error(f"[QR Buy] TrustGain API error: {e}")
        raise HTTPException(status_code=502, detail=f"Ошибка API провайдера: {str(e)}")
    finally:
        await client.close()

    if not result.get("success"):
        # Rollback: unfreeze + delete trade
        await db.qr_providers.update_one({"id": provider["id"]}, {"$inc": {"frozen_usdt": -total_freeze_usdt}})
        await db.trades.delete_one({"id": trade_id})
        logger.error(f"[QR Buy] Failed: {result}")
        raise HTTPException(status_code=502, detail=f"Ошибка создания операции: {result.get('error', 'unknown')}")

    operation_data = result.get("data", {})
    trustgain_operation_id = operation_data.get("id", "")
    payment_url = operation_data.get("url", "")

    # Save QR operation record
    op_id = str(uuid.uuid4())
    op_doc = {
        "id": op_id,
        "provider_id": provider["id"],
        "trade_id": trade_id,
        "invoice_id": None,
        "trustgain_operation_id": trustgain_operation_id,
        "idempotency_key": idempotency_key,
        "amount_rub": amount_rub,
        "payment_method": tg_payment_method,
        "status": "pending",
        "gateway_id": gateway_id,
        "merchant_id": merchant_id_tg,
        "trustgain_data": operation_data,
        "provider_earning_usdt": 0,
        "provider_earning_rub": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.qr_provider_operations.insert_one(op_doc)

    await db.qr_providers.update_one(
        {"id": provider["id"]},
        {"$inc": {"active_operations_count": 1}}
    )

    # Extract payment details
    payment_requisite = operation_data.get("payment_requisite", {})
    qr_code_data = payment_requisite.get("sbp") or payment_requisite.get("qr") or ""
    card_number = payment_requisite.get("card_number", "")

    # Update trade with payment details
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "qr_operation_id": op_id,
            "trustgain_operation_id": trustgain_operation_id,
            "payment_url": payment_url,
            "payment_requisite": payment_requisite,
        }}
    )

    logger.info(f"[QR Buy] Trade {trade_id} created for user {user['id']}, amount={data.amount_usdt} USDT, method={method}")

    return {
        "trade_id": trade_id,
        "operation_id": op_id,
        "amount_usdt": amount_usdt,
        "amount_rub": amount_rub,
        "price_rub": qr_price,
        "payment_url": payment_url,
        "payment_requisite": payment_requisite,
        "qr_data": qr_code_data,
        "card_number": card_number,
        "status": "pending",
        "expires_at": expires_at,
        "expires_in": 1800,
    }


@router.post("/qr-aggregator/create-operation")
async def create_qr_operation(request: Request, background_tasks: BackgroundTasks):
    """Create a QR operation for a trade - called when customer selects QR payment"""
    body = await request.json()

    trade_id = body.get("trade_id")
    invoice_id = body.get("invoice_id")
    amount_rub = body.get("amount_rub", 0)
    payment_method = body.get("payment_method", "nspk")  # 'nspk' or 'transgrant'
    client_id = body.get("client_id", "anonymous")
    client_ip = body.get("client_ip", "127.0.0.1")

    if not trade_id and not invoice_id:
        raise HTTPException(status_code=400, detail="trade_id or invoice_id required")
    if amount_rub <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    # Select best provider for this method
    providers = await db.qr_providers.find({
        "is_active": True,
        f"{payment_method}_enabled": True,
        "balance_usdt": {"$gt": 0},
    }, {"_id": 0}).to_list(100)

    base_rate = await _get_base_rate()

    # Filter by capacity and balance
    eligible = []
    for p in providers:
        available_usdt = p.get("balance_usdt", 0) - p.get("frozen_usdt", 0)
        available_rub = available_usdt * base_rate
        if available_rub >= amount_rub:
            if p.get("active_operations_count", 0) < p.get("max_concurrent_operations", 10):
                eligible.append(p)

    if not eligible:
        raise HTTPException(status_code=503, detail="Нет доступных провайдеров для данной суммы")

    # Weighted random selection
    import random
    weights = [p.get("weight", 100) for p in eligible]
    provider = random.choices(eligible, weights=weights, k=1)[0]

    # Create TrustGain operation via API per docs
    from services.trustgain_client import TrustGainClient

    api_key = provider.get(f"{payment_method}_api_key", "")
    secret_key = provider.get(f"{payment_method}_secret_key", "")
    api_url = provider.get(f"{payment_method}_api_url", "https://api.trustgain.io")
    merchant_id = provider.get(f"{payment_method}_merchant_id", "")
    gateway_id = provider.get(f"{payment_method}_gateway_id", "")

    if not api_key or not merchant_id or not gateway_id:
        raise HTTPException(status_code=503, detail="Провайдер не настроен полностью")

    client = TrustGainClient(api_url=api_url, api_key=api_key, secret_key=secret_key)

    import os
    backend_url = os.environ.get("BACKEND_URL", "https://reptiloid.vg")
    webhook_url = f"{backend_url}/api/qr-aggregator/webhook/{provider['id']}"

    idempotency_key = str(uuid.uuid4())

    result = await client.create_income_operation(
        amount=str(amount_rub),
        merchant_id=merchant_id,
        gateway_id=gateway_id,
        client_id=str(client_id),
        client_ip=client_ip,
        idempotency_key=idempotency_key,
        webhook_url=webhook_url,
    )
    await client.close()

    if not result.get("success"):
        logger.error(f"[QR Op] Failed to create operation: {result}")
        raise HTTPException(status_code=502, detail=f"Ошибка создания операции: {result.get('error', 'unknown')}")

    operation_data = result.get("data", {})
    trustgain_operation_id = operation_data.get("id", "")
    payment_url = operation_data.get("url", "")

    # Save operation
    op_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    op_doc = {
        "id": op_id,
        "provider_id": provider["id"],
        "trade_id": trade_id,
        "invoice_id": invoice_id,
        "trustgain_operation_id": trustgain_operation_id,
        "idempotency_key": idempotency_key,
        "amount_rub": amount_rub,
        "payment_method": payment_method,
        "status": "pending",
        "gateway_id": gateway_id,
        "merchant_id": merchant_id,
        "trustgain_data": operation_data,
        "provider_earning_usdt": 0,
        "provider_earning_rub": 0,
        "created_at": now,
        "updated_at": now,
    }

    await db.qr_provider_operations.insert_one(op_doc)

    await db.qr_providers.update_one(
        {"id": provider["id"]},
        {"$inc": {"active_operations_count": 1}}
    )

    # FREEZE funds for merchant trade too
    base_rate_val = await _get_base_rate()
    qr_settings_m = await db.qr_aggregator_settings.find_one({"type": "main"}, {"_id": 0})
    platform_markup_m = qr_settings_m.get(f"{payment_method}_commission_percent", 5.0) if qr_settings_m else 5.0
    amount_usdt_m = amount_rub / base_rate_val if base_rate_val > 0 else 0
    platform_commission_usdt_m = round(amount_usdt_m * platform_markup_m / 100, 6)
    total_freeze_m = round(amount_usdt_m + platform_commission_usdt_m, 6)

    freeze_r = await db.qr_providers.update_one(
        {
            "id": provider["id"],
            "$expr": {"$gte": [{"$subtract": ["$balance_usdt", "$frozen_usdt"]}, total_freeze_m]}
        },
        {"$inc": {"frozen_usdt": total_freeze_m}}
    )

    # Update trade with freeze info if trade_id exists
    if trade_id and freeze_r.modified_count > 0:
        await db.trades.update_one(
            {"id": trade_id},
            {"$set": {
                "platform_commission_usdt": platform_commission_usdt_m,
                "total_freeze_usdt": total_freeze_m,
                "platform_markup_pct": platform_markup_m,
                "provider_id": provider["id"],
                "qr_aggregator_trade": True,
            }}
        )
        logger.info(f"[QR Op] Frozen {total_freeze_m:.2f} USDT from provider {provider['id']} for trade {trade_id}")

    # Extract payment requisites from TrustGain response
    payment_requisite = operation_data.get("payment_requisite", {})
    qr_data = payment_requisite.get("sbp") or ""
    card_number = payment_requisite.get("card_number", "")

    return {
        "status": "success",
        "operation_id": op_id,
        "trustgain_operation_id": trustgain_operation_id,
        "payment_url": payment_url,
        "payment_requisite": payment_requisite,
        "qr_data": qr_data,
        "card_number": card_number,
        "amount_rub": amount_rub,
        "payment_method": payment_method,
        "expires_in": 1800,
    }


# ==================== Health Check Background Task ====================

async def _cleanup_expired_trades():
    """Cleanup expired QR trades and unfreeze provider funds"""
    try:
        now = datetime.now(timezone.utc).isoformat()
        expired_trades = await db.trades.find({
            "$or": [{"trader_id": "qr_aggregator"}, {"qr_aggregator_trade": True}],
            "status": "pending",
            "expires_at": {"$lt": now}
        }).to_list(100)
        
        for trade in expired_trades:
            provider_id = trade.get("provider_id")
            total_freeze = trade.get("total_freeze_usdt", 0)
            
            await db.trades.update_one(
                {"id": trade["id"], "status": "pending"},
                {"$set": {"status": "cancelled", "cancelled_at": now, "cancel_reason": "expired"}}
            )
            
            if provider_id and total_freeze > 0:
                result = await db.qr_providers.update_one(
                    {"id": provider_id, "frozen_usdt": {"$gte": total_freeze}},
                    {"$inc": {"frozen_usdt": -total_freeze, "active_operations_count": -1}}
                )
                if result.modified_count == 0:
                    p = await db.qr_providers.find_one({"id": provider_id})
                    if p:
                        await db.qr_providers.update_one(
                            {"id": provider_id},
                            {"$set": {
                                "frozen_usdt": max(0, p.get("frozen_usdt", 0) - total_freeze),
                                "active_operations_count": max(0, p.get("active_operations_count", 0) - 1)
                            }}
                        )
                logger.info(f"[QR Cleanup] Expired trade {trade['id']}: unfrozen {total_freeze:.4f} USDT for provider {provider_id}")
            
            # Cancel the TrustGain operation too
            op = await db.qr_provider_operations.find_one({"trade_id": trade["id"], "status": "pending"})
            if op:
                await db.qr_provider_operations.update_one(
                    {"id": op["id"]},
                    {"$set": {"status": "cancelled", "updated_at": now}}
                )
        
        if expired_trades:
            logger.info(f"[QR Cleanup] Cleaned up {len(expired_trades)} expired trades")
    except Exception as e:
        logger.error(f"[QR Cleanup] Error: {e}")

async def qr_health_check_loop():
    """Background task to check QR provider health every N seconds"""
    while True:
        # Cleanup expired trades on each cycle
        await _cleanup_expired_trades()

        interval = 45
        try:
            settings = await db.qr_aggregator_settings.find_one({"type": "main"}, {"_id": 0})
            if settings:
                interval = settings.get("health_check_interval", 45)
                if not settings.get("is_enabled", True):
                    await asyncio.sleep(interval)
                    continue

            providers = await db.qr_providers.find({"is_active": True}, {"_id": 0}).to_list(100)

            for provider in providers:
                for prefix in ("nspk", "transgrant"):
                    api_key = provider.get(f"{prefix}_api_key", "")
                    secret_key = provider.get(f"{prefix}_secret_key", "")
                    api_url = provider.get(f"{prefix}_api_url", "https://api.trustgain.io")

                    if not api_key or api_key.startswith("demo") or len(api_key) < 10:
                        continue

                    try:
                        from services.trustgain_client import TrustGainClient
                        client = TrustGainClient(api_url=api_url, api_key=api_key, secret_key=secret_key)
                        is_healthy = await client.check_health()
                        await client.close()

                        await db.qr_providers.update_one(
                            {"id": provider["id"]},
                            {"$set": {
                                f"{prefix}_api_available": is_healthy,
                                "last_health_check": datetime.now(timezone.utc).isoformat(),
                            }}
                        )

                        if not is_healthy:
                            logger.warning(f"[QR Health] Provider {provider['id']} {prefix} API unavailable")
                    except Exception as e:
                        logger.error(f"[QR Health] Error checking {prefix} for {provider['id']}: {e}")

        except Exception as e:
            logger.error(f"[QR Health] Loop error: {e}")

        await asyncio.sleep(interval)
