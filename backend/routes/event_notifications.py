"""
Event Notifications System - Centralized notifications for all user events
Creates notifications for all important events across the platform:
- Trades: status changes, new messages, payments
- Payouts: new orders, status updates
- Marketplace: purchases, confirmations
- Messages: new private/support messages
- Finance: deposits, withdrawals
- Referrals: new referrals, bonuses
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from core.database import db
from core.auth import get_current_user

# WebSocket manager for real-time notifications
try:
    from routes.ws_routes import ws_manager
except ImportError:
    ws_manager = None

async def _ws_broadcast(channel: str, data: dict):
    """Broadcast message via WebSocket"""
    if ws_manager:
        await ws_manager.broadcast(channel, data)

router = APIRouter(prefix="/event-notifications", tags=["event-notifications"])


# ==================== NOTIFICATION TYPES ====================
NOTIFICATION_TYPES = {
    # Trading section
    "trade_created": {"icon": "TrendingUp", "section": "trading"},
    "trade_payment_sent": {"icon": "DollarSign", "section": "trading"},
    "trade_payment_received": {"icon": "CheckCircle", "section": "trading"},
    "trade_completed": {"icon": "CheckCircle", "section": "trading"},
    "trade_cancelled": {"icon": "XCircle", "section": "trading"},
    "trade_disputed": {"icon": "AlertTriangle", "section": "trading"},
    "trade_message": {"icon": "MessageCircle", "section": "trading"},
    
    # Buy USDT (Crypto payouts)
    "payout_order_created": {"icon": "DollarSign", "section": "buy_usdt"},
    "payout_order_assigned": {"icon": "User", "section": "buy_usdt"},
    "payout_order_paid": {"icon": "CheckCircle", "section": "buy_usdt"},
    "payout_order_completed": {"icon": "CheckCircle", "section": "buy_usdt"},
    "payout_order_cancelled": {"icon": "XCircle", "section": "buy_usdt"},
    
    # Marketplace
    "marketplace_purchase": {"icon": "ShoppingBag", "section": "market"},
    "marketplace_delivered": {"icon": "Package", "section": "market"},
    "marketplace_confirmed": {"icon": "CheckCircle", "section": "market"},
    "marketplace_disputed": {"icon": "AlertTriangle", "section": "market"},
    "shop_new_order": {"icon": "ShoppingBag", "section": "market"},
    "shop_message": {"icon": "MessageCircle", "section": "market"},
    
    # Finance
    "deposit_received": {"icon": "ArrowDownRight", "section": "finances"},
    "withdrawal_completed": {"icon": "ArrowUpRight", "section": "finances"},
    "withdrawal_processing": {"icon": "Clock", "section": "finances"},
    "balance_updated": {"icon": "Wallet", "section": "finances"},
    
    # Messages
    "new_message": {"icon": "MessageCircle", "section": "messages"},
    "support_reply": {"icon": "MessageCircle", "section": "messages"},
    "broadcast": {"icon": "Bell", "section": "messages"},
    
    # Referrals
    "new_referral": {"icon": "Users", "section": "referrals"},
    "referral_bonus": {"icon": "DollarSign", "section": "referrals"},
    
    # Merchant specific
    "merchant_payment_received": {"icon": "DollarSign", "section": "trading"},
    "merchant_withdrawal_request": {"icon": "ArrowUpRight", "section": "trading"},
    "merchant_withdrawal_completed": {"icon": "CheckCircle", "section": "finances"},
}


# ==================== HELPER FUNCTIONS ====================

async def create_event_notification(
    user_id: str,
    event_type: str,
    title: str,
    message: str,
    link: str = None,
    reference_id: str = None,
    reference_type: str = None,
    extra_data: dict = None
):
    """
    Create a new event notification for a user.
    
    Args:
        user_id: The user to notify
        event_type: Type from NOTIFICATION_TYPES
        title: Short title for the notification
        message: Detailed message
        link: Link to navigate to when clicked
        reference_id: ID of related entity (trade_id, order_id, etc.)
        reference_type: Type of reference (trade, order, purchase, etc.)
        extra_data: Additional data to store with notification
    """
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": event_type,
        "title": title,
        "message": message,
        "link": link,
        "reference_id": reference_id,
        "reference_type": reference_type,
        "extra_data": extra_data or {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.event_notifications.insert_one(notification)
    
    # Real-time notification via WebSocket
    await _ws_broadcast(f"user_{user_id}", {
        "type": "new_notification",
        "notification": {k: v for k, v in notification.items() if k != "_id"}
    })
    
    return notification


async def create_bulk_notifications(notifications: List[dict]):
    """Create multiple notifications at once"""
    if not notifications:
        return
    
    docs = []
    now = datetime.now(timezone.utc).isoformat()
    
    for n in notifications:
        docs.append({
            "id": str(uuid.uuid4()),
            "user_id": n["user_id"],
            "type": n["type"],
            "title": n["title"],
            "message": n["message"],
            "link": n.get("link"),
            "reference_id": n.get("reference_id"),
            "reference_type": n.get("reference_type"),
            "extra_data": n.get("extra_data", {}),
            "read": False,
            "created_at": now
        })
    
    await db.event_notifications.insert_many(docs)


# ==================== API ENDPOINTS ====================

@router.get("")
async def get_event_notifications(
    user: dict = Depends(get_current_user),
    limit: int = 50,
    include_read: bool = False
):
    """Get user's event notifications"""
    query = {"user_id": user["id"]}
    if not include_read:
        query["read"] = False
    
    notifications = await db.event_notifications.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return notifications


