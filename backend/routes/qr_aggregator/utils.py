from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from core.auth import get_current_user
from core.database import db


def mask_key(key: str) -> str:
    """Mask API key for display."""
    if not key or len(key) < 12:
        return "***" if key else ""
    return key[:6] + "..." + key[-4:]


def mask_secret(key: str) -> str:
    """Mask secret key for display."""
    if not key or len(key) < 8:
        return "****" if key else ""
    return "*" * (len(key) - 4) + key[-4:]


async def get_qr_provider_user(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: ensure user is a qr_provider."""
    if user.get("role") != "qr_provider":
        raise HTTPException(status_code=403, detail="QR Provider access required")

    provider = await db.qr_providers.find_one({"id": user["id"]}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    return provider


async def get_base_rate() -> float:
    """Get base USDT/RUB exchange rate."""
    payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    return payout_settings.get("base_rate", 78.0) if payout_settings else 78.0


async def touch_provider_last_seen(provider_id: str) -> None:
    await db.qr_providers.update_one(
        {"id": provider_id},
        {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}},
    )
