"""
Admin Users Routes - Migrated from server.py
Handles super-admin user management, balance operations, account actions
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid

from core.auth import require_role, require_admin_level, get_current_user, log_admin_action, hash_password
from core.database import db

router = APIRouter(tags=["admin_users"])


# ==================== MODELS ====================

class PasswordReset(BaseModel):
    new_password: str

class BalanceFreeze(BaseModel):
    frozen: bool
    reason: Optional[str] = None

class AdminMessage(BaseModel):
    content: str


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

@router.post("/super-admin/users/{user_id}/freeze-balance")
async def freeze_user_balance(user_id: str, data: BalanceFreeze, user: dict = Depends(require_admin_level(80))):
    """Freeze/unfreeze user balance"""
    now = datetime.now(timezone.utc).isoformat()
    
    # Try traders
    result = await db.traders.update_one(
        {"id": user_id},
        {"$set": {
            "balance_frozen": data.frozen,
            "balance_freeze_reason": data.reason,
            "balance_frozen_at": now if data.frozen else None,
            "balance_frozen_by": user["id"] if data.frozen else None
        }}
    )
    if result.modified_count:
        await log_admin_action(user["id"], "freeze_balance" if data.frozen else "unfreeze_balance", "trader", user_id, {"reason": data.reason})
        return {"status": "success", "frozen": data.frozen}
    
    # Try merchants
    result = await db.merchants.update_one(
        {"id": user_id},
        {"$set": {
            "balance_frozen": data.frozen,
            "balance_freeze_reason": data.reason,
            "balance_frozen_at": now if data.frozen else None,
            "balance_frozen_by": user["id"] if data.frozen else None
        }}
    )
    if result.modified_count:
        await log_admin_action(user["id"], "freeze_balance" if data.frozen else "unfreeze_balance", "merchant", user_id, {"reason": data.reason})
        return {"status": "success", "frozen": data.frozen}
    
    raise HTTPException(status_code=404, detail="Пользователь не найден")


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
    await db.private_messages.insert_one(message_doc)
    
    await log_admin_action(user["id"], "send_message", "user", user_id, {"preview": data.content[:50]})
    
    return {"status": "sent", "conversation_id": conversation_id}


# ==================== OFFER TOGGLE ====================

@router.put("/admin/offers/{offer_id}/toggle")
async def toggle_offer_status(offer_id: str, user: dict = Depends(require_admin_level(50))):
    """Toggle offer active status (pause/play)"""
    offer = await db.offers.find_one({"id": offer_id})
    if not offer:
        raise HTTPException(status_code=404, detail="Оффер не найден")
    
    new_status = not offer.get("is_active", True)
    
    await db.offers.update_one(
        {"id": offer_id},
        {"$set": {
            "is_active": new_status,
            "paused_by_admin": not new_status,
            "toggled_at": datetime.now(timezone.utc).isoformat(),
            "toggled_by": user["id"]
        }}
    )
    
    action = "offer_activated" if new_status else "offer_deactivated"
    await log_admin_action(user["id"], action, "offer", offer_id, {"trader_login": offer.get("trader_login")})
    
    return {"status": "success", "is_active": new_status}


# ==================== USER BALANCE LOCK ====================

@router.post("/super-admin/users/{user_id}/toggle-balance-lock")
async def toggle_user_balance_lock(user_id: str, user: dict = Depends(require_admin_level(50))):
    """Lock or unlock user's balance"""
    # Try to find user in traders
    target_trader = await db.traders.find_one({"id": user_id}, {"_id": 0})
    target_merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0}) if not target_trader else None
    
    if not target_trader and not target_merchant:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if target_trader:
        current_locked = target_trader.get("is_balance_locked", False)
        new_locked = not current_locked
        
        await db.traders.update_one(
            {"id": user_id},
            {"$set": {"is_balance_locked": new_locked, "balance_locked_at": datetime.now(timezone.utc).isoformat() if new_locked else None}}
        )
        
        await log_admin_action(user["id"], "toggle_balance_lock", "trader", user_id, {"locked": new_locked})
        
        return {"status": "success", "is_balance_locked": new_locked, "user_type": "trader"}
    else:
        current_locked = target_merchant.get("is_balance_locked", False)
        new_locked = not current_locked
        
        await db.merchants.update_one(
            {"id": user_id},
            {"$set": {"is_balance_locked": new_locked, "balance_locked_at": datetime.now(timezone.utc).isoformat() if new_locked else None}}
        )
        
        await log_admin_action(user["id"], "toggle_balance_lock", "merchant", user_id, {"locked": new_locked})
        
        return {"status": "success", "is_balance_locked": new_locked, "user_type": "merchant"}


# ==================== DELETE/RESTORE ACCOUNT ====================

@router.delete("/super-admin/users/{user_id}")
async def delete_user_account(user_id: str, user: dict = Depends(require_admin_level(80))):
    """Hard delete user account - permanently removes from database"""
    target_trader = await db.traders.find_one({"id": user_id}, {"_id": 0})
    target_merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0}) if not target_trader else None
    
    if not target_trader and not target_merchant:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    target = target_trader or target_merchant
    
    # Log before deletion
    await log_admin_action(user["id"], "delete_account_permanent", "trader" if target_trader else "merchant", user_id, {
        "login": target.get("login"),
        "nickname": target.get("nickname")
    })
    
    # Hard delete - completely remove from database
    if target_trader:
        await db.traders.delete_one({"id": user_id})
        # Also delete related data
        await db.offers.delete_many({"seller_id": user_id})
    else:
        await db.merchants.delete_one({"id": user_id})
    
    return {"status": "deleted", "permanent": True}


