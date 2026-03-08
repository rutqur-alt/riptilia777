"""Trading and public offer routes for QR aggregator.

Extracted from legacy.py to keep modules focused.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

from core.auth import require_role
from core.database import db

from .router import logger, router
from .utils import get_base_rate as _get_base_rate

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
            "trader_login": "MAGNAT",
            "trader_display_name": f"MAGNAT ({label})",
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
