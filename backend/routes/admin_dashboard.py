"""
Admin Dashboard Routes - Migrated from server.py
Handles admin analytics, dashboard stats, system settings, maintenance
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

from core.auth import require_role, require_admin_level, log_admin_action
from core.database import db

router = APIRouter(tags=["admin_dashboard"])


# ==================== MODELS ====================

class MaintenanceToggle(BaseModel):
    enabled: bool
    message: Optional[str] = "Ведутся технические работы"


# ==================== ADMIN: ANALYTICS ====================

@router.get("/admin/analytics")
async def get_analytics(period: str = "week", user: dict = Depends(require_role(["admin"]))):
    """Get analytics for period (day, week, month)"""
    now = datetime.now(timezone.utc)
    
    if period == "day":
        start = now - timedelta(days=1)
    elif period == "week":
        start = now - timedelta(days=7)
    else:  # month
        start = now - timedelta(days=30)
    
    start_str = start.isoformat()
    
    # Get completed trades in period
    trades = await db.trades.find(
        {"created_at": {"$gte": start_str}, "status": "completed"},
        {"_id": 0}
    ).to_list(100000)
    
    total_volume = sum(t.get("amount_usdt", 0) for t in trades)
    total_trades = len(trades)
    # Commission in USDT - use merchant_commission field
    total_commission_usdt = sum(t.get("merchant_commission", 0) or 0 for t in trades)
    total_turnover_rub = sum(t.get("client_amount_rub", 0) or t.get("amount_rub", 0) for t in trades)
    
    # Volume by day
    volume_by_day = {}
    for trade in trades:
        day = trade["created_at"][:10]
        volume_by_day[day] = volume_by_day.get(day, 0) + trade.get("amount_usdt", 0)
    
    # Top traders
    trader_volumes = {}
    for trade in trades:
        tid = trade["trader_id"]
        trader_volumes[tid] = trader_volumes.get(tid, 0) + trade.get("amount_usdt", 0)
    
    top_traders = sorted(trader_volumes.items(), key=lambda x: x[1], reverse=True)[:10]
    top_traders_data = []
    for tid, vol in top_traders:
        trader = await db.traders.find_one({"id": tid}, {"_id": 0})
        if trader:
            top_traders_data.append({"login": trader["login"], "volume": round(vol, 2)})
    
    return {
        "period": period,
        "total_volume": round(total_volume, 2),
        "total_trades": total_trades,
        "total_commission": round(total_commission_usdt, 4),
        "total_turnover_rub": round(total_turnover_rub, 2),
        "avg_trade_size": round(total_volume / total_trades, 2) if total_trades > 0 else 0,
        "volume_by_day": volume_by_day,
        "top_traders": top_traders_data
    }


# ==================== ADMIN: SYSTEM SETTINGS ====================

@router.get("/admin/system-settings")
async def get_system_settings(user: dict = Depends(require_role(["admin"]))):
    """Get system settings"""
    settings = await db.system_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {
            "trade_timeout_minutes": 30,
            "dispute_timeout_minutes": 10,
            "max_daily_volume_new_trader": 10000,
            "referral_rate": 0.5
        }
        await db.system_settings.insert_one(settings)
    return settings


@router.put("/admin/system-settings")
async def update_system_settings(
    trade_timeout_minutes: Optional[int] = None,
    dispute_timeout_minutes: Optional[int] = None,
    max_daily_volume_new_trader: Optional[float] = None,
    referral_rate: Optional[float] = None,
    user: dict = Depends(require_role(["admin"]))
):
    """Update system settings"""
    update_data = {}
    if trade_timeout_minutes is not None:
        update_data["trade_timeout_minutes"] = trade_timeout_minutes
    if dispute_timeout_minutes is not None:
        update_data["dispute_timeout_minutes"] = dispute_timeout_minutes
    if max_daily_volume_new_trader is not None:
        update_data["max_daily_volume_new_trader"] = max_daily_volume_new_trader
    if referral_rate is not None:
        update_data["referral_rate"] = referral_rate
    
    if update_data:
        await db.system_settings.update_one({}, {"$set": update_data}, upsert=True)
    
    return await get_system_settings(user)


# ==================== SYSTEM STATUS & MAINTENANCE ====================

@router.get("/system/status")
async def get_system_status():
    """Get system status including maintenance mode"""
    settings = await db.system_settings.find_one({}, {"_id": 0})
    maintenance = settings.get("maintenance_mode", False) if settings else False
    maintenance_message = settings.get("maintenance_message", "") if settings else ""
    
    return {
        "status": "maintenance" if maintenance else "online",
        "maintenance_mode": maintenance,
        "maintenance_message": maintenance_message
    }


@router.post("/admin/maintenance")
async def toggle_maintenance(data: MaintenanceToggle, user: dict = Depends(require_role(["admin", "owner"]))):
    """Toggle maintenance mode"""
    enabled = data.enabled
    message = data.message or "Ведутся технические работы"
    
    await db.system_settings.update_one(
        {},
        {"$set": {"maintenance_mode": enabled, "maintenance_message": message}},
        upsert=True
    )
    
    await log_admin_action(user["id"], "toggle_maintenance", "system", "maintenance", {"enabled": enabled, "message": message})
    
    return {"status": "success", "maintenance_mode": enabled}


@router.get("/maintenance-status")
async def get_maintenance_status():
    """Public endpoint to check maintenance status"""
    settings = await db.system_settings.find_one({}, {"_id": 0})
    if settings and settings.get("maintenance_mode"):
        return {
            "maintenance": True,
            "enabled": True,
            "message": settings.get("maintenance_message", "Ведутся технические работы")
        }
    return {"maintenance": False, "enabled": False, "message": ""}


# ==================== ADMIN: DASHBOARD STATS ====================

@router.get("/admin/dashboard/stats")
async def get_admin_dashboard_stats(user: dict = Depends(require_admin_level(30))):
    """Get comprehensive dashboard statistics"""
    # Count users
    traders_count = await db.traders.count_documents({})
    merchants_count = await db.merchants.count_documents({})
    pending_merchants = await db.merchants.count_documents({"status": "pending"})
    
    # Count trades
    total_trades = await db.trades.count_documents({})
    completed_trades = await db.trades.count_documents({"status": "completed"})
    active_trades = await db.trades.count_documents({"status": {"$in": ["pending", "paid"]}})
    disputed_trades = await db.trades.count_documents({"status": "disputed"})
    
    # Count offers
    active_offers = await db.offers.count_documents({"is_active": True})
    
    # Calculate volumes
    completed_trades_list = await db.trades.find({"status": "completed"}, {"_id": 0, "amount_usdt": 1, "amount_rub": 1}).to_list(10000)
    total_volume_usdt = sum([t.get("amount_usdt", 0) for t in completed_trades_list])
    total_volume_rub = sum([t.get("amount_rub", 0) for t in completed_trades_list])
    
    # Platform earnings (commissions)
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    
    # Shops and products
    shops_count = await db.shops.count_documents({})
    products_count = await db.products.count_documents({})
    
    # Today's stats
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    trades_today = await db.trades.count_documents({"created_at": {"$gte": today_start.isoformat()}})
    new_users_today = await db.traders.count_documents({"created_at": {"$gte": today_start.isoformat()}})
    
    return {
        "users": {
            "traders": traders_count,
            "merchants": merchants_count,
            "pending_merchants": pending_merchants
        },
        "trades": {
            "total": total_trades,
            "completed": completed_trades,
            "active": active_trades,
            "disputed": disputed_trades,
            "today": trades_today
        },
        "volume": {
            "usdt": total_volume_usdt,
            "rub": total_volume_rub
        },
        "offers": {
            "active": active_offers
        },
        "marketplace": {
            "shops": shops_count,
            "products": products_count
        },
        "today": {
            "trades": trades_today,
            "new_users": new_users_today
        },
        "settings": settings
    }