@router.get("/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await db.event_notifications.count_documents({
        "user_id": user["id"],
        "read": False
    })
    return {"count": count}


@router.post("/mark-read")
async def mark_notification_read(
    user: dict = Depends(get_current_user),
    body: dict = Body(...)
):
    """
    Mark notification(s) as read.
    
    Body options:
    - {"notification_id": "..."} - mark single notification
    - {"all": true} - mark all as read
    """
    user_id = user["id"]
    
    if body.get("all"):
        # Mark all as read
        result = await db.event_notifications.update_many(
            {"user_id": user_id, "read": False},
            {"$set": {"read": True}}
        )
        return {"marked": result.modified_count}
    
    notification_id = body.get("notification_id")
    if notification_id:
        result = await db.event_notifications.update_one(
            {"id": notification_id, "user_id": user_id},
            {"$set": {"read": True}}
        )
        return {"marked": result.modified_count}
    
    raise HTTPException(status_code=400, detail="Specify notification_id or all:true")


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a specific notification"""
    result = await db.event_notifications.delete_one({
        "id": notification_id,
        "user_id": user["id"]
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"status": "deleted"}


# ==================== NOTIFICATION TRIGGERS ====================
# These functions should be called from other routes when events occur

async def notify_trade_event(trade_id: str, event: str, exclude_user_id: str = None):
    """Create notifications for trade events"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        return
    
    # Determine who to notify
    users_to_notify = []
    trader_id = trade.get("trader_id")
    buyer_id = trade.get("buyer_id")
    
    if trader_id and trader_id != exclude_user_id:
        users_to_notify.append({"user_id": trader_id, "role": "seller"})
    if buyer_id and buyer_id != exclude_user_id:
        users_to_notify.append({"user_id": buyer_id, "role": "buyer"})
    
    amount_usdt = trade.get("amount_usdt", 0)
    amount_rub = trade.get("amount_rub", 0)
    
    event_config = {
        "payment_sent": {
            "type": "trade_payment_sent",
            "title": "Оплата отправлена",
            "message": f"Покупатель отправил оплату {amount_rub:.0f} ₽ по сделке"
        },
        "payment_received": {
            "type": "trade_payment_received", 
            "title": "Оплата получена",
            "message": f"Продавец подтвердил получение {amount_rub:.0f} ₽"
        },
        "completed": {
            "type": "trade_completed",
            "title": "Сделка завершена",
            "message": f"Сделка на {amount_usdt:.2f} USDT успешно завершена"
        },
        "cancelled": {
            "type": "trade_cancelled",
            "title": "Сделка отменена",
            "message": f"Сделка на {amount_usdt:.2f} USDT была отменена"
        },
        "disputed": {
            "type": "trade_disputed",
            "title": "Открыт спор",
            "message": f"По сделке на {amount_usdt:.2f} USDT открыт спор"
        }
    }
    
    config = event_config.get(event)
    if not config:
        return
    
    for u in users_to_notify:
        link = f"/trader/{'sales' if u['role'] == 'seller' else 'purchases'}/{trade_id}"
        await create_event_notification(
            user_id=u["user_id"],
            event_type=config["type"],
            title=config["title"],
            message=config["message"],
            link=link,
            reference_id=trade_id,
            reference_type="trade"
        )


