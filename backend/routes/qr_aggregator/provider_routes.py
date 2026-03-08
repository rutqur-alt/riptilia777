from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import uuid

from fastapi import Depends, HTTPException

from core.auth import create_token, verify_password
from core.database import db

from .router import logger, router
from .schemas import QRProviderLogin, WithdrawRequest
from .utils import get_qr_provider_user, mask_key


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
        {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}},
    )

    return {
        "token": token,
        "user": {
            "id": provider["id"],
            "login": provider["login"],
            "display_name": provider["display_name"],
            "role": "qr_provider",
            "is_active": provider.get("is_active", False),
        },
    }


@router.get("/qr-provider/me")
async def get_qr_provider_profile(provider: dict = Depends(get_qr_provider_user)):
    """Get current QR provider profile (sensitive keys masked)"""
    safe = {k: v for k, v in provider.items() if k not in (
        "password_hash", "nspk_secret_key", "transgrant_secret_key"
    )}

    for prefix in ("nspk", "transgrant"):
        key_field = f"{prefix}_api_key"
        if safe.get(key_field):
            safe[key_field] = mask_key(safe[key_field])

    return safe


@router.get("/qr-provider/stats")
async def get_qr_provider_stats(provider: dict = Depends(get_qr_provider_user)):
    """Get provider statistics - separate per integration (NSPK + TransGrant)"""
    provider_id = provider["id"]
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    stats = {}
    for method in ("nspk", "transgrant"):
        today_ops = await db.qr_provider_operations.count_documents({
            "provider_id": provider_id,
            "payment_method": method,
            "created_at": {"$gte": today_start},
        })
        today_completed = await db.qr_provider_operations.count_documents({
            "provider_id": provider_id,
            "payment_method": method,
            "status": "completed",
            "created_at": {"$gte": today_start},
        })
        today_vol_cur = db.qr_provider_operations.aggregate([
            {
                "$match": {
                    "provider_id": provider_id,
                    "payment_method": method,
                    "status": "completed",
                    "created_at": {"$gte": today_start},
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$amount_rub"}}},
        ])
        today_vol_list = await today_vol_cur.to_list(1)
        today_volume = today_vol_list[0]["total"] if today_vol_list else 0

        total_ops = await db.qr_provider_operations.count_documents({
            "provider_id": provider_id,
            "payment_method": method,
        })
        total_completed = await db.qr_provider_operations.count_documents({
            "provider_id": provider_id,
            "payment_method": method,
            "status": "completed",
        })
        total_vol_cur = db.qr_provider_operations.aggregate([
            {
                "$match": {
                    "provider_id": provider_id,
                    "payment_method": method,
                    "status": "completed",
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$amount_rub"}}},
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

    active_ops = await db.qr_provider_operations.count_documents({
        "provider_id": provider_id,
        "status": {"$in": ["pending", "processing"]},
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
    provider: dict = Depends(get_qr_provider_user),
):
    """Get provider's operations history (filterable by method: nspk/transgrant)."""
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

    trade_ids = [op.get("trade_id") for op in operations if op.get("trade_id")]
    trades_by_id: Dict[str, dict] = {}
    if trade_ids:
        trades = await db.trades.find(
            {"id": {"$in": trade_ids}},
            {
                "_id": 0,
                "id": 1,
                "trade_number": 1,
                "status": 1,
                "amount_usdt": 1,
                "expires_at": 1,
                "merchant_id": 1,
                "buyer_id": 1,
            },
        ).to_list(len(trade_ids))
        trades_by_id = {t["id"]: t for t in trades if t.get("id")}

    for op in operations:
        t = trades_by_id.get(op.get("trade_id"))
        if t:
            op["trade_number"] = t.get("trade_number")
            op["trade_status"] = t.get("status")
            op["trade_amount_usdt"] = t.get("amount_usdt")
            op["trade_expires_at"] = t.get("expires_at")
            op["trade_merchant_id"] = t.get("merchant_id")
            op["trade_buyer_id"] = t.get("buyer_id")

    return {
        "operations": operations,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/qr-provider/wallet")
async def get_qr_provider_wallet(provider: dict = Depends(get_qr_provider_user)):
    """Get provider wallet info - balance in USDT."""
    provider_id = provider["id"]

    earnings_cursor = db.qr_provider_operations.aggregate([
        {"$match": {"provider_id": provider_id, "status": "completed"}},
        {"$group": {"_id": None, "total_earnings": {"$sum": "$provider_earning_usdt"}}},
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
async def get_qr_provider_deposit_address(provider: dict = Depends(get_qr_provider_user)):
    """Get deposit address for provider (same flow as regular users)."""
    provider_id = provider["id"]
    import random, string

    deposit_code = provider.get("deposit_code")
    if not deposit_code:
        for _ in range(20):
            code = "".join(random.choices(string.digits, k=6))
            existing = await db.qr_providers.find_one({"deposit_code": code})
            if not existing:
                ex2 = await db.traders.find_one({"deposit_code": code})
                ex3 = await db.merchants.find_one({"deposit_code": code})
                if not ex2 and not ex3:
                    deposit_code = code
                    await db.qr_providers.update_one(
                        {"id": provider_id},
                        {"$set": {"deposit_code": code}},
                    )
                    break

    try:
        from routes.ton_finance import get_deposit_address

        result = await get_deposit_address(provider_id)
        wallet_address = result.get("address", "")
    except Exception as e:
        logger.error(f"[QR Provider] Failed to get deposit address: {e}")
        settings = await db.settings.find_one({"type": "ton_settings"}, {"_id": 0})
        wallet_address = settings.get("hot_wallet_address", "") if settings else ""

    return {
        "deposit_info": {
            "address": wallet_address,
            "comment": deposit_code,
            "instructions": [
                "1. Отправьте USDT (TRC-20 или TON) на адрес выше",
                f"2. ОБЯЗАТЕЛЬНО укажите комментарий: {deposit_code}",
                "3. Депозит будет зачислен автоматически после подтверждения",
            ],
        }
    }


@router.post("/qr-provider/withdraw")
async def qr_provider_withdraw(data: WithdrawRequest, provider: dict = Depends(get_qr_provider_user)):
    """Request USDT withdrawal - same flow as regular users."""
    provider_id = provider["id"]
    now = datetime.now(timezone.utc).isoformat()

    five_seconds_ago = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    recent = await db.withdrawal_requests.find_one({
        "user_id": provider_id,
        "amount": data.amount,
        "created_at": {"$gte": five_seconds_ago},
        "status": "pending",
    })
    if recent:
        raise HTTPException(status_code=429, detail="Заявка уже создана. Подождите.")

    balance_usdt = provider.get("balance_usdt", 0)
    frozen_usdt = provider.get("frozen_usdt", 0)
    available = balance_usdt - frozen_usdt

    WITHDRAWAL_FEE = 1.0
    total_needed = data.amount + WITHDRAWAL_FEE

    if total_needed > available:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Недостаточно средств. Нужно: {total_needed:.2f} USDT (включая комиссию {WITHDRAWAL_FEE} USDT). "
                f"Доступно: {available:.2f} USDT"
            ),
        )

    result = await db.qr_providers.update_one(
        {"id": provider_id, "balance_usdt": {"$gte": frozen_usdt + total_needed}},
        {"$inc": {"frozen_usdt": total_needed}},
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
async def get_qr_provider_finances(provider: dict = Depends(get_qr_provider_user)):
    """QR Provider: Financial overview with separate stats per integration."""
    provider_id = provider["id"]

    finances = {}
    for method in ("nspk", "transgrant"):
        pipeline = [
            {"$match": {"provider_id": provider_id, "payment_method": method, "status": "completed"}},
            {
                "$group": {
                    "_id": None,
                    "total_amount_rub": {"$sum": "$amount_rub"},
                    "total_earning_usdt": {"$sum": "$provider_earning_usdt"},
                    "count": {"$sum": 1},
                }
            },
        ]
        agg = await db.qr_provider_operations.aggregate(pipeline).to_list(1)
        total_ops = await db.qr_provider_operations.count_documents(
            {"provider_id": provider_id, "payment_method": method}
        )
        completed = agg[0]["count"] if agg else 0
        finances[method] = {
            "total_operations": total_ops,
            "completed_operations": completed,
            "turnover_rub": round(agg[0]["total_amount_rub"], 2) if agg else 0,
            "earnings_usdt": round(agg[0]["total_earning_usdt"], 4) if agg else 0,
            "success_rate": round((completed / total_ops * 100) if total_ops > 0 else 100, 1),
        }

    recent_txs = await db.transactions.find({"user_id": provider_id}, {"_id": 0}).sort(
        "created_at", -1
    ).limit(50).to_list(50)

    withdrawals = await db.withdrawal_requests.find({"user_id": provider_id}, {"_id": 0}).sort(
        "created_at", -1
    ).limit(20).to_list(20)

    return {
        "balance_usdt": round(provider.get("balance_usdt", 0), 2),
        "frozen_usdt": round(provider.get("frozen_usdt", 0), 2),
        "available_usdt": round(provider.get("balance_usdt", 0) - provider.get("frozen_usdt", 0), 2),
        "nspk": finances["nspk"],
        "transgrant": finances["transgrant"],
        "recent_transactions": recent_txs,
        "withdrawal_history": withdrawals,
    }
