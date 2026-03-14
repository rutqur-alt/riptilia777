from datetime import datetime, timezone
import uuid

from fastapi import Depends, HTTPException, Request

from core.auth import hash_password, require_admin_level
from core.database import db

from .router import logger, router
from .schemas import AdminAdjustBalance, QRAggregatorSettings, QRProviderCreate, QRProviderUpdate
from .utils import mask_key, mask_secret


@router.get("/admin/qr-providers")
async def admin_list_qr_providers(user: dict = Depends(require_admin_level(50))):
    """Admin: List all QR providers."""
    providers = await db.qr_providers.find(
        {},
        {"_id": 0, "password_hash": 0, "nspk_secret_key": 0, "transgrant_secret_key": 0},
    ).to_list(100)

    for p in providers:
        for prefix in ("nspk", "transgrant"):
            key_field = f"{prefix}_api_key"
            if p.get(key_field):
                p[key_field] = mask_key(p[key_field])

    return {"providers": providers, "total": len(providers)}


@router.post("/admin/qr-providers")
async def admin_create_qr_provider(
    data: QRProviderCreate, user: dict = Depends(require_admin_level(80))
):
    """Admin: Create a new QR provider."""
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

    safe_doc = {
        k: v
        for k, v in provider_doc.items()
        if k not in ("password_hash", "nspk_secret_key", "transgrant_secret_key", "_id")
    }
    logger.info(f"[QR Aggregator] Provider created: {provider_id} ({data.login})")

    return {"status": "success", "provider": safe_doc}


