from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import require_admin_level, log_admin_action, hash_password
from .models import PasswordReset, BalanceFreeze, AdminMessage
from .utils import get_msg_role_info

router = APIRouter()

# ==================== GET ALL USERS ====================

@router.get("/super-admin/users")
async def get_all_users(user_type: str = "all", limit: int = 200, user: dict = Depends(require_admin_level(30))):
    """Get all users for admin panel"""
    users = []
    
    if user_type in ["all", "traders"]:
        traders = await db.traders.find(
            {}, 
            {"_id": 0, "password_hash": 0, "password": 0}
        ).limit(limit).to_list(limit)
        for t in traders:
            t["user_type"] = "trader"
        users.extend(traders)
    
    if user_type in ["all", "merchants"]:
        merchants = await db.merchants.find(
            {},
            {"_id": 0, "password_hash": 0, "password": 0}
        ).limit(limit).to_list(limit)
        for m in merchants:
            m["user_type"] = "merchant"
        users.extend(merchants)
    
    if user_type in ["all", "staff"]:
        staff = await db.admins.find(
            {"login": {"$ne": "admin"}},  # Exclude main admin
            {"_id": 0, "password_hash": 0, "password": 0}
        ).limit(limit).to_list(limit)
        for s in staff:
            s["user_type"] = "staff"
            s["balance_usdt"] = 0  # Staff don't have balance
        users.extend(staff)
    
    return users


# ==================== ADMIN: USERS/TRADERS ====================

@router.get("/admin/users/traders")
async def get_all_traders_admin(
    skip: int = 0, 
    limit: int = 50,
    search: str = None,
    status: str = None,
    user: dict = Depends(require_admin_level(30))
):
    """Get all traders with admin info"""
    query = {}
    if search:
        query["$or"] = [
            {"login": {"$regex": search, "$options": "i"}},
            {"nickname": {"$regex": search, "$options": "i"}}
        ]
    if status == "blocked":
        query["is_blocked"] = True
    elif status == "active":
        query["is_blocked"] = {"$ne": True}
    
    traders = await db.traders.find(query, {"_id": 0, "password_hash": 0, "password": 0}).skip(skip).limit(limit).to_list(limit)
    total = await db.traders.count_documents(query)
    
    return {"traders": traders, "total": total}


