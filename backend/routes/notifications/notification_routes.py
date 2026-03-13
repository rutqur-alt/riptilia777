
from fastapi import APIRouter, Depends, Body
from datetime import datetime, timezone

from core.database import db
from core.auth import get_current_user

router = APIRouter()

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