@router.get("/admin/qr-providers/{provider_id}")
async def admin_get_qr_provider(provider_id: str, user: dict = Depends(require_admin_level(50))):
    """Admin: Get QR provider details."""
    provider = await db.qr_providers.find_one({"id": provider_id}, {"_id": 0, "password_hash": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    for prefix in ("nspk", "transgrant"):
        sk = f"{prefix}_secret_key"
        ak = f"{prefix}_api_key"
        if provider.get(sk):
            provider[sk] = mask_secret(provider[sk])
        if provider.get(ak):
            provider[ak] = mask_key(provider[ak])

    return provider


@router.put("/admin/qr-providers/{provider_id}")
async def admin_update_qr_provider(
    provider_id: str, data: QRProviderUpdate, user: dict = Depends(require_admin_level(80))
):
    """Admin: Update QR provider."""
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

    logger.info(
        f"[QR Aggregator] Provider updated: {provider_id}, fields: {list(update_data.keys())}"
    )
    return {"status": "success", "updated_fields": list(update_data.keys())}


@router.delete("/admin/qr-providers/{provider_id}")
async def admin_delete_qr_provider(provider_id: str, user: dict = Depends(require_admin_level(100))):
    """Admin: Delete QR provider (owner only)."""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    active_ops = await db.qr_provider_operations.count_documents(
        {"provider_id": provider_id, "status": {"$in": ["pending", "processing"]}}
    )
    if active_ops > 0:
        raise HTTPException(status_code=400, detail=f"У провайдера есть {active_ops} активных операций.")

    if provider.get("balance_usdt", 0) > 0:
        raise HTTPException(status_code=400, detail="У провайдера есть баланс. Сначала выведите средства.")

    await db.qr_providers.delete_one({"id": provider_id})
    logger.info(f"[QR Aggregator] Provider deleted: {provider_id}")
    return {"status": "success"}


@router.post("/admin/qr-providers/{provider_id}/toggle")
async def admin_toggle_qr_provider(provider_id: str, user: dict = Depends(require_admin_level(80))):
    """Admin: Toggle provider active status."""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    new_status = not provider.get("is_active", False)
    await db.qr_providers.update_one(
        {"id": provider_id},
        {"$set": {"is_active": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    logger.info(f"[QR Aggregator] Provider {provider_id} {'activated' if new_status else 'deactivated'}")
    return {"status": "success", "is_active": new_status}


@router.post("/admin/qr-providers/{provider_id}/reset-password")
async def admin_reset_qr_provider_password(provider_id: str, user: dict = Depends(require_admin_level(80))):
    """Admin: Reset QR provider password."""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    import secrets
    import string

    chars = string.ascii_letters + string.digits + "!@#$%"
    new_password = "".join(secrets.choice(chars) for _ in range(12))

    await db.qr_providers.update_one(
        {"id": provider_id},
        {"$set": {"password_hash": hash_password(new_password), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    logger.info(f"[QR Aggregator] Password reset for provider: {provider_id}")
    return {"status": "success", "new_password": new_password}


@router.put("/admin/qr-providers/{provider_id}/api-keys")
async def admin_update_qr_provider_api_keys(
    provider_id: str, request: Request, user: dict = Depends(require_admin_level(80))
):
    """Admin: Update QR provider API keys for NSPK or TransGrant integration."""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    body = await request.json()
    update_data = {}

    for field in ("nspk_api_key", "nspk_secret_key", "nspk_api_url", "nspk_merchant_id", "nspk_gateway_id"):
        if field in body and body[field]:
            update_data[field] = body[field]

    for field in (
        "transgrant_api_key",
        "transgrant_secret_key",
        "transgrant_api_url",
        "transgrant_merchant_id",
        "transgrant_gateway_id",
    ):
        if field in body and body[field]:
            update_data[field] = body[field]

    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.qr_providers.update_one({"id": provider_id}, {"$set": update_data})

    logger.info(
        f"[QR Aggregator] API keys updated for provider: {provider_id}, fields: {list(update_data.keys())}"
    )
    return {"status": "success", "updated_fields": list(update_data.keys())}


@router.get("/admin/qr-providers/{provider_id}/api-keys")
async def admin_get_qr_provider_api_keys(provider_id: str, user: dict = Depends(require_admin_level(80))):
    """Admin: Get QR provider API keys (masked) - separate per integration."""
    provider = await db.qr_providers.find_one({"id": provider_id}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")

    return {
        "nspk": {
            "api_key": provider.get("nspk_api_key", ""),
            "secret_key": mask_secret(provider.get("nspk_secret_key", "")),
            "api_url": provider.get("nspk_api_url", "https://api.trustgain.io"),
            "merchant_id": provider.get("nspk_merchant_id", ""),
            "gateway_id": provider.get("nspk_gateway_id", ""),
        },
        "transgrant": {
            "api_key": provider.get("transgrant_api_key", ""),
            "secret_key": mask_secret(provider.get("transgrant_secret_key", "")),
            "api_url": provider.get("transgrant_api_url", "https://api.trustgain.io"),
            "merchant_id": provider.get("transgrant_merchant_id", ""),
            "gateway_id": provider.get("transgrant_gateway_id", ""),
        },
    }


@router.post("/admin/qr-providers/{provider_id}/health-check")
async def admin_health_check_provider(provider_id: str, user: dict = Depends(require_admin_level(50))):
    """Admin: Manually trigger health check for both integrations."""
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
        {
            "$set": {
                "nspk_api_available": results.get("nspk", False),
                "transgrant_api_available": results.get("transgrant", False),
                "last_health_check": now,
            }
        },
    )

    return {
        "status": "success",
        "nspk_available": results.get("nspk"),
        "transgrant_available": results.get("transgrant"),
        "checked_at": now,
    }


@router.get("/admin/qr-aggregator/settings")
async def admin_get_qr_settings(user: dict = Depends(require_admin_level(50))):
    """Admin: Get QR Aggregator settings (separate per integration)."""
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
async def admin_update_qr_settings(
    data: QRAggregatorSettings, user: dict = Depends(require_admin_level(80))
):
    """Admin: Update QR Aggregator settings (separate commissions per integration)."""
    update = data.model_dump()
    update["type"] = "main"
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.qr_aggregator_settings.update_one({"type": "main"}, {"$set": update}, upsert=True)
    return {"status": "success"}


@router.post("/admin/qr-providers/{provider_id}/adjust-balance")
async def admin_adjust_provider_balance(
    provider_id: str, data: AdminAdjustBalance, user: dict = Depends(require_admin_level(80))
):
    """Admin: Adjust provider balance (add or subtract USDT)."""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    current_balance = provider.get("balance_usdt", 0)
    current_frozen = provider.get("frozen_usdt", 0)
    available = current_balance - current_frozen

    if data.amount < 0 and abs(data.amount) > available:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot subtract {abs(data.amount)} USDT. Available: {round(available, 4)} USDT "
                f"(frozen: {round(current_frozen, 4)})"
            ),
        )

    new_balance = round(current_balance + data.amount, 6)
    if new_balance < 0:
        raise HTTPException(status_code=400, detail="Balance cannot go negative")

    await db.qr_providers.update_one(
        {"id": provider_id},
        {"$set": {"balance_usdt": new_balance, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

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

    logger.info(
        f"[QR Admin] Balance adjusted for {provider_id}: {current_balance} -> {new_balance} "
        f"({data.amount:+.4f}) by {user.get('login')}, reason: {data.reason}"
    )

    pending_completed = 0
    if data.amount > 0:
        try:
            from .legacy import _process_pending_completions

            pending_completed = await _process_pending_completions(provider_id)
            if pending_completed > 0:
                logger.info(
                    f"[QR Admin] Auto-completed {pending_completed} pending trades after balance adjustment for {provider_id}"
                )
        except Exception as e:
            logger.error(f"[QR Admin] Error processing pending completions: {e}")

    return {
        "status": "success",
        "old_balance": round(current_balance, 4),
        "new_balance": round(new_balance, 4),
        "adjustment": data.amount,
        "available": round(new_balance - current_frozen, 4),
        "pending_completed": pending_completed,
    }


@router.post("/admin/qr-providers/{provider_id}/reconcile-frozen")
async def admin_reconcile_frozen(provider_id: str, user: dict = Depends(require_admin_level(80))):
    """Admin: Reconcile frozen balance - recalculate from actual active trades."""
    provider = await db.qr_providers.find_one({"id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    active_trades = await db.trades.find(
        {
            "provider_id": provider_id,
            "status": {"$in": ["pending", "paid"]},
            "$or": [{"trader_id": "qr_aggregator"}, {"qr_aggregator_trade": True}],
        }
    ).to_list(500)

    frozen_sum = 0
    for trade in active_trades:
        frozen_sum += trade.get("total_freeze_usdt", 0)

    old_frozen = provider.get("frozen_usdt", 0)
    old_active = provider.get("active_operations_count", 0)

    await db.qr_providers.update_one(
        {"id": provider_id},
        {
            "$set": {
                "frozen_usdt": round(frozen_sum, 6),
                "active_operations_count": len(active_trades),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    logger.info(
        f"[QR Admin] Reconciled frozen for {provider_id}: {old_frozen} -> {frozen_sum} (active: {old_active} -> {len(active_trades)})"
    )

    return {
        "status": "success",
        "old_frozen": round(old_frozen, 4),
        "new_frozen": round(frozen_sum, 4),
        "active_trades": len(active_trades),
    }


@router.get("/admin/qr-providers/{provider_id}/balance-logs")
async def admin_get_balance_logs(provider_id: str, user: dict = Depends(require_admin_level(50))):
    """Admin: Get provider balance adjustment logs."""
    logs = await db.qr_provider_balance_logs.find(
        {"provider_id": provider_id}, {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    return {"logs": logs}


@router.get("/admin/qr-aggregator/stats")
async def admin_get_qr_aggregator_stats(user: dict = Depends(require_admin_level(50))):
    """Admin: Get overall QR aggregator statistics."""
    providers = await db.qr_providers.find({}, {"_id": 0, "password_hash": 0}).to_list(100)

    total_balance = sum(p.get("balance_usdt", 0) for p in providers)
    total_frozen = sum(p.get("frozen_usdt", 0) for p in providers)
    total_active_ops = sum(p.get("active_operations_count", 0) for p in providers)

    total_operations = await db.qr_provider_operations.count_documents({})
    completed_operations = await db.qr_provider_operations.count_documents({"status": "completed"})
    pending_operations = await db.qr_provider_operations.count_documents({"status": {"$in": ["pending", "processing"]}})

    # Volume & earnings
    volume_cursor = db.qr_provider_operations.aggregate([
        {"$match": {"status": "completed"}},
        {"$group": {"_id": None, "total_volume": {"$sum": "$amount_rub"}, "total_earnings": {"$sum": "$provider_earning_usdt"}}},
    ])
    volume_list = await volume_cursor.to_list(1)
    total_volume = volume_list[0]["total_volume"] if volume_list else 0
    total_earnings = volume_list[0]["total_earnings"] if volume_list else 0

    return {
        "providers": {
            "total": len(providers),
            "active": sum(1 for p in providers if p.get("is_active")),
            "balance_usdt": round(total_balance, 2),
            "frozen_usdt": round(total_frozen, 2),
            "available_usdt": round(total_balance - total_frozen, 2),
            "active_operations": total_active_ops,
        },
        "operations": {
            "total": total_operations,
            "completed": completed_operations,
            "pending": pending_operations,
            "success_rate": round((completed_operations / total_operations * 100) if total_operations > 0 else 100, 1),
        },
        "financial": {
            "total_volume_rub": round(total_volume, 2),
            "total_earnings_usdt": round(total_earnings, 4),
        },
    }