@router.post("/super-admin/users/{user_id}/unblock")
async def unblock_user_with_key(user_id: str, data: dict = Body(...), user: dict = Depends(require_admin_level(50))):
    """Unblock user account with recovery key verification"""
    recovery_key = data.get("recovery_key")
    if not recovery_key:
        raise HTTPException(status_code=400, detail="Требуется ключ восстановления")
    
    target_trader = await db.traders.find_one({"id": user_id}, {"_id": 0})
    target_merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0}) if not target_trader else None
    
    if not target_trader and not target_merchant:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    target = target_trader or target_merchant
    collection = db.traders if target_trader else db.merchants
    
    # Verify recovery key
    if target.get("recovery_key") != recovery_key:
        raise HTTPException(status_code=400, detail="Неверный ключ восстановления")
    
    # Check if user is blocked
    if not target.get("is_blocked") and target.get("status") != "blocked":
        raise HTTPException(status_code=400, detail="Пользователь не заблокирован")
    
    # Unblock the user
    await collection.update_one(
        {"id": user_id},
        {"$set": {"is_blocked": False, "status": "active", "unblocked_at": datetime.now(timezone.utc).isoformat(), "unblocked_by": user["id"]}}
    )
    
    await log_admin_action(user["id"], "unblock_with_key", "trader" if target_trader else "merchant", user_id, {})
    
    return {"status": "unblocked"}


# ==================== ADMIN SHOP MANAGEMENT ====================

@router.get("/admin/shops")
async def get_all_shops(user: dict = Depends(require_admin_level(30))):
    """Get all shops for admin"""
    traders = await db.traders.find({"has_shop": True}, {"_id": 0, "password_hash": 0, "password": 0}).to_list(500)
    shops = []
    for t in traders:
        shop = t.get("shop_settings", {})
        shops.append({
            "id": t["id"],
            "owner_login": t.get("login"),
            "owner_nickname": t.get("nickname"),
            "shop_name": shop.get("shop_name"),
            "is_active": shop.get("is_active", True),
            "is_blocked": shop.get("is_blocked", False),
            "is_balance_locked": t.get("shop_balance_locked", False),
            "commission_rate": shop.get("commission_rate", 5),
            "shop_balance": t.get("shop_balance", 0),
            "total_sales": t.get("shop_stats", {}).get("total_sales", 0),
            "approved_at": shop.get("approved_at")
        })
    return shops


@router.post("/admin/shops/{user_id}/block")
async def toggle_shop_block(user_id: str, user: dict = Depends(require_admin_level(50))):
    """Block or unblock a shop"""
    trader = await db.traders.find_one({"id": user_id, "has_shop": True}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    
    current_blocked = trader.get("shop_settings", {}).get("is_blocked", False)
    new_blocked = not current_blocked
    
    await db.traders.update_one(
        {"id": user_id},
        {"$set": {"shop_settings.is_blocked": new_blocked}}
    )
    
    await log_admin_action(user["id"], "toggle_shop_block", "shop", user_id, {"blocked": new_blocked})
    
    return {"status": "success", "is_blocked": new_blocked}


@router.post("/admin/shops/{user_id}/toggle-balance")
async def toggle_shop_balance_lock(user_id: str, user: dict = Depends(require_admin_level(50))):
    """Lock or unlock shop balance"""
    trader = await db.traders.find_one({"id": user_id, "has_shop": True}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    
    current_locked = trader.get("shop_balance_locked", False)
    new_locked = not current_locked
    
    await db.traders.update_one(
        {"id": user_id},
        {"$set": {"shop_balance_locked": new_locked}}
    )
    
    await log_admin_action(user["id"], "toggle_shop_balance", "shop", user_id, {"locked": new_locked})
    
    return {"status": "success", "is_balance_locked": new_locked}


@router.put("/admin/shops/{user_id}/commission")
async def update_shop_commission_v2(user_id: str, commission_rate: float, user: dict = Depends(require_admin_level(50))):
    """Update shop commission rate"""
    trader = await db.traders.find_one({"id": user_id, "has_shop": True}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    
    if commission_rate < 0 or commission_rate > 50:
        raise HTTPException(status_code=400, detail="Комиссия должна быть от 0 до 50%")
    
    await db.traders.update_one(
        {"id": user_id},
        {"$set": {"shop_settings.commission_rate": commission_rate}}
    )
    
    await log_admin_action(user["id"], "update_shop_commission", "shop", user_id, {"commission_rate": commission_rate})
    
    return {"status": "success", "commission_rate": commission_rate}


@router.delete("/admin/shops/{user_id}")
async def delete_shop(user_id: str, user: dict = Depends(require_admin_level(80))):
    """Delete a shop (remove has_shop flag)"""
    trader = await db.traders.find_one({"id": user_id, "has_shop": True}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    
    await db.traders.update_one(
        {"id": user_id},
        {"$set": {
            "has_shop": False,
            "shop_settings.is_active": False,
            "shop_settings.deleted_at": datetime.now(timezone.utc).isoformat(),
            "shop_settings.deleted_by": user["id"]
        }}
    )
    
    await log_admin_action(user["id"], "delete_shop", "shop", user_id, {})
    
    return {"status": "deleted"}
