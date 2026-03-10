
from core.database import db
from .utils import create_event_notification

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
        link="/trader/market",
        reference_type="marketplace"
    )


async def notify_broadcast(title: str, message: str, user_ids: list = None):
    """Create broadcast notification for multiple users"""
    if not user_ids:
        return
        
    notifications = []
    for uid in user_ids:
        notifications.append({
            "user_id": uid,
            "type": "broadcast",
            "title": title,
            "message": message,
            "link": None,
            "reference_type": "broadcast"
        })
    
    from .utils import create_bulk_notifications
    await create_bulk_notifications(notifications)
