from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone, timedelta
import uuid

from core.auth import get_current_user
from core.database import db

router = APIRouter(tags=["crypto"])

@router.post("/crypto/buy")
async def buy_crypto(
    data: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """Buy crypto from a sell offer (trader only, 50+ trades required)"""
    # Block merchants
    if user.get("role") == "merchant":
        raise HTTPException(status_code=403, detail="Мерчантам покупка USDT недоступна")
    
    # Block admin/staff
    admin_roles = ["admin", "owner", "mod_p2p", "mod_marketplace", "mod_support", "super_admin"]
    if user.get("admin_role") in admin_roles or user.get("role") in admin_roles:
        raise HTTPException(status_code=403, detail="Администрации покупка USDT недоступна")
    
    if user.get("role") != "trader":
        raise HTTPException(status_code=403, detail="Только для трейдеров")
    
    # Check trader's trade count
    trader = await db.traders.find_one({"id": user["id"]}, {"_id": 0})
    profile_trades = trader.get("successful_trades", 0) if trader else 0
    
    db_trades = await db.trades.count_documents({
        "$or": [
            {"buyer_id": user["id"], "status": "completed"},
            {"seller_id": user["id"], "status": "completed"}
        ]
    })
    
    successful_trades = max(profile_trades, db_trades)
    
    # Check min successful trades from settings
    settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    min_trades = settings.get("min_successful_trades", 20) if settings else 20
    
    if successful_trades < min_trades:
        raise HTTPException(
            status_code=403, 
            detail=f"Необходимо минимум {min_trades} успешных сделок. У вас: {successful_trades}"
        )
    
    offer_id = data.get("offer_id")
    rules_accepted = data.get("rules_accepted", False)
    
    if not rules_accepted:
        raise HTTPException(status_code=400, detail="Необходимо принять правила")
    
    if not offer_id:
        raise HTTPException(status_code=400, detail="Некорректные данные")
    
    # Get offer - must be active
    offer = await db.crypto_sell_offers.find_one(
        {"id": offer_id, "status": "active"},
        {"_id": 0}
    )
    
    if not offer:
        raise HTTPException(status_code=404, detail="Заявка не найдена или уже занята")
    
    # ALWAYS get current sell_rate from settings
    sell_rate = settings.get("sell_rate", 82.16) if settings else 82.16
    
    # Get amounts from offer
    rub_amount = offer.get("amount_rub", 0)
    
    # Calculate USDT using current sell_rate
    usdt_for_buyer = round(rub_amount / sell_rate, 2) if rub_amount > 0 else 0
    
    # Calculate merchant's frozen amount and platform profit
    base_rate = settings.get("base_rate", 78.21) if settings else 78.21
    usdt_from_merchant = round(rub_amount / base_rate, 2) if rub_amount > 0 else 0
    platform_profit = round(usdt_from_merchant - usdt_for_buyer, 2) if usdt_from_merchant > usdt_for_buyer else 0
    
    # Get merchant info
    merchant = await db.merchants.find_one({"id": offer.get("merchant_id")}, {"_id": 0})
    merchant_nickname = merchant.get("nickname", merchant.get("login")) if merchant else "Мерчант"
    
    now = datetime.now(timezone.utc).isoformat()
    order_id = str(uuid.uuid4())
    
    # Create order
    order = {
        "id": order_id,
        "offer_id": offer_id,
        "buyer_id": user["id"],
        "buyer_nickname": user.get("nickname", user.get("login")),
        "merchant_id": offer.get("merchant_id"),
        "merchant_nickname": merchant_nickname,
        "amount_usdt": usdt_for_buyer,
        "usdt_from_merchant": usdt_from_merchant,
        "platform_profit": platform_profit,
        "amount_rub": rub_amount,
        "sell_rate": sell_rate,
        "withdrawal_commission": offer.get("withdrawal_commission"),
        "payment_type": offer.get("payment_type", "card"),
        "card_number": offer.get("card_number", ""),
        "sbp_phone": offer.get("sbp_phone", ""),
        "bank_name": offer.get("bank_name", ""),
        "status": "pending",
        "status_history": [
            {"status": "pending", "timestamp": now, "by": "system", "action": "order_created"}
        ],
        "dispute_window_until": None,
        "dispute_opened_at": None,
        "dispute_reason": None,
        "dispute_winner": None,
        "created_at": now,
        "updated_at": now,
        "completed_at": None
    }
    
    await db.crypto_orders.insert_one(order)
    
    # Mark offer as "in_progress"
    await db.crypto_sell_offers.update_one(
        {"id": offer_id},
        {"$set": {
            "status": "in_progress",
            "current_order_id": order_id,
            "updated_at": now
        }}
    )
    
    # Create conversation
    conv_id = str(uuid.uuid4())
    conv = {
        "id": conv_id,
        "type": "crypto_order",
        "related_id": order_id,
        "status": "active",
        "title": f"Покупка {usdt_for_buyer} USDT",
        "subtitle": f"@{user.get('nickname', user.get('login'))} • {rub_amount:.2f} ₽",
        "participants": [user["id"]],
        "buyer_id": user["id"],
        "merchant_id": offer.get("merchant_id"),
        "amount_usdt": usdt_for_buyer,
        "amount_rub": rub_amount,
        "created_at": now,
        "updated_at": now
    }
    
    await db.unified_conversations.insert_one(conv)
    
    # Build payment details message
    payment_details = ""
    if offer.get("payment_type") == "card":
        payment_details = f"💳 Карта: {offer.get('card_number', 'Не указано')}"
        if offer.get("bank_name"):
            payment_details += f"\n🏦 Банк: {offer.get('bank_name')}"
    elif offer.get("payment_type") == "sbp":
        payment_details = f"📱 СБП: {offer.get('sbp_phone', 'Не указано')}"
        if offer.get("bank_name"):
            payment_details += f"\n🏦 Банк: {offer.get('bank_name')}"
    
    # Send initial system message
    await db.unified_messages.insert_one({
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "sender_id": "system",
        "sender_role": "system",
        "text": f"Заказ #{order_id[:8]} создан.\n\nСумма к оплате: {rub_amount:.2f} ₽\nВы получите: {usdt_for_buyer} USDT\n\nРеквизиты для оплаты:\n{payment_details}\n\nПосле оплаты нажмите кнопку 'Я оплатил'.",
        "is_system": True,
        "created_at": now,
        "read_by": []
    })
    
    # Create notification for merchant (if needed)
    # But merchant doesn't participate in chat directly, only admin confirms
    
    return {
        "order_id": order_id,
        "status": "pending",
        "amount_rub": rub_amount,
        "amount_usdt": usdt_for_buyer,
        "payment_details": {
            "type": offer.get("payment_type"),
            "card_number": offer.get("card_number"),
            "sbp_phone": offer.get("sbp_phone"),
            "bank_name": offer.get("bank_name")
        }
    }


@router.get("/crypto/my-orders")
async def get_my_crypto_orders(user: dict = Depends(get_current_user)):
    """Get trader's crypto buy orders"""
    if user.get("role") != "trader":
        raise HTTPException(status_code=403, detail="Только для трейдеров")
    
    orders = await db.crypto_orders.find(
        {"buyer_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return orders


@router.post("/crypto/orders/{order_id}/paid")
async def mark_crypto_order_paid(
    order_id: str,
    user: dict = Depends(get_current_user)
):
    """Mark crypto order as paid by buyer"""
    order = await db.crypto_orders.find_one(
        {"id": order_id, "buyer_id": user["id"]},
        {"_id": 0}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    if order["status"] != "pending":
        raise HTTPException(status_code=400, detail="Заказ уже оплачен или завершён")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update order status
    await db.crypto_orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "paid",
            "paid_at": now,
            "updated_at": now
        }, "$push": {
            "status_history": {
                "status": "paid",
                "timestamp": now,
                "by": user["id"],
                "action": "buyer_marked_paid"
            }
        }}
    )
    
    # Send system message
    conv = await db.unified_conversations.find_one({"related_id": order_id, "type": "crypto_order"})
    if conv:
        await db.unified_messages.insert_one({
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_role": "system",
            "text": "Покупатель отметил заказ как оплаченный. Ожидайте подтверждения администратором.",
            "is_system": True,
            "created_at": now,
            "read_by": []
        })
    
    # Notify admins
    # In a real system, we would notify admins via websocket or push
    
    return {"status": "paid"}
