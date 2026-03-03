"""
Notifications routes - User notifications and badges
Routes for notification management and sidebar badge counts
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone, timedelta
from typing import Optional
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
async def mark_notifications_read(user: dict = Depends(get_current_user), body: dict = Body(default={})):
    """Mark notifications/badges as read.

    - If body has 'type': dismiss only that type
    - Otherwise: dismiss everything

    Note: some sidebar badges are derived from live DB queries. For those we store a
    dismissal timestamp in `badge_dismissals` collection.
    """
    user_id = user["id"]
    badge_type = body.get("type", None) if body else None
    now_iso = datetime.now(timezone.utc).isoformat()

    # Map badge keys to notification types (notifications collection)
    notif_types_by_badge = {
        "trade_payment": ["trade_payment"],
        "trade_message": ["trade_message"],
        "trade_dispute": ["trade_dispute"],
        # backward compatibility / old keys
        "trade_payments": ["trade_payment"],
        "trade_events": ["trade_message", "trade_dispute"],
        "disputes": ["trade_dispute"],
    }

    if badge_type:
        notif_types = notif_types_by_badge.get(badge_type)
        if notif_types:
            await db.notifications.update_many(
                {"user_id": user_id, "type": {"$in": notif_types}, "read": False},
                {"$set": {"read": True}}
            )
    else:
        await db.notifications.update_many(
            {"user_id": user_id, "read": False},
            {"$set": {"read": True}}
        )

    types_to_dismiss = [badge_type] if badge_type else [
        "trades",
        "purchases",
        "guarantor",
        "deposits",
        "withdrawals",
        "trade_payment",
        "trade_message",
        "trade_dispute",
    ]

    for t in types_to_dismiss:
        if t == "deposits":
            await db.transactions.update_many(
                {
                    "user_id": user_id,
                    "type": {"$in": ["deposit", "admin_deposit"]},
                    "notified": {"$ne": True},
                },
                {"$set": {"notified": True}}
            )
        elif t == "withdrawals":
            await db.withdrawal_requests.update_many(
                {"user_id": user_id, "notified": {"$ne": True}},
                {"$set": {"notified": True}}
            )
        elif t == "purchases":
            # Delivered marketplace purchases (buyer)
            await db.marketplace_purchases.update_many(
                {"buyer_id": user_id, "status": "delivered", "viewed": {"$ne": True}},
                {"$set": {"viewed": True}}
            )
        elif t == "guarantor":
            # Marketplace guarantor deals
            await db.marketplace_purchases.update_many(
                {
                    "$or": [{"buyer_id": user_id}, {"seller_id": user_id}],
                    "purchase_type": "guarantor",
                    "status": {"$in": ["pending_confirmation", "disputed"]},
                    "guarantor_notified": {"$ne": True},
                },
                {"$set": {"guarantor_notified": True}}
            )
            await db.badge_dismissals.update_one(
                {"user_id": user_id, "type": "guarantor"},
                {"$set": {"dismissed_at": now_iso}},
                upsert=True,
            )
        elif t == "trades":
            await db.badge_dismissals.update_one(
                {"user_id": user_id, "type": "trades"},
                {"$set": {"dismissed_at": now_iso}},
                upsert=True,
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
    
    # Badge dismissals (per-type). Fallback to legacy `badges_dismissed_at` if present.
    user_doc = await db.traders.find_one({"id": user_id}, {"_id": 0, "badges_dismissed_at": 1})
    if not user_doc:
        user_doc = await db.merchants.find_one({"id": user_id}, {"_id": 0, "badges_dismissed_at": 1})
    dismissed_at_fallback = user_doc.get("badges_dismissed_at") if user_doc else None

    dismissals = await db.badge_dismissals.find(
        {"user_id": user_id},
        {"_id": 0, "type": 1, "dismissed_at": 1}
    ).to_list(50)
    dismissed_map = {d.get("type"): d.get("dismissed_at") for d in dismissals if d.get("type")}

    trades_dismissed_at = dismissed_map.get("trades") or dismissed_at_fallback
    guarantor_dismissed_at = dismissed_map.get("guarantor") or dismissed_at_fallback
    
    # Active P2P trades (only count those created after dismissal)
    trades_filter = {
        "$or": [
            {"trader_id": user_id, "status": {"$in": ["created", "pending_payment", "payment_sent", "payment_received"]}},
            {"buyer_id": user_id, "buyer_type": "trader", "status": {"$in": ["created", "pending_payment", "payment_sent", "payment_received"]}}
        ]
    }
    if trades_dismissed_at:
        trades_filter["created_at"] = {"$gt": trades_dismissed_at}
    active_trades = await db.trades.count_documents(trades_filter)
    
    # Unread messages in private chats
    unread_messages = 0
    chats = await db.chats.find({"user_id": user_id}, {"_id": 0, "id": 1, "unread_admin": 1}).to_list(50)
    for chat in chats:
        unread_messages += chat.get("unread_admin", 0)
    
    # Active guarantor deals
    guarantor_filter = {
        "$or": [
            {"creator_id": user_id, "status": {"$in": ["pending_counterparty", "pending_payment", "funded"]}},
            {"counterparty_id": user_id, "status": {"$in": ["pending_payment", "funded"]}}
        ]
    }
    if guarantor_dismissed_at:
        guarantor_filter["created_at"] = {"$gt": guarantor_dismissed_at}
    active_guarantor = await db.guarantor_deals.count_documents(guarantor_filter)
    
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
    
    # Active marketplace guarantor deals (as buyer or seller)
    guarantor_deals_count = await db.marketplace_purchases.count_documents({
        "$or": [
            {"buyer_id": user_id},
            {"seller_id": user_id}
        ],
        "purchase_type": "guarantor",
        "status": {"$in": ["pending_confirmation", "disputed"]},
        "guarantor_notified": {"$ne": True}
    })
    
    # Unread guarantor messages
    guarantor_unread = 0
    guarantor_convs = await db.unified_conversations.find(
        {"type": "marketplace_guarantor", "participant_ids": user_id},
        {"_id": 0, "id": 1}
    ).to_list(50)
    for conv in guarantor_convs:
        unread = await db.unified_messages.count_documents({
            "conversation_id": conv["id"],
            "sender_id": {"$ne": user_id},
            "read_by": {"$not": {"$elemMatch": {"$eq": user_id}}}
        })
        guarantor_unread += unread
    
    # Keep purchases and guarantor deals separate to avoid double-counting
    purchases = pending_purchases
    guarantor_deals = guarantor_deals_count + guarantor_unread
    
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
    
    # Pending deposits (recent in last 24h, not yet viewed)
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    pending_deposits = await db.transactions.count_documents({
        "user_id": user_id,
        "type": {"$in": ["deposit", "admin_deposit"]},
        "created_at": {"$gte": recent_cutoff},
        "notified": {"$ne": True}
    })
    
    # Pending withdrawals (not yet dismissed)
    pending_withdrawals = await db.withdrawal_requests.count_documents({
        "user_id": user_id,
        "status": {"$in": ["pending", "processing", "completed"]},
        "notified": {"$ne": True}
    })
    
    # Trade events (payment/message/dispute) are true notifications
    trade_payment = await db.notifications.count_documents({
        "user_id": user_id,
        "type": "trade_payment",
        "read": False
    })
    trade_message = await db.notifications.count_documents({
        "user_id": user_id,
        "type": "trade_message",
        "read": False
    })
    trade_dispute = await db.notifications.count_documents({
        "user_id": user_id,
        "type": {"$in": ["trade_dispute", "trade_disputed"]},
        "read": False
    })
    
    # Count unread event_notifications (new unified system)
    event_notifications_count = await db.event_notifications.count_documents({
        "user_id": user_id,
        "read": False
    })
    
    # Also count from old notifications as fallback
    old_notifications_count = await db.notifications.count_documents({
        "user_id": user_id,
        "read": False
    })
    
    # Use whichever is higher (to ensure we show all notifications)
    combined_notifications = max(event_notifications_count, old_notifications_count)

    # Backward compatibility
    trade_payments = trade_payment
    trade_events = trade_message + trade_dispute
    
    # Use combined notifications count as total for consistency
    total = combined_notifications if combined_notifications > 0 else (
        active_trades
        + unread_messages
        + active_guarantor
        + shop_messages
        + shop_customer_messages
        + purchases
        + guarantor_deals
        + admin_messages
        + pending_deposits
        + pending_withdrawals
        + trade_payment
        + trade_message
        + trade_dispute
    )

    return {
        "trades": active_trades,
        "messages": unread_messages,
        "guarantor": active_guarantor,
        "shop_messages": shop_messages,
        "shop_customer_messages": shop_customer_messages,
        "purchases": purchases,
        "guarantor_deals": guarantor_deals,
        "guarantor_unread": guarantor_unread,
        "support": open_tickets,
        "admin_messages": admin_messages,
        "deposits": pending_deposits,
        "withdrawals": pending_withdrawals,
        "trade_payment": trade_payment,
        "trade_message": trade_message,
        "trade_dispute": trade_dispute,
        "event_notifications": combined_notifications,
        # Backward compatibility
        "trade_payments": trade_payments,
        "trade_events": trade_events,
        "disputes": trade_dispute,
        "total": total
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