@router.get("/admin/users/traders/{trader_id}")
async def get_trader_details_admin(trader_id: str, user: dict = Depends(require_admin_level(30))):
    """Get detailed trader info including history"""
    trader = await db.traders.find_one({"id": trader_id}, {"_id": 0, "password_hash": 0, "password": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    
    # Get recent trades
    trades = await db.trades.find(
        {"$or": [{"trader_id": trader_id}, {"buyer_id": trader_id}]},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Get offers
    offers = await db.offers.find({"trader_id": trader_id}, {"_id": 0}).to_list(100)
    
    # Get requisites
    requisites = await db.requisites.find({"trader_id": trader_id}, {"_id": 0}).to_list(50)
    
    return {
        "trader": trader,
        "trades": trades,
        "offers": offers,
        "requisites": requisites
    }


@router.post("/admin/users/traders/{trader_id}/block")
async def block_trader(trader_id: str, data: dict, user: dict = Depends(require_admin_level(50))):
    """Block/unblock a trader"""
    block = data.get("block", True)
    reason = data.get("reason", "")
    
    await db.traders.update_one(
        {"id": trader_id},
        {"$set": {"is_blocked": block, "block_reason": reason, "blocked_at": datetime.now(timezone.utc).isoformat() if block else None, "blocked_by": user["id"] if block else None}}
    )
    
    await log_admin_action(user["id"], "block_trader" if block else "unblock_trader", "trader", trader_id, {"reason": reason})
    
    return {"status": "success", "blocked": block}


@router.post("/admin/users/traders/{trader_id}/edit")
async def edit_trader_admin(trader_id: str, data: dict, user: dict = Depends(require_admin_level(80))):
    """Edit trader data"""
    allowed_fields = ["balance_usdt", "commission_rate", "nickname", "display_name"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    await db.traders.update_one({"id": trader_id}, {"$set": update_data})
    
    await log_admin_action(user["id"], "edit_trader", "trader", trader_id, update_data)
    
    return {"status": "success"}


# ==================== ADMIN: USERS/MERCHANTS ====================

@router.get("/admin/users/merchants")
async def get_all_merchants_admin(
    skip: int = 0,
    limit: int = 50,
    search: str = None,
    status: str = None,
    user: dict = Depends(require_admin_level(30))
):
    """Get all merchants with admin info"""
    query = {}
    if search:
        query["$or"] = [
            {"login": {"$regex": search, "$options": "i"}},
            {"merchant_name": {"$regex": search, "$options": "i"}}
        ]
    if status:
        query["status"] = status
    
    merchants = await db.merchants.find(query, {"_id": 0, "password_hash": 0, "password": 0}).skip(skip).limit(limit).to_list(limit)
    total = await db.merchants.count_documents(query)
    
    return {"merchants": merchants, "total": total}


@router.post("/admin/users/merchants/{merchant_id}/edit")
async def edit_merchant_admin(merchant_id: str, data: dict, user: dict = Depends(require_admin_level(80))):
    """Edit merchant data"""
    allowed_fields = ["balance_usdt", "commission_rate", "merchant_name", "status"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    await db.merchants.update_one({"id": merchant_id}, {"$set": update_data})
    
    await log_admin_action(user["id"], "edit_merchant", "merchant", merchant_id, update_data)
    
    return {"status": "success"}


# ==================== BAN/UNBAN USER ====================

@router.post("/super-admin/users/{user_id}/ban")
async def ban_unban_user(user_id: str, data: dict, user: dict = Depends(require_admin_level(50))):
    """Ban or unban a user"""
    banned = data.get("banned", True)
    reason = data.get("reason", "")
    now = datetime.now(timezone.utc).isoformat()
    
    update_data = {
        "is_blocked": banned,
        "blocked_reason": reason if banned else None,
        "blocked_at": now if banned else None,
        "blocked_by": user["id"] if banned else None
    }
    
    # Try traders
    result = await db.traders.update_one({"id": user_id}, {"$set": update_data})
    if result.modified_count:
        action = "ban_user" if banned else "unban_user"
        await log_admin_action(user["id"], action, "trader", user_id, {"reason": reason})
        return {"status": "success", "banned": banned}
    
    # Try merchants
    result = await db.merchants.update_one({"id": user_id}, {"$set": update_data})
    if result.modified_count:
        action = "ban_user" if banned else "unban_user"
        await log_admin_action(user["id"], action, "merchant", user_id, {"reason": reason})
        return {"status": "success", "banned": banned}
    
    raise HTTPException(status_code=404, detail="Пользователь не найден")


# ==================== ADJUST BALANCE ====================

@router.post("/super-admin/users/{user_id}/balance")
async def adjust_user_balance(user_id: str, data: dict, user: dict = Depends(require_admin_level(80))):
    """Adjust user balance (add or subtract)"""
    amount = data.get("amount", 0)
    reason = data.get("reason", "Admin adjustment")
    now = datetime.now(timezone.utc).isoformat()
    
    if amount == 0:
        raise HTTPException(status_code=400, detail="Сумма не может быть 0")
    
    # Try traders
    trader = await db.traders.find_one({"id": user_id})
    if trader:
        new_balance = trader.get("balance_usdt", 0) + amount
        if new_balance < 0:
            raise HTTPException(status_code=400, detail="Недостаточно средств")
        
        await db.traders.update_one(
            {"id": user_id},
            {"$set": {"balance_usdt": new_balance}}
        )
        
        # Log transaction
        await db.balance_adjustments.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "user_type": "trader",
            "amount": amount,
            "reason": reason,
            "admin_id": user["id"],
            "created_at": now
        })
        
        await log_admin_action(user["id"], "adjust_balance", "trader", user_id, {"amount": amount, "reason": reason})
        return {"status": "success", "new_balance": new_balance}
    
    # Try merchants
    merchant = await db.merchants.find_one({"id": user_id})
    if merchant:
        new_balance = merchant.get("balance_usdt", 0) + amount
        if new_balance < 0:
            raise HTTPException(status_code=400, detail="Недостаточно средств")
        
        await db.merchants.update_one(
            {"id": user_id},
            {"$set": {"balance_usdt": new_balance}}
        )
        
        await db.balance_adjustments.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "user_type": "merchant",
            "amount": amount,
            "reason": reason,
            "admin_id": user["id"],
            "created_at": now
        })
        
        await log_admin_action(user["id"], "adjust_balance", "merchant", user_id, {"amount": amount, "reason": reason})
        return {"status": "success", "new_balance": new_balance}
    
    raise HTTPException(status_code=404, detail="Пользователь не найден")


# ==================== PASSWORD RESET ====================

@router.post("/super-admin/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, data: PasswordReset, user: dict = Depends(require_admin_level(80))):
    """Reset user password (admin only)"""
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть минимум 6 символов")
    
    new_hash = hash_password(data.new_password)
    
    # Try traders
    result = await db.traders.update_one(
        {"id": user_id},
        {"$set": {"password_hash": new_hash}}
    )
    if result.modified_count:
        await log_admin_action(user["id"], "reset_password", "trader", user_id, {})
        return {"status": "success", "message": "Пароль сброшен"}
    
    # Try merchants
    result = await db.merchants.update_one(
        {"id": user_id},
        {"$set": {"password_hash": new_hash}}
    )
    if result.modified_count:
        await log_admin_action(user["id"], "reset_password", "merchant", user_id, {})
        return {"status": "success", "message": "Пароль сброшен"}
    
    raise HTTPException(status_code=404, detail="Пользователь не найден")


# ==================== USER DETAILED STATS ====================

@router.get("/super-admin/users/{user_id}/stats")
async def get_user_detailed_stats(user_id: str, user: dict = Depends(require_admin_level(30))):
    """Get detailed statistics for a user"""
    # Find user
    trader = await db.traders.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "password": 0})
    merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "password": 0}) if not trader else None
    
    if not trader and not merchant:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    target_user = trader or merchant
    user_type = "trader" if trader else "merchant"
    
    stats = {
        "user": target_user,
        "user_type": user_type
    }
    
    if user_type == "trader":
        # P2P Stats
        stats["p2p"] = {
            "total_offers": await db.offers.count_documents({"trader_id": user_id}),
            "active_offers": await db.offers.count_documents({"trader_id": user_id, "is_active": True}),
            "total_sales": await db.trades.count_documents({"trader_id": user_id, "status": "completed"}),
            "total_purchases": await db.trades.count_documents({"buyer_id": user_id, "status": "completed"}),
        }
        
        # Calculate volumes
        sales_pipeline = [
            {"$match": {"trader_id": user_id, "status": "completed"}},
            {"$group": {"_id": None, "total_usdt": {"$sum": "$amount_usdt"}, "total_rub": {"$sum": "$amount_rub"}}}
        ]
        purchases_pipeline = [
            {"$match": {"buyer_id": user_id, "status": "completed"}},
            {"$group": {"_id": None, "total_usdt": {"$sum": "$amount_usdt"}, "total_rub": {"$sum": "$amount_rub"}}}
        ]
        
        sales_result = await db.trades.aggregate(sales_pipeline).to_list(1)
        purchases_result = await db.trades.aggregate(purchases_pipeline).to_list(1)
        
        stats["p2p"]["sales_volume_usdt"] = round(sales_result[0]["total_usdt"], 2) if sales_result else 0
        stats["p2p"]["sales_volume_rub"] = round(sales_result[0]["total_rub"], 2) if sales_result else 0
        stats["p2p"]["purchases_volume_usdt"] = round(purchases_result[0]["total_usdt"], 2) if purchases_result else 0
        stats["p2p"]["purchases_volume_rub"] = round(purchases_result[0]["total_rub"], 2) if purchases_result else 0
        
        # Shop stats if has shop
        if trader.get("has_shop"):
            stats["shop"] = {
                "shop_name": trader.get("shop_settings", {}).get("shop_name", ""),
                "shop_balance": trader.get("shop_balance", 0),
                "total_products": await db.marketplace_products.count_documents({"seller_id": user_id}),
                "active_products": await db.marketplace_products.count_documents({"seller_id": user_id, "is_active": True}),
                "total_orders": await db.marketplace_purchases.count_documents({"seller_id": user_id}),
                "completed_orders": await db.marketplace_purchases.count_documents({"seller_id": user_id, "status": {"$in": ["completed", "delivered"]}})
            }
            
            # Shop sales volume
            shop_pipeline = [
                {"$match": {"seller_id": user_id, "status": {"$in": ["completed", "delivered"]}}},
                {"$group": {"_id": None, "total": {"$sum": "$total_price"}}}
            ]
            shop_result = await db.marketplace_purchases.aggregate(shop_pipeline).to_list(1)
            stats["shop"]["total_sales_volume"] = round(shop_result[0]["total"], 2) if shop_result else 0
        
        # Guarantor stats
        stats["guarantor"] = {
            "as_seller": await db.guarantor_deals.count_documents({"seller_id": user_id}),
            "as_buyer": await db.guarantor_deals.count_documents({"buyer_id": user_id}),
            "completed": await db.guarantor_deals.count_documents({
                "$or": [{"seller_id": user_id}, {"buyer_id": user_id}],
                "status": "completed"
            })
        }
        
        # Referral stats
        stats["referrals"] = {
            "total_referrals": await db.traders.count_documents({"referred_by": user_id}),
            "referral_earnings": trader.get("referral_earnings", 0)
        }
        
    else:  # Merchant
        stats["merchant"] = {
            "total_payments": await db.payment_requests.count_documents({"merchant_id": user_id}),
            "completed_payments": await db.payment_requests.count_documents({"merchant_id": user_id, "status": "completed"}),
            "pending_payments": await db.payment_requests.count_documents({"merchant_id": user_id, "status": "pending"})
        }
        
        # Volume
        merchant_pipeline = [
            {"$match": {"merchant_id": user_id, "status": "completed"}},
            {"$group": {"_id": None, "total_usdt": {"$sum": "$amount_usdt"}, "total_rub": {"$sum": "$amount_rub"}}}
        ]
        merchant_result = await db.payment_requests.aggregate(merchant_pipeline).to_list(1)
        stats["merchant"]["volume_usdt"] = round(merchant_result[0]["total_usdt"], 2) if merchant_result else 0
        stats["merchant"]["volume_rub"] = round(merchant_result[0]["total_rub"], 2) if merchant_result else 0
    
    # Recent activity
    stats["recent_trades"] = await db.trades.find(
        {"$or": [{"trader_id": user_id}, {"buyer_id": user_id}]},
        {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    # Support tickets
    stats["support_tickets"] = await db.support_tickets.count_documents({"user_id": user_id})
    
    # Admin actions on this user
    stats["admin_actions"] = await db.admin_logs.find(
        {"target_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    return stats


# ==================== BALANCE FREEZE/UNFREEZE ====================

@router.post("/admin/user/{user_id}/freeze-funds")
async def freeze_user_funds(
    user_id: str,
    data: BalanceFreeze,
    user: dict = Depends(require_admin_level(80))
):
    """Freeze user's funds for specified hours (admin only)"""
    reason = data.reason
    hours = 24  # Default or from data if extended
    
    target_user = await db.traders.find_one({"id": user_id}, {"_id": 0})
    collection = "traders"
    if not target_user:
        target_user = await db.merchants.find_one({"id": user_id}, {"_id": 0})
        collection = "merchants"
    
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if target_user.get("funds_frozen"):
        raise HTTPException(status_code=400, detail="Средства уже заморожены")
    
    freeze_until = datetime.now(timezone.utc) + timedelta(hours=hours)
    
    db_collection = db.traders if collection == "traders" else db.merchants
    await db_collection.update_one(
        {"id": user_id},
        {"$set": {
            "funds_frozen": True,
            "freeze_until": freeze_until.isoformat(),
            "freeze_reason": reason,
            "frozen_by": user["id"],
            "frozen_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    await log_admin_action(user["id"], "freeze_funds", collection, user_id, {"hours": hours, "reason": reason})
    
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "funds_frozen",
        "title": "Средства заморожены",
        "message": f"Ваши средства заморожены на {hours} часов. Причина: {reason}. Разморозка: {freeze_until.strftime('%d.%m.%Y %H:%M')}",
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"status": "frozen", "freeze_until": freeze_until.isoformat()}


@router.post("/admin/user/{user_id}/unfreeze-funds")
async def unfreeze_user_funds(user_id: str, user: dict = Depends(require_admin_level(80))):
    """Unfreeze user's funds (admin only)"""
    target_user = await db.traders.find_one({"id": user_id}, {"_id": 0})
    collection = "traders"
    if not target_user:
        target_user = await db.merchants.find_one({"id": user_id}, {"_id": 0})
        collection = "merchants"
    
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if not target_user.get("funds_frozen"):
        raise HTTPException(status_code=400, detail="Средства не заморожены")
    
    db_collection = db.traders if collection == "traders" else db.merchants
    await db_collection.update_one(
        {"id": user_id},
        {"$unset": {"funds_frozen": "", "freeze_until": "", "freeze_reason": "", "frozen_by": "", "frozen_at": ""}}
    )
    
    await log_admin_action(user["id"], "unfreeze_funds", collection, user_id, {})
    
    return {"status": "unfrozen"}


# ==================== ADMIN SEND MESSAGE TO USER ====================

@router.post("/super-admin/users/{user_id}/message")
async def admin_send_message_to_user(user_id: str, data: AdminMessage, user: dict = Depends(require_admin_level(50))):
    """Admin sends a private message to user"""
    # Find admin's trader account or create conversation directly
    admin_info = await db.admins.find_one({"id": user["id"]}, {"_id": 0, "login": 1})
    admin_nickname = admin_info.get("login", "Администратор") if admin_info else "Администратор"
    
    # Find target user
    target_trader = await db.traders.find_one({"id": user_id}, {"_id": 0, "id": 1, "nickname": 1, "login": 1})
    target_merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0, "id": 1, "nickname": 1, "login": 1}) if not target_trader else None
    
    target = target_trader or target_merchant
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    target_nickname = target.get("nickname", target.get("login", ""))
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Find or create conversation
    conversation_id = f"admin_conv_{user_id}"
    
    conversation = await db.conversations.find_one({"id": conversation_id})
    if not conversation:
        conversation = {
            "id": conversation_id,
            "participant_ids": ["admin", user_id],
            "participant_nicknames": ["Администрация", target_nickname],
            "is_admin_chat": True,
            "created_at": now,
            "last_message_at": now
        }
        await db.conversations.insert_one(conversation)
    else:
        await db.conversations.update_one(
            {"id": conversation_id},
            {"$set": {"last_message_at": now}}
        )
    
    # Create message
    message_doc = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "admin",
        "sender_nickname": f"Администрация ({admin_nickname})",
        "content": data.content,
        "created_at": now,
        "is_admin_message": True
    }
    await db.messages.insert_one(message_doc)
    
    # Also create unified message
    unified_msg = {
        "id": message_doc["id"],
        "conversation_id": conversation_id,
        "sender_id": "admin",
        "sender_role": "admin",
        "sender_name": f"Администрация ({admin_nickname})",
        "content": data.content,
        "created_at": now
    }
    await db.unified_messages.insert_one(unified_msg)
    
    return {"status": "sent", "message_id": message_doc["id"]}


# ==================== TOGGLE USER BALANCE LOCK ====================

@router.post("/super-admin/users/{user_id}/toggle-balance-lock")
async def toggle_user_balance_lock(user_id: str, user: dict = Depends(require_admin_level(80))):
    """Toggle user balance lock (prevent withdrawals)"""
    # Try traders
    trader = await db.traders.find_one({"id": user_id})
    if trader:
        new_state = not trader.get("balance_locked", False)
        await db.traders.update_one(
            {"id": user_id},
            {"$set": {"balance_locked": new_state}}
        )
        await log_admin_action(user["id"], "toggle_balance_lock", "trader", user_id, {"locked": new_state})
        return {"status": "success", "balance_locked": new_state}
    
    # Try merchants
    merchant = await db.merchants.find_one({"id": user_id})
    if merchant:
        new_state = not merchant.get("balance_locked", False)
        await db.merchants.update_one(
            {"id": user_id},
            {"$set": {"balance_locked": new_state}}
        )
        await log_admin_action(user["id"], "toggle_balance_lock", "merchant", user_id, {"locked": new_state})
        return {"status": "success", "balance_locked": new_state}
    
    raise HTTPException(status_code=404, detail="Пользователь не найден")


# ==================== DELETE USER ====================

@router.delete("/super-admin/users/{user_id}")
async def delete_user_account(user_id: str, user: dict = Depends(require_admin_level(100))):
    """Delete user account (owner only)"""
    # Try traders
    result = await db.traders.delete_one({"id": user_id})
    if result.deleted_count:
        await log_admin_action(user["id"], "delete_user", "trader", user_id, {})
        return {"status": "success", "message": "Пользователь удален"}
    
    # Try merchants
    result = await db.merchants.delete_one({"id": user_id})
    if result.deleted_count:
        await log_admin_action(user["id"], "delete_user", "merchant", user_id, {})
        return {"status": "success", "message": "Пользователь удален"}
    
    raise HTTPException(status_code=404, detail="Пользователь не найден")


# ==================== UNBLOCK WITH KEY ====================

@router.post("/admin/users/unblock-with-key")
async def unblock_user_with_key(data: dict = Body(...)):
    """Unblock user with secret key (for support/recovery)"""
    user_id = data.get("user_id")
    key = data.get("key")
    
    if not user_id or not key:
        raise HTTPException(status_code=400, detail="Missing user_id or key")
        
    # Verify key (simple implementation, should be more secure in prod)
    # This is a backdoor for support to unblock users if needed
    # Key should be rotated and stored securely
    valid_key = "support_unblock_key_2024"  # Change this!
    
    if key != valid_key:
        raise HTTPException(status_code=403, detail="Invalid key")
        
    # Try traders
    result = await db.traders.update_one(
        {"id": user_id},
        {"$set": {"is_blocked": False, "blocked_reason": None}}
    )
    if result.modified_count:
        return {"status": "success", "message": "User unblocked"}
        
    # Try merchants
    result = await db.merchants.update_one(
        {"id": user_id},
        {"$set": {"is_blocked": False, "blocked_reason": None}}
    )
    if result.modified_count:
        return {"status": "success", "message": "User unblocked"}
        
    raise HTTPException(status_code=404, detail="User not found")


# ==================== ADMIN: SHOPS ====================

@router.get("/admin/shops")
async def get_all_shops(user: dict = Depends(require_admin_level(30))):
    """Get all shops (traders with has_shop=True)"""
    shops = await db.traders.find(
        {"has_shop": True},
        {"_id": 0, "password_hash": 0, "password": 0}
    ).to_list(100)
    
    # Also get merchants with shops
    merchant_shops = await db.merchants.find(
        {"has_shop": True},
        {"_id": 0, "password_hash": 0, "password": 0}
    ).to_list(100)
    
    shops.extend(merchant_shops)
    
    return shops


@router.post("/admin/shops/{shop_id}/toggle-block")
async def toggle_shop_block(shop_id: str, data: dict, user: dict = Depends(require_admin_level(50))):
    """Block/unblock a shop"""
    block = data.get("block", True)
    reason = data.get("reason", "")
    
    # Try traders
    result = await db.traders.update_one(
        {"id": shop_id, "has_shop": True},
        {"$set": {"shop_settings.is_blocked": block, "shop_settings.block_reason": reason}}
    )
    
    if result.matched_count == 0:
        # Try merchants
        result = await db.merchants.update_one(
            {"id": shop_id, "has_shop": True},
            {"$set": {"shop_settings.is_blocked": block, "shop_settings.block_reason": reason}}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    await log_admin_action(user["id"], "block_shop" if block else "unblock_shop", "shop", shop_id, {"reason": reason})
    
    return {"status": "success", "blocked": block}


@router.post("/admin/shops/{shop_id}/toggle-balance-lock")
async def toggle_shop_balance_lock(shop_id: str, data: dict, user: dict = Depends(require_admin_level(80))):
    """Lock/unlock shop balance"""
    lock = data.get("lock", True)
    
    # Try traders
    result = await db.traders.update_one(
        {"id": shop_id, "has_shop": True},
        {"$set": {"shop_balance_locked": lock}}
    )
    
    if result.matched_count == 0:
        # Try merchants
        result = await db.merchants.update_one(
            {"id": shop_id, "has_shop": True},
            {"$set": {"shop_balance_locked": lock}}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    await log_admin_action(user["id"], "lock_shop_balance" if lock else "unlock_shop_balance", "shop", shop_id, {})
    
    return {"status": "success", "locked": lock}


@router.put("/admin/shops/{shop_id}/commission")
async def update_shop_commission_v2(
    shop_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_admin_level(80))
):
    """Update shop commission rate"""
    commission_rate = data.get("commission_rate")
    if commission_rate is None:
        raise HTTPException(status_code=400, detail="commission_rate required")
        
    # Try traders
    result = await db.traders.update_one(
        {"id": shop_id, "has_shop": True},
        {"$set": {"shop_settings.commission_rate": float(commission_rate)}}
    )
    
    if result.matched_count == 0:
        # Try merchants
        result = await db.merchants.update_one(
            {"id": shop_id, "has_shop": True},
            {"$set": {"shop_settings.commission_rate": float(commission_rate)}}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    await log_admin_action(user["id"], "update_shop_commission", "shop", shop_id, {"rate": commission_rate})
    
    return {"status": "success", "commission_rate": commission_rate}


@router.delete("/admin/shops/{shop_id}")
async def delete_shop(shop_id: str, user: dict = Depends(require_admin_level(100))):
    """Delete a shop (remove shop status from user)"""
    # Try traders
    result = await db.traders.update_one(
        {"id": shop_id, "has_shop": True},
        {"$set": {"has_shop": False}, "$unset": {"shop_settings": "", "shop_stats": ""}}
    )
    
    if result.matched_count == 0:
        # Try merchants
        result = await db.merchants.update_one(
            {"id": shop_id, "has_shop": True},
            {"$set": {"has_shop": False}, "$unset": {"shop_settings": "", "shop_stats": ""}}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    await log_admin_action(user["id"], "delete_shop", "shop", shop_id, {})
    
    return {"status": "success"}