async def notify_payout_event(order_id: str, event: str, exclude_user_id: str = None):
    """Create notifications for payout (crypto_order) events"""
    order = await db.crypto_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        return
    
    trader_id = order.get("trader_id")
    if not trader_id or trader_id == exclude_user_id:
        return
    
    amount_usdt = order.get("amount_usdt", 0)
    amount_rub = order.get("amount_rub", 0)
    
    event_config = {
        "assigned": {
            "type": "payout_order_assigned",
            "title": "Новый заказ на выплату",
            "message": f"Вам назначен заказ на {amount_usdt:.2f} USDT ({amount_rub:.0f} ₽)"
        },
        "paid": {
            "type": "payout_order_paid",
            "title": "Оплата получена",
            "message": f"Платёж {amount_rub:.0f} ₽ подтверждён"
        },
        "completed": {
            "type": "payout_order_completed",
            "title": "Выплата завершена",
            "message": f"Заказ на {amount_usdt:.2f} USDT успешно выполнен"
        },
        "cancelled": {
            "type": "payout_order_cancelled",
            "title": "Заказ отменён",
            "message": f"Заказ на {amount_usdt:.2f} USDT был отменён"
        }
    }
    
    config = event_config.get(event)
    if not config:
        return
    
    await create_event_notification(
        user_id=trader_id,
        event_type=config["type"],
        title=config["title"],
        message=config["message"],
        link="/trader/messages",  # Payouts are handled via messages
        reference_id=order_id,
        reference_type="crypto_order"
    )


async def notify_message_event(user_id: str, sender_name: str, chat_type: str = "private"):
    """Create notification for new message"""
    await create_event_notification(
        user_id=user_id,
        event_type="new_message",
        title="Новое сообщение",
        message=f"Сообщение от {sender_name}",
        link="/trader/messages" if chat_type == "private" else "/trader/shop-chats",
        reference_type="message"
    )


async def notify_finance_event(user_id: str, event: str, amount: float, currency: str = "USDT"):
    """Create notification for finance events"""
    event_config = {
        "deposit": {
            "type": "deposit_received",
            "title": "Пополнение баланса",
            "message": f"На ваш баланс зачислено {amount:.2f} {currency}"
        },
        "withdrawal_processing": {
            "type": "withdrawal_processing",
            "title": "Вывод в обработке",
            "message": f"Заявка на вывод {amount:.2f} {currency} обрабатывается"
        },
        "withdrawal_completed": {
            "type": "withdrawal_completed",
            "title": "Вывод выполнен",
            "message": f"Вывод {amount:.2f} {currency} успешно выполнен"
        }
    }
    
    config = event_config.get(event)
    if not config:
        return
    
    await create_event_notification(
        user_id=user_id,
        event_type=config["type"],
        title=config["title"],
        message=config["message"],
        link="/trader/transactions",
        reference_type="finance"
    )


async def notify_referral_event(user_id: str, event: str, referral_name: str = None, bonus: float = None):
    """Create notification for referral events"""
    if event == "new_referral":
        await create_event_notification(
            user_id=user_id,
            event_type="new_referral",
            title="Новый реферал",
            message=f"Пользователь {referral_name or 'аноним'} зарегистрировался по вашей ссылке",
            link="/trader/referral",
            reference_type="referral"
        )
    elif event == "bonus" and bonus:
        await create_event_notification(
            user_id=user_id,
            event_type="referral_bonus",
            title="Реферальный бонус",
            message=f"Начислено {bonus:.4f} USDT от сделки реферала",
            link="/trader/referral",
            reference_type="referral"
        )


async def notify_marketplace_event(user_id: str, event: str, product_name: str, amount: float = None):
    """Create notification for marketplace events"""
    event_config = {
        "purchase": {
            "type": "marketplace_purchase",
            "title": "Новая покупка",
            "message": f"Вы приобрели '{product_name}'"
        },
        "delivered": {
            "type": "marketplace_delivered",
            "title": "Товар доставлен",
            "message": f"Товар '{product_name}' доставлен, подтвердите получение"
        },
        "shop_order": {
            "type": "shop_new_order",
            "title": "Новый заказ в магазине",
            "message": f"Получен заказ на '{product_name}'"
        }
    }
    
    config = event_config.get(event)
    if not config:
        return
    
    await create_event_notification(
        user_id=user_id,
        event_type=config["type"],
        title=config["title"],
        message=config["message"],
        link="/trader/my-purchases" if event != "shop_order" else "/trader/shop",
        reference_type="marketplace"
    )


async def notify_broadcast(user_ids: List[str], title: str, message: str):
    """Send broadcast notification to multiple users"""
    notifications = []
    for user_id in user_ids:
        notifications.append({
            "user_id": user_id,
            "type": "broadcast",
            "title": title,
            "message": message,
            "link": "/trader/messages",
            "reference_type": "broadcast"
        })
    
    await create_bulk_notifications(notifications)
