"""
Notifications routes - User notifications and badges
Routes for notification management and sidebar badge counts
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import get_current_user

router = APIRouter(tags=["notifications"])


# ==================== NOTIFICATIONS ====================

@router.get("/notifications")
async def get_notifications(user: dict = Depends(get_current_user)):
    """Get user's notifications"""
    notifications = await db.notifications.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return notifications


@router.post("/notifications/read")
async def mark_notifications_read(user: dict = Depends(get_current_user)):
    """Mark all notifications as read"""
    await db.notifications.update_many(
        {"user_id": user["id"], "read": False},
        {"$set": {"read": True}}
    )
    return {"status": "ok"}


@router.get("/notifications/unread-count")
async def get_unread_notifications_count(user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await db.notifications.count_documents({
        "user_id": user["id"],
        "read": False
    })
    return {"count": count}


@router.get("/notifications/sidebar-badges")
async def get_sidebar_badges(user: dict = Depends(get_current_user)):
    """Get badge counts for sidebar menu items"""
    user_id = user["id"]
    
    # Active P2P trades
    active_trades = await db.trades.count_documents({
        "$or": [
            {"trader_id": user_id, "status": {"$in": ["created", "pending_payment", "payment_sent", "payment_received"]}},
            {"buyer_id": user_id, "buyer_type": "trader", "status": {"$in": ["created", "pending_payment", "payment_sent", "payment_received"]}}
        ]
    })
    
    # Unread messages in private chats
    unread_messages = 0
    chats = await db.chats.find({"user_id": user_id}, {"_id": 0, "id": 1, "unread_admin": 1}).to_list(50)
    for chat in chats:
        unread_messages += chat.get("unread_admin", 0)
    
    # Active guarantor deals
    active_guarantor = await db.guarantor_deals.count_documents({
        "$or": [
            {"creator_id": user_id, "status": {"$in": ["pending_counterparty", "pending_payment", "funded"]}},
            {"counterparty_id": user_id, "status": {"$in": ["pending_payment", "funded"]}}
        ]
    })
    
    # Shop messages (if has shop)
    shop_messages = 0
    trader = await db.traders.find_one({"id": user_id}, {"_id": 0, "has_shop": 1})
    if trader and trader.get("has_shop"):
        shop = await db.shops.find_one({"owner_id": user_id}, {"_id": 0, "id": 1})
        if shop:
            shop_chats = await db.shop_messages.find({"shop_id": shop["id"], "unread_shop": {"$gt": 0}}, {"_id": 0, "unread_shop": 1}).to_list(100)
            shop_messages = sum(c.get("unread_shop", 0) for c in shop_chats)
    
    # Customer messages from shops
    shop_customer_messages = 0
    customer_shop_chats = await db.shop_conversations.find(
        {"customer_id": user_id, "unread_customer": {"$gt": 0}}, 
        {"_id": 0, "unread_customer": 1}
    ).to_list(100)
    shop_customer_messages = sum(c.get("unread_customer", 0) for c in customer_shop_chats)
    
    # Pending marketplace purchases
    pending_purchases = await db.marketplace_purchases.count_documents({
        "buyer_id": user_id,
        "status": "delivered",
        "viewed": {"$ne": True}
    })
    
    # Open support tickets
    open_tickets = await db.support_tickets.count_documents({
        "user_id": user_id,
        "status": {"$in": ["open", "in_progress"]}
    })
    
    # Unread messages from admin/staff
    admin_messages = await db.admin_user_messages.count_documents({
        "user_id": user_id,
        "sender_type": "admin",
        "read": {"$ne": True}
    })
    
    return {
        "trades": active_trades,
        "messages": unread_messages,
        "guarantor": active_guarantor,
        "shop_messages": shop_messages,
        "shop_customer_messages": shop_customer_messages,
        "purchases": pending_purchases,
        "support": open_tickets,
        "admin_messages": admin_messages,
        "total": active_trades + unread_messages + active_guarantor + shop_messages + shop_customer_messages + pending_purchases + admin_messages
    }


# ==================== USER ONLINE STATUS ====================

@router.post("/users/heartbeat")
async def user_heartbeat(user: dict = Depends(get_current_user)):
    """Update user's last seen timestamp"""
    await db.traders.update_one(
        {"id": user["id"]},
        {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}}
    )
    return {"status": "ok"}


@router.get("/users/{user_id}/online-status")
async def get_user_online_status(user_id: str):
    """Check if user is online (active in last 5 minutes)"""
    user = await db.traders.find_one({"id": user_id}, {"_id": 0, "last_seen": 1})
    if not user or not user.get("last_seen"):
        return {"online": False, "last_seen": None}
    
    last_seen = datetime.fromisoformat(user["last_seen"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    diff_minutes = (now - last_seen).total_seconds() / 60
    
    return {
        "online": diff_minutes < 5,
        "last_seen": user["last_seen"],
        "minutes_ago": int(diff_minutes)
    }


# ==================== LOGIN HISTORY ====================

@router.get("/security/login-history")
async def get_login_history(user: dict = Depends(get_current_user)):
    """Get user's login history"""
    history = await db.login_history.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    return history


# ==================== HELPER FUNCTION ====================

async def create_notification(user_id: str, type: str, title: str, message: str, link: str = None):
    """Helper to create a notification"""
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": type,
        "title": title,
        "message": message,
        "link": link,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
