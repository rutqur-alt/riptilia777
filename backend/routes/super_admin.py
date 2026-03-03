"""
Super Admin routes - High-level platform management
Requires admin_level >= 50-100 depending on action
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from core.database import db
from core.auth import require_role, get_current_user, hash_password

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


def require_admin_level(min_level: int = 30):
    """Check admin has sufficient permission level"""
    async def admin_checker(user: dict = Depends(get_current_user)):
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        level = {"owner": 100, "admin": 80, "mod_p2p": 50, "mod_market": 50, "support": 30}.get(user.get("admin_role", ""), 0)
        if level < min_level:
            raise HTTPException(status_code=403, detail=f"Insufficient admin level. Required: {min_level}")
        return user
    return admin_checker


async def log_admin_action(admin_id: str, action: str, target_type: str, target_id: str, details: dict = None):
    """Log administrative action"""
    log_doc = {
        "id": str(uuid.uuid4()),
        "admin_id": admin_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "details": details or {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log_doc)


@router.get("/overview")
async def get_super_admin_overview(user: dict = Depends(require_admin_level(80))):
    """Get full platform overview with financial data"""
    traders_count = await db.traders.count_documents({})
    merchants_count = await db.merchants.count_documents({})
    blocked_traders = await db.traders.count_documents({"is_blocked": True})
    blocked_merchants = await db.merchants.count_documents({"status": "blocked"})
    
    total_trades = await db.trades.count_documents({})
    active_trades = await db.trades.count_documents({"status": {"$in": ["pending", "paid"]}})
    disputed_trades = await db.trades.count_documents({"status": "disputed"})
    completed_trades_count = await db.trades.count_documents({"status": "completed"})
    
    # Get completed trades for volume calculation
    completed_trades = await db.trades.find(
        {"status": "completed"},
        {"_id": 0, "amount_usdt": 1, "client_amount_rub": 1, "amount_rub": 1, "platform_fee_rub": 1}
    ).to_list(10000)
    
    total_usdt = sum(t.get("amount_usdt", 0) or 0 for t in completed_trades)
    total_rub = sum(t.get("client_amount_rub") or t.get("amount_rub", 0) for t in completed_trades)
    
    # Get base rate from Rapira API settings
    rate_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = rate_settings.get("base_rate", 78) if rate_settings else 78
    
    # Commission in USDT = platform_fee_rub / base_rate (Rapira exchange rate)
    total_platform_fee_rub = sum(t.get("platform_fee_rub", 0) or 0 for t in completed_trades)
    total_commission_usdt = total_platform_fee_rub / base_rate if base_rate > 0 else 0
    
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_trades = await db.trades.count_documents({"created_at": {"$gte": today.isoformat()}})
    today_registrations = await db.traders.count_documents({"created_at": {"$gte": today.isoformat()}})
    
    shops_count = await db.traders.count_documents({"shop_settings.approved": True})
    products_count = await db.marketplace_products.count_documents({"is_active": True})
    pending_withdrawals = await db.withdrawals.count_documents({"status": "pending"})
    
    staff = await db.admins.find({}, {"_id": 0, "password_hash": 0, "password": 0}).to_list(50)
    maintenance = await db.system_settings.find_one({"key": "maintenance_mode"}, {"_id": 0})
    
    return {
        "users": {
            "total_traders": traders_count,
            "total_merchants": merchants_count,
            "blocked_traders": blocked_traders,
            "blocked_merchants": blocked_merchants,
            "today_registrations": today_registrations
        },
        "trades": {
            "total": total_trades,
            "active": active_trades,
            "disputed": disputed_trades,
            "completed": completed_trades_count,
            "today": today_trades
        },
        "volumes": {
            "total_usdt": round(total_usdt, 2),
            "total_rub": round(total_rub, 2),
            "total_commission": round(total_commission_usdt, 4)
        },
        "marketplace": {
            "shops": shops_count,
            "products": products_count,
            "pending_withdrawals": pending_withdrawals
        },
        "staff_count": len(staff),
        "maintenance_mode": maintenance.get("enabled", False) if maintenance else False
    }


@router.get("/notifications-count")
async def get_admin_notifications(user: dict = Depends(require_admin_level(30))):
    """Get count of pending items requiring admin attention"""
    pending_merchants = await db.merchants.count_documents({"status": "pending"})
    open_tickets = await db.support_tickets.count_documents({"status": "open"})
    
    shop_applications = await db.support_tickets.count_documents({
        "category": "shop_application",
        "is_shop_application": True,
        "shop_approved": {"$ne": True},
        "status": {"$ne": "closed"}
    })
    
    disputed_trades = await db.trades.count_documents({"status": "disputed"})
    pending_withdrawals = await db.withdrawals.count_documents({"status": "pending"})
    active_trades = await db.trades.count_documents({"status": {"$in": ["pending", "paid"]}})
    
    # Count unread messages for admin (all chats)
    messages_total = await db.unified_messages.count_documents({
        "read_by": {"$ne": user["id"]},
        "sender_id": {"$ne": user["id"]}
    })
    
    # Count unread staff messages
    staff_messages = await db.unified_messages.count_documents({
        "conversation_id": {"$regex": "^staff_"},
        "read_by": {"$ne": user["id"]},
        "sender_id": {"$ne": user["id"]}
    })
    
    return {
        "pending_merchants": pending_merchants,
        "open_tickets": open_tickets,
        "shop_applications": shop_applications,
        "disputed_trades": disputed_trades,
        "pending_withdrawals": pending_withdrawals,
        "active_trades": active_trades,
        "support_total": open_tickets + shop_applications,
        "p2p_total": disputed_trades + active_trades,
        "users_total": pending_merchants,
        "finances_total": pending_withdrawals,
        "messages_total": messages_total,
        "staff_messages": staff_messages
    }


@router.post("/maintenance")
async def toggle_maintenance_mode(data: dict = None, enabled: bool = None, message: str = "", user: dict = Depends(require_admin_level(100))):
    """Toggle maintenance mode (owner only). Accepts JSON body or query params."""
    # Support both JSON body and query params
    if data and isinstance(data, dict):
        enabled_val = data.get("enabled", enabled)
        message_val = data.get("message", message)
    else:
        enabled_val = enabled
        message_val = message
    
    if enabled_val is None:
        from fastapi import HTTPException as HE
        raise HE(status_code=400, detail="'enabled' is required")
    
    await db.system_settings.update_one(
        {"key": "maintenance_mode"},
        {"$set": {
            "key": "maintenance_mode",
            "enabled": enabled_val,
            "message": message_val,
            "updated_by": user["id"],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    await log_admin_action(user["id"], "toggle_maintenance", "system", "maintenance_mode", {"enabled": enabled_val})
    return {"status": "success", "maintenance_mode": enabled_val}


@router.get("/maintenance")
async def get_maintenance_status(user: dict = Depends(require_admin_level(30))):
    """Get maintenance mode status"""
    maintenance = await db.system_settings.find_one({"key": "maintenance_mode"}, {"_id": 0})
    return maintenance or {"enabled": False, "message": ""}


@router.get("/users")
async def get_all_users_detailed(
    user_type: str = "all",
    status: str = "all",
    search: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    user: dict = Depends(require_admin_level(50))
):
    """Get all users with full details"""
    results = []
    
    if user_type in ["all", "traders"]:
        query = {}
        if status == "blocked":
            query["is_blocked"] = True
        elif status == "active":
            query["is_blocked"] = {"$ne": True}
        if search:
            query["$or"] = [
                {"login": {"$regex": search, "$options": "i"}},
                {"nickname": {"$regex": search, "$options": "i"}}
            ]
        
        traders = await db.traders.find(query, {"_id": 0, "password_hash": 0, "password": 0}).skip(skip).limit(limit).to_list(limit)
        for t in traders:
            t["user_type"] = "trader"
            t["status"] = "blocked" if t.get("is_blocked") else "active"
            t["trades_count"] = await db.trades.count_documents({"trader_id": t["id"]})
            results.append(t)
    
    if user_type in ["all", "merchants"]:
        query = {}
        if status == "blocked":
            query["status"] = "blocked"
        elif status == "active":
            query["status"] = {"$in": ["approved", "active"]}
        if search:
            query["$or"] = [
                {"login": {"$regex": search, "$options": "i"}},
                {"merchant_name": {"$regex": search, "$options": "i"}}
            ]
        
        merchants = await db.merchants.find(query, {"_id": 0, "password_hash": 0, "password": 0}).skip(skip).limit(limit).to_list(limit)
        for m in merchants:
            m["user_type"] = "merchant"
            results.append(m)
    
    if user_type in ["all", "staff"]:
        staff = await db.admins.find({}, {"_id": 0, "password_hash": 0, "password": 0}).to_list(50)
        for s in staff:
            s["user_type"] = "staff"
            s["status"] = "active"
            results.append(s)
    
    return results


@router.post("/users/{user_id}/ban")
async def ban_user(user_id: str, data: dict = None, user: dict = Depends(require_admin_level(50))):
    """Ban/unban user. Accepts JSON body with banned, reason, duration_hours."""
    if not data:
        data = {}
    banned = data.get("banned", True)
    reason = data.get("reason", "")
    duration_hours = data.get("duration_hours")
    trader = await db.traders.find_one({"id": user_id})
    if trader:
        ban_until = None
        if banned and duration_hours:
            ban_until = (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).isoformat()
        
        await db.traders.update_one(
            {"id": user_id},
            {"$set": {
                "is_blocked": banned,
                "block_reason": reason,
                "ban_until": ban_until,
                "blocked_by": user["id"],
                "blocked_at": datetime.now(timezone.utc).isoformat() if banned else None
            }}
        )
        
        await log_admin_action(user["id"], "ban_user" if banned else "unban_user", "trader", user_id, {"reason": reason})
        return {"status": "success"}
    
    merchant = await db.merchants.find_one({"id": user_id})
    if merchant:
        new_status = "blocked" if banned else "approved"
        await db.merchants.update_one(
            {"id": user_id},
            {"$set": {"status": new_status, "block_reason": reason, "blocked_by": user["id"]}}
        )
        
        await log_admin_action(user["id"], "ban_merchant" if banned else "unban_merchant", "merchant", user_id, {"reason": reason})
        return {"status": "success"}
    
    raise HTTPException(status_code=404, detail="User not found")


@router.post("/users/{user_id}/balance")
async def adjust_user_balance(user_id: str, data: dict = None, user: dict = Depends(require_admin_level(80))):
    """Adjust user balance. Accepts JSON body with amount, reason."""
    if not data:
        data = {}
    amount = data.get("amount", 0)
    reason = data.get("reason", "")
    if not amount:
        raise HTTPException(status_code=400, detail="Amount is required")
    trader = await db.traders.find_one({"id": user_id})
    if trader:
        new_balance = trader.get("balance_usdt", 0) + amount
        if new_balance < 0:
            raise HTTPException(status_code=400, detail="Resulting balance cannot be negative")
        
        await db.traders.update_one({"id": user_id}, {"$inc": {"balance_usdt": amount}})
        
        tx_doc = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": "admin_adjustment",
            "amount": amount,
            "reason": reason,
            "adjusted_by": user["id"],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.transactions.insert_one(tx_doc)
        
        await log_admin_action(user["id"], "adjust_balance", "trader", user_id, {"amount": amount, "reason": reason})
        return {"status": "success", "new_balance": new_balance}
    
    merchant = await db.merchants.find_one({"id": user_id})
    if merchant:
        new_balance = merchant.get("balance_usdt", 0) + amount
        if new_balance < 0:
            raise HTTPException(status_code=400, detail="Resulting balance cannot be negative")
        
        await db.merchants.update_one({"id": user_id}, {"$inc": {"balance_usdt": amount}})
        await log_admin_action(user["id"], "adjust_balance", "merchant", user_id, {"amount": amount, "reason": reason})
        return {"status": "success", "new_balance": new_balance}
    
    raise HTTPException(status_code=404, detail="User not found")


@router.get("/users/{user_id}/stats")
async def get_user_stats(user_id: str, user: dict = Depends(require_admin_level(50))):
    """Get detailed user stats for admin view"""
    # Try traders first
    trader = await db.traders.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "password": 0})
    if trader:
        trades_as_seller = await db.trades.find({"seller_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(10).to_list(10)
        trades_as_buyer = await db.trades.find({"buyer_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(10).to_list(10)
        all_trades = trades_as_seller + trades_as_buyer
        completed = [t for t in all_trades if t.get("status") == "completed"]
        vol_usdt = sum(t.get("amount", 0) for t in completed)
        vol_rub = sum(t.get("total_rub", 0) for t in completed)
        referral_count = await db.traders.count_documents({"referred_by": user_id})
        referral_count += await db.merchants.count_documents({"referred_by": user_id})
        
        return {
            "user": trader,
            "user_type": "trader",
            "trader": {
                "total_trades": len(all_trades),
                "completed_trades": len(completed),
                "volume_usdt": round(vol_usdt, 2),
                "volume_rub": round(vol_rub, 2)
            },
            "referrals": {
                "total_referrals": referral_count,
                "referral_earnings": trader.get("referral_earnings", 0)
            },
            "recent_trades": [{"id": t.get("id"), "amount_usdt": t.get("amount", 0), "amount_rub": t.get("total_rub", 0), "status": t.get("status")} for t in all_trades[:10]]
        }
    
    # Try merchants
    merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "password": 0})
    if merchant:
        payments = await db.merchant_payments.find({"merchant_id": user_id, "status": "completed"}, {"_id": 0}).to_list(200)
        vol_usdt = sum(p.get("amount_usdt", 0) for p in payments)
        vol_rub = sum(p.get("amount_rub", 0) for p in payments)
        referral_count = await db.traders.count_documents({"referred_by": user_id})
        referral_count += await db.merchants.count_documents({"referred_by": user_id})
        
        return {
            "user": merchant,
            "user_type": "merchant",
            "merchant": {
                "completed_payments": len(payments),
                "volume_usdt": round(vol_usdt, 2),
                "volume_rub": round(vol_rub, 2)
            },
            "referrals": {
                "total_referrals": referral_count,
                "referral_earnings": merchant.get("referral_earnings", 0)
            }
        }
    
    raise HTTPException(status_code=404, detail="Пользователь не найден")


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, data: dict = None, user: dict = Depends(require_admin_level(80))):
    """Reset user password (admin only)"""
    if not data:
        data = {}
    new_password = data.get("new_password", "")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть минимум 6 символов")
    
    new_hash = hash_password(new_password)
    
    trader = await db.traders.find_one({"id": user_id})
    if trader:
        await db.traders.update_one({"id": user_id}, {"$set": {"password_hash": new_hash, "password": new_hash}})
        await log_admin_action(user["id"], "reset_password", "trader", user_id, {})
        return {"status": "success"}
    
    merchant = await db.merchants.find_one({"id": user_id})
    if merchant:
        await db.merchants.update_one({"id": user_id}, {"$set": {"password_hash": new_hash, "password": new_hash}})
        await log_admin_action(user["id"], "reset_password", "merchant", user_id, {})
        return {"status": "success"}
    
    raise HTTPException(status_code=404, detail="Пользователь не найден")


@router.post("/users/{user_id}/toggle-balance-lock")
async def toggle_balance_lock(user_id: str, user: dict = Depends(require_admin_level(80))):
    """Lock/unlock user balance"""
    trader = await db.traders.find_one({"id": user_id})
    if trader:
        current = trader.get("balance_locked", False)
        await db.traders.update_one({"id": user_id}, {"$set": {"balance_locked": not current}})
        await log_admin_action(user["id"], "toggle_balance_lock", "trader", user_id, {"locked": not current})
        return {"status": "success", "locked": not current}
    
    merchant = await db.merchants.find_one({"id": user_id})
    if merchant:
        current = merchant.get("balance_locked", False)
        await db.merchants.update_one({"id": user_id}, {"$set": {"balance_locked": not current}})
        await log_admin_action(user["id"], "toggle_balance_lock", "merchant", user_id, {"locked": not current})
        return {"status": "success", "locked": not current}
    
    raise HTTPException(status_code=404, detail="Пользователь не найден")


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_admin_level(100))):
    """Delete user permanently (owner only)"""
    trader = await db.traders.find_one({"id": user_id})
    if trader:
        await db.traders.delete_one({"id": user_id})
        await db.offers.delete_many({"trader_id": user_id})
        await db.transactions.delete_many({"user_id": user_id})
        await log_admin_action(user["id"], "delete_user", "trader", user_id, {"login": trader.get("login")})
        return {"status": "deleted"}
    
    merchant = await db.merchants.find_one({"id": user_id})
    if merchant:
        await db.merchants.delete_one({"id": user_id})
        await log_admin_action(user["id"], "delete_user", "merchant", user_id, {"login": merchant.get("login")})
        return {"status": "deleted"}
    
    raise HTTPException(status_code=404, detail="Пользователь не найден")


@router.get("/users/{user_id}/history")
async def get_user_history(user_id: str, user: dict = Depends(require_admin_level(50))):
    """Get full user activity history"""
    logins = await db.login_history.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    trades_seller = await db.trades.find({"trader_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    trades_buyer = await db.trades.find({"buyer_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    offers = await db.offers.find({"trader_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    purchases = await db.marketplace_purchases.find({"buyer_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    admin_actions = await db.admin_logs.find({"target_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    
    return {
        "logins": logins,
        "trades_as_seller": trades_seller,
        "trades_as_buyer": trades_buyer,
        "offers": offers,
        "marketplace_purchases": purchases,
        "admin_actions": admin_actions
    }


@router.get("/staff")
async def get_staff_list(user: dict = Depends(require_admin_level(80))):
    """Get all staff members"""
    staff = await db.admins.find({}, {"_id": 0, "password_hash": 0, "password": 0}).to_list(50)
    
    for s in staff:
        s["actions_count"] = await db.admin_logs.count_documents({"admin_id": s["id"]})
        last_action = await db.admin_logs.find_one({"admin_id": s["id"]}, {"_id": 0}, sort=[("created_at", -1)])
        s["last_action"] = last_action
    
    return staff


ADMIN_ROLES = {"owner": 100, "admin": 80, "mod_p2p": 50, "mod_market": 50, "support": 30}


@router.post("/staff/create")
async def create_staff_member(data: dict, user: dict = Depends(require_admin_level(100))):
    """Create new staff member (owner only)"""
    login = data.get("login")
    password = data.get("password")
    admin_role = data.get("role", "support")
    nickname = data.get("nickname", login)

    if not login or not password:
        raise HTTPException(status_code=400, detail="Login and password required")

    if admin_role not in ADMIN_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {list(ADMIN_ROLES.keys())}")

    existing = await db.admins.find_one({"login": login})
    if existing:
        raise HTTPException(status_code=400, detail="Login already exists")

    staff_doc = {
        "id": str(uuid.uuid4()),
        "login": login,
        "nickname": nickname,
        "password_hash": hash_password(password),
        "role": "admin",
        "admin_role": admin_role,
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True
    }

    await db.admins.insert_one(staff_doc)
    await log_admin_action(user["id"], "create_staff", "admin", staff_doc["id"], {"login": login, "role": admin_role})

    return {"status": "success", "id": staff_doc["id"]}


@router.delete("/staff/{staff_id}")
async def delete_staff_member(staff_id: str, user: dict = Depends(require_admin_level(100))):
    """Delete staff member (owner only)"""
    staff = await db.admins.find_one({"id": staff_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    if staff.get("admin_role") == "owner":
        raise HTTPException(status_code=403, detail="Cannot delete owner")

    await db.admins.delete_one({"id": staff_id})
    await log_admin_action(user["id"], "delete_staff", "admin", staff_id, {"login": staff.get("login")})

    return {"status": "deleted"}


@router.get("/finances")
async def get_finances_overview(period: str = "7d", user: dict = Depends(require_admin_level(80))):
    """Get financial overview"""
    days = {"1d": 1, "7d": 7, "30d": 30, "90d": 90, "all": 3650}
    period_days = days.get(period, 7)
    start_date = datetime.now(timezone.utc) - timedelta(days=period_days)
    
    # Get completed trades for the period
    completed_trades = await db.trades.find(
        {"status": "completed", "created_at": {"$gte": start_date.isoformat()}},
        {"_id": 0, "amount_usdt": 1, "client_amount_rub": 1, "amount_rub": 1, "platform_fee_rub": 1}
    ).to_list(10000)
    
    total_volume_usdt = sum(t.get("amount_usdt", 0) or 0 for t in completed_trades)
    total_volume_rub = sum(t.get("client_amount_rub") or t.get("amount_rub", 0) for t in completed_trades)
    
    # Get base rate from Rapira API settings
    rate_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = rate_settings.get("base_rate", 78) if rate_settings else 78
    
    # Commission in USDT = platform_fee_rub / base_rate (Rapira exchange rate)
    total_platform_fee_rub = sum(t.get("platform_fee_rub", 0) or 0 for t in completed_trades)
    total_commission_usdt = total_platform_fee_rub / base_rate if base_rate > 0 else 0
    
    trade_count = len(completed_trades)
    
    traders_balance = 0
    merchants_balance = 0
    
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$balance_usdt"}}}]
    t_result = await db.traders.aggregate(pipeline).to_list(1)
    if t_result:
        traders_balance = t_result[0].get("total", 0)
    
    m_result = await db.merchants.aggregate(pipeline).to_list(1)
    if m_result:
        merchants_balance = m_result[0].get("total", 0)
    
    return {
        "period": period,
        "commission_earned": round(total_commission_usdt, 4),
        "volume_usdt": round(total_volume_usdt, 2),
        "volume_rub": round(total_volume_rub, 2),
        "trade_count": trade_count,
        "traders_total_balance": round(traders_balance, 2),
        "merchants_total_balance": round(merchants_balance, 2),
        "platform_total_funds": round(traders_balance + merchants_balance, 2)
    }


@router.get("/activity-log")
async def get_activity_log(limit: int = 100, user: dict = Depends(require_admin_level(50))):
    """Get recent admin activity logs"""
    logs = await db.admin_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return logs


# ==================== MODERATION ====================

@router.get("/moderation/chats")
async def get_chats_for_moderation(
    search: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(require_admin_level(50))
):
    """Get private chats for moderation"""
    query = {}
    if search:
        query["participant_nicknames"] = {"$regex": search, "$options": "i"}
    
    conversations = await db.conversations.find(query, {"_id": 0}).sort("last_message_at", -1).limit(limit).to_list(limit)
    
    # Get last messages
    for conv in conversations:
        last_msg = await db.private_messages.find_one(
            {"conversation_id": conv["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        conv["last_message"] = last_msg
        conv["message_count"] = await db.private_messages.count_documents({"conversation_id": conv["id"]})
    
    return conversations


@router.delete("/moderation/chats/{conversation_id}")
async def delete_conversation_admin(conversation_id: str, user: dict = Depends(require_admin_level(50))):
    """Delete a conversation and all messages"""
    await db.private_messages.delete_many({"conversation_id": conversation_id})
    await db.conversations.delete_one({"id": conversation_id})
    
    await log_admin_action(user["id"], "delete_conversation", "conversation", conversation_id, {})
    
    return {"status": "success"}


@router.delete("/moderation/messages/{message_id}")
async def delete_message_admin(message_id: str, user: dict = Depends(require_admin_level(50))):
    """Delete a single message"""
    msg = await db.private_messages.find_one({"id": message_id})
    if not msg:
        msg = await db.forum_messages.find_one({"id": message_id})
        if msg:
            await db.forum_messages.delete_one({"id": message_id})
        else:
            raise HTTPException(status_code=404, detail="Message not found")
    else:
        await db.private_messages.delete_one({"id": message_id})
    
    await log_admin_action(user["id"], "delete_message", "message", message_id, {})
    
    return {"status": "success"}


# ==================== COMMISSIONS ====================

@router.get("/commissions/all")
async def get_all_commission_settings(user: dict = Depends(require_admin_level(80))):
    """Get all commission settings"""
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {
            "trader_commission": 5.0,
            "casino_commission": 3.0,
            "shop_commission": 5.0,
            "stream_commission": 5.0,
            "other_commission": 5.0,
            "minimum_commission": 0.01,
            "guarantor_commission_percent": 3.0,
            "guarantor_auto_complete_days": 14
        }
    
    return settings


@router.put("/commissions/update")
async def update_all_commissions(data: dict, user: dict = Depends(require_admin_level(100))):
    """Update commission settings (owner only)"""
    allowed_keys = [
        "trader_commission", "casino_commission", "shop_commission", 
        "stream_commission", "other_commission", "minimum_commission",
        "guarantor_commission_percent", "guarantor_auto_complete_days"
    ]
    
    update_data = {k: v for k, v in data.items() if k in allowed_keys}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = user["id"]
    
    await db.commission_settings.update_one({}, {"$set": update_data}, upsert=True)
    
    await log_admin_action(user["id"], "update_commissions", "system", "commissions", update_data)
    
    return await get_all_commission_settings(user)


@router.put("/users/{user_id}/commission")
async def update_user_commission(user_id: str, data: dict, user: dict = Depends(require_admin_level(80))):
    """Set individual user commission rate"""
    commission_rate = data.get("commission_rate")
    if commission_rate is None:
        raise HTTPException(status_code=400, detail="commission_rate is required")
    
    # Try traders
    result = await db.traders.update_one(
        {"id": user_id},
        {"$set": {"commission_rate": commission_rate}}
    )
    if result.modified_count:
        await log_admin_action(user["id"], "update_user_commission", "trader", user_id, {"rate": commission_rate})
        return {"status": "success"}
    
    # Try merchants
    result = await db.merchants.update_one(
        {"id": user_id},
        {"$set": {"commission_rate": commission_rate}}
    )
    if result.modified_count:
        await log_admin_action(user["id"], "update_user_commission", "merchant", user_id, {"rate": commission_rate})
        return {"status": "success"}
    
    raise HTTPException(status_code=404, detail="User not found")


# ==================== DISPUTES ====================

@router.get("/disputes/all")
async def get_all_disputes_detailed(
    status: str = "all",
    user: dict = Depends(require_admin_level(50))
):
    """Get all disputes with full details"""
    query = {}
    if status != "all":
        query["status"] = status
    else:
        query["status"] = "disputed"
    
    trades = await db.trades.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    for trade in trades:
        # Get seller info
        seller = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0, "login": 1, "nickname": 1})
        trade["seller_info"] = seller
        
        # Get buyer info
        if trade.get("buyer_id"):
            buyer = await db.traders.find_one({"id": trade["buyer_id"]}, {"_id": 0, "login": 1, "nickname": 1})
            trade["buyer_info"] = buyer
        
        # Get messages
        trade["messages"] = await db.trade_messages.find({"trade_id": trade["id"]}, {"_id": 0}).sort("created_at", 1).to_list(100)
    
    return trades
