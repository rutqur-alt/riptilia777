"""
Crypto Payouts Routes - Migrated from server.py
Handles crypto sell offers, orders, payout settings, and admin crypto management
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone, timedelta
import uuid

from core.auth import require_role, get_current_user
from server import db

router = APIRouter(tags=["crypto"])


# ==================== CRYPTO SELL OFFERS (ЗАЯВКИ НА ПРОДАЖУ КРИПТЫ) ====================

@router.get("/crypto/sell-offers")
async def get_crypto_sell_offers():
    """Get all active crypto sell offers from merchants
    
    Shows offers with RUB amount and USDT amount (what buyer receives).
    USDT is calculated at platform's SELL RATE.
    """
    # Get payout settings
    settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    sell_rate = settings.get("sell_rate", 110.0) if settings else 110.0  # Platform sell rate
    
    # Get all active sell offers
    offers = await db.crypto_sell_offers.find(
        {"status": "active"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    result = []
    for offer in offers:
        # Add merchant info
        merchant = await db.merchants.find_one(
            {"id": offer.get("merchant_id")},
            {"_id": 0, "nickname": 1, "is_verified": 1}
        )
        if merchant:
            offer["merchant_name"] = merchant.get("nickname", "Мерчант")
            offer["merchant_verified"] = merchant.get("is_verified", False)
        
        # Get merchant trades count
        trades_count = await db.trades.count_documents({
            "merchant_id": offer.get("merchant_id"),
            "status": "completed"
        })
        offer["merchant_trades"] = trades_count
        
        # Show USDT amount buyer will receive (at sell_rate)
        if offer.get("amount_rub"):
            # Use pre-calculated usdt_for_buyer if available, otherwise calculate
            usdt_for_buyer = offer.get("usdt_for_buyer") or round(offer["amount_rub"] / sell_rate, 2)
            offer["amount_usdt"] = usdt_for_buyer
            offer["sell_rate"] = sell_rate
            # For backward compatibility
            offer["amount"] = usdt_for_buyer
            offer["available_amount"] = usdt_for_buyer
            offer["rate"] = sell_rate
            result.append(offer)
        # Old format offers
        elif offer.get("available_amount", 0) > 0:
            offer["amount_usdt"] = offer.get("available_amount", 0)
            offer["sell_rate"] = offer.get("rate", sell_rate)
            result.append(offer)
    
    return result


@router.post("/crypto/sell-offers")
async def create_crypto_sell_offer(
    data: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """Create a crypto sell offer (merchant only)
    
    NEW Business logic with TWO RATES:
    1. Merchant enters amount in RUB (FIXED on storefront)
    2. Merchant gives USDT at his rate (base_rate - withdrawal_commission%)
    3. Platform sells at sell_rate (higher than base)
    4. Buyer pays RUB, receives USDT at sell_rate
    5. Difference is platform profit
    """
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    # Get payout settings
    settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = settings.get("base_rate", 100.0) if settings else 100.0
    sell_rate = settings.get("sell_rate", 110.0) if settings else 110.0
    
    # Input in RUB - THIS IS FIXED
    amount_rub = data.get("amount_rub", 0)
    if amount_rub <= 0:
        raise HTTPException(status_code=400, detail="Укажите сумму в рублях")
    
    # Payment details - required
    payment_type = data.get("payment_type", "card")
    card_number = data.get("card_number", "")
    sbp_phone = data.get("sbp_phone", "")
    bank_name = data.get("bank_name", "")
    
    if payment_type == "card" and not card_number:
        raise HTTPException(status_code=400, detail="Укажите номер карты")
    if payment_type == "sbp" and (not sbp_phone or not bank_name):
        raise HTTPException(status_code=400, detail="Укажите номер СБП и банк")
    
    # Get merchant
    merchant = await db.merchants.find_one({"id": user["id"]}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    # Calculate merchant's rate (base_rate minus withdrawal_commission%)
    withdrawal_commission = merchant.get("withdrawal_commission", 3.0)
    merchant_rate = base_rate * (1 - withdrawal_commission / 100)
    
    # Calculate USDT to deduct from merchant at MERCHANT's rate
    usdt_to_deduct = amount_rub / merchant_rate
    usdt_to_deduct = round(usdt_to_deduct, 2)
    
    # Calculate USDT buyer will receive at SELL rate
    usdt_for_buyer = amount_rub / sell_rate
    usdt_for_buyer = round(usdt_for_buyer, 2)
    
    # Platform profit
    platform_profit = round(usdt_to_deduct - usdt_for_buyer, 2)
    
    # Check merchant balance
    if merchant.get("balance_usdt", 0) < usdt_to_deduct:
        raise HTTPException(
            status_code=400, 
            detail=f"Недостаточно средств. Нужно: {usdt_to_deduct} USDT (по курсу {merchant_rate:.2f}), доступно: {merchant.get('balance_usdt', 0)} USDT"
        )
    
    min_amount_rub = data.get("min_amount_rub", 1000)
    
    now = datetime.now(timezone.utc).isoformat()
    offer_id = str(uuid.uuid4())
    
    offer = {
        "id": offer_id,
        "merchant_id": user["id"],
        "merchant_nickname": merchant.get("nickname") or merchant.get("login"),
        # RUB amount - FIXED on storefront
        "amount_rub": amount_rub,
        "min_amount_rub": min_amount_rub,
        # USDT amounts
        "usdt_from_merchant": usdt_to_deduct,
        "usdt_for_buyer": usdt_for_buyer,
        "platform_profit": platform_profit,
        # Rates used
        "base_rate": base_rate,
        "merchant_rate": merchant_rate,
        "sell_rate": sell_rate,
        "withdrawal_commission": withdrawal_commission,
        # Payment details
        "payment_type": payment_type,
        "card_number": card_number if payment_type == "card" else "",
        "sbp_phone": sbp_phone if payment_type == "sbp" else "",
        "bank_name": bank_name,
        # Status
        "status": "active",
        "created_at": now,
        "updated_at": now
    }
    
    await db.crypto_sell_offers.insert_one(offer)
    
    # Transfer USDT from merchant to platform
    await db.merchants.update_one(
        {"id": user["id"]},
        {"$inc": {"balance_usdt": -usdt_to_deduct}}
    )
    
    # Add to platform balance
    await db.settings.update_one(
        {"type": "platform_balance"},
        {"$inc": {"balance_usdt": usdt_to_deduct}},
        upsert=True
    )
    
    # Record transaction
    await db.platform_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "type": "merchant_deposit",
        "offer_id": offer_id,
        "merchant_id": user["id"],
        "usdt_from_merchant": usdt_to_deduct,
        "usdt_for_buyer": usdt_for_buyer,
        "platform_profit": platform_profit,
        "amount_rub": amount_rub,
        "merchant_rate": merchant_rate,
        "sell_rate": sell_rate,
        "created_at": now
    })
    
    offer.pop("_id", None)
    return {
        **offer,
        "message": f"Заявка на {amount_rub} ₽ создана.\n\n📊 Ваш курс: {merchant_rate:.2f} ₽/USDT\n💸 Списано: {usdt_to_deduct} USDT\n👤 Покупатель получит: {usdt_for_buyer} USDT\n📈 Прибыль платформы: {platform_profit} USDT"
    }


@router.delete("/crypto/sell-offers/{offer_id}")
async def cancel_crypto_sell_offer(
    offer_id: str,
    user: dict = Depends(get_current_user)
):
    """Cancel a crypto sell offer (merchant only)"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    offer = await db.crypto_sell_offers.find_one(
        {"id": offer_id, "merchant_id": user["id"]},
        {"_id": 0}
    )
    
    if not offer:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    if offer.get("status") != "active":
        raise HTTPException(status_code=400, detail="Заявка уже закрыта")
    
    # Return frozen funds
    await db.merchants.update_one(
        {"id": user["id"]},
        {
            "$inc": {
                "balance_usdt": offer.get("available_amount", 0),
                "frozen_balance": -offer.get("available_amount", 0)
            }
        }
    )
    
    # Mark offer as cancelled
    await db.crypto_sell_offers.update_one(
        {"id": offer_id},
        {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"status": "cancelled"}


@router.post("/crypto/buy")
async def buy_crypto(
    data: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """Buy crypto from a sell offer (trader only, 50+ trades required)"""
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
    
    if successful_trades < 50:
        raise HTTPException(
            status_code=403, 
            detail=f"Необходимо минимум 50 успешных сделок. У вас: {successful_trades}"
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
    
    # Get amounts from offer
    rub_amount = offer.get("amount_rub", 0)
    usdt_for_buyer = offer.get("usdt_for_buyer", 0)
    usdt_from_merchant = offer.get("usdt_from_merchant", 0)
    platform_profit = offer.get("platform_profit", 0)
    sell_rate = offer.get("sell_rate", 110.0)
    
    # Fallback for old format offers
    if not usdt_for_buyer and rub_amount:
        settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
        sell_rate = settings.get("sell_rate", 110.0) if settings else 110.0
        usdt_for_buyer = round(rub_amount / sell_rate, 2)
    
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
    else:
        payment_details = f"📱 СБП: {offer.get('sbp_phone', 'Не указано')}"
        if offer.get("bank_name"):
            payment_details += f"\n🏦 Банк: {offer.get('bank_name')}"
    
    # System message with payment details
    sys_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"""💰 Заявка на покупку {usdt_for_buyer} USDT создана

📊 Курс продажи: {sell_rate:.2f} ₽/USDT
💵 К оплате: {rub_amount:.2f} ₽

{payment_details}

⚠️ Переведите точную сумму {rub_amount:.2f} ₽ на указанные реквизиты.
После оплаты нажмите кнопку "Я оплатил" и дождитесь подтверждения.""",
        "is_system": True,
        "created_at": now
    }
    
    await db.unified_messages.insert_one(sys_msg)
    
    return {
        "status": "created",
        "order_id": order_id,
        "conversation_id": conv_id,
        "amount_usdt": usdt_for_buyer,
        "amount_rub": rub_amount,
        "sell_rate": sell_rate,
        "payment_details": {
            "type": offer.get("payment_type"),
            "card_number": offer.get("card_number"),
            "sbp_phone": offer.get("sbp_phone"),
            "bank_name": offer.get("bank_name")
        }
    }


@router.get("/crypto/my-offers")
async def get_my_crypto_offers(user: dict = Depends(get_current_user)):
    """Get merchant's crypto sell offers"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    offers = await db.crypto_sell_offers.find(
        {"merchant_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return offers


@router.get("/crypto/my-orders")
async def get_my_crypto_orders(user: dict = Depends(get_current_user)):
    """Get user's crypto orders (buyer or merchant)"""
    query = {}
    if user.get("role") == "merchant":
        query["merchant_id"] = user["id"]
    else:
        query["buyer_id"] = user["id"]
    
    orders = await db.crypto_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    return orders


@router.get("/merchant/deals-archive")
async def get_merchant_deals_archive(user: dict = Depends(get_current_user)):
    """Get merchant's completed/disputed deals archive with full chat history"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    orders = await db.crypto_orders.find(
        {
            "merchant_id": user["id"],
            "status": {"$in": ["completed", "cancelled", "dispute", "dispute_resolved"]}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    result = []
    for order in orders:
        conv = await db.unified_conversations.find_one(
            {"related_id": order["id"]},
            {"_id": 0}
        )
        
        messages = []
        if conv:
            messages = await db.unified_messages.find(
                {"conversation_id": conv["id"]},
                {"_id": 0}
            ).sort("created_at", 1).to_list(500)
        
        archive_entry = {
            "order": order,
            "conversation": conv,
            "messages": messages,
            "message_count": len(messages),
            "order_id": order["id"],
            "status": order.get("status"),
            "amount_usdt": order.get("amount_usdt", 0),
            "amount_rub": order.get("amount_rub", 0),
            "buyer_nickname": order.get("buyer_nickname", "N/A"),
            "created_at": order.get("created_at"),
            "completed_at": order.get("completed_at"),
            "dispute_winner": order.get("dispute_winner"),
            "has_dispute": order.get("status") in ["dispute", "dispute_resolved"]
        }
        
        result.append(archive_entry)
    
    return result


@router.get("/merchant/deals-archive/{order_id}")
async def get_merchant_deal_details(order_id: str, user: dict = Depends(get_current_user)):
    """Get detailed archive entry for a specific deal"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    order = await db.crypto_orders.find_one(
        {"id": order_id, "merchant_id": user["id"]},
        {"_id": 0}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    conv = await db.unified_conversations.find_one(
        {"related_id": order_id},
        {"_id": 0}
    )
    
    messages = []
    if conv:
        messages = await db.unified_messages.find(
            {"conversation_id": conv["id"]},
            {"_id": 0}
        ).sort("created_at", 1).to_list(500)
    
    offer = await db.crypto_sell_offers.find_one(
        {"id": order.get("offer_id")},
        {"_id": 0}
    )
    
    return {
        "order": order,
        "offer": offer,
        "conversation": conv,
        "messages": messages,
        "summary": {
            "order_id": order["id"],
            "status": order.get("status"),
            "amount_usdt": order.get("amount_usdt", 0),
            "usdt_from_merchant": order.get("usdt_from_merchant", 0),
            "platform_profit": order.get("platform_profit", 0),
            "amount_rub": order.get("amount_rub", 0),
            "sell_rate": order.get("sell_rate", 0),
            "buyer_nickname": order.get("buyer_nickname"),
            "payment_type": order.get("payment_type"),
            "card_number": order.get("card_number"),
            "sbp_phone": order.get("sbp_phone"),
            "bank_name": order.get("bank_name"),
            "created_at": order.get("created_at"),
            "completed_at": order.get("completed_at"),
            "dispute_winner": order.get("dispute_winner"),
            "dispute_reason": order.get("dispute_reason")
        }
    }


# ==================== PAYOUT SETTINGS API ====================

@router.get("/admin/payout-settings")
async def get_payout_settings(user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Get payout rules and settings"""
    settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    if not settings:
        settings = {
            "rules": """📋 ПРАВИЛА ПОКУПКИ КРИПТОВАЛЮТЫ

1. Оплата производится строго на указанные реквизиты
2. После оплаты нажмите кнопку "Я оплатил" и дождитесь подтверждения
3. Не закрывайте страницу до завершения сделки
4. При возникновении проблем - откройте спор
5. Мошеннические действия приводят к блокировке аккаунта

⚠️ Внимание: возврат средств возможен только через спор""",
            "base_rate": 100.0,
            "sell_rate": 110.0,
            "dispute_window_days": 5
        }
    return settings


@router.put("/admin/payout-settings")
async def update_payout_settings(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p"]))
):
    """Update payout rules and settings"""
    now = datetime.now(timezone.utc).isoformat()
    
    await db.settings.update_one(
        {"type": "payout_settings"},
        {"$set": {
            "type": "payout_settings",
            "rules": data.get("rules", ""),
            "base_rate": data.get("base_rate", 100.0),
            "sell_rate": data.get("sell_rate", 110.0),
            "dispute_window_days": data.get("dispute_window_days", 5),
            "updated_at": now,
            "updated_by": user["id"]
        }},
        upsert=True
    )
    
    return {"status": "ok"}


@router.get("/payout-settings/public")
async def get_public_payout_settings():
    """Get public payout settings (rules text and sell rate for buyers)"""
    settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    if not settings:
        settings = {
            "rules": "Правила покупки криптовалюты будут показаны здесь.",
            "sell_rate": 110.0,
            "base_rate": 100.0
        }
    return {
        "rules": settings.get("rules", ""),
        "sell_rate": settings.get("sell_rate", 110.0),
        "base_rate": settings.get("base_rate", 100.0)
    }


# ==================== ADMIN CRYPTO PAYOUTS API ====================

@router.get("/admin/platform-balance")
async def get_platform_balance(user: dict = Depends(require_role(["admin"]))):
    """Get platform USDT balance"""
    balance_doc = await db.settings.find_one({"type": "platform_balance"}, {"_id": 0})
    return {
        "balance_usdt": balance_doc.get("balance_usdt", 0) if balance_doc else 0
    }


@router.get("/admin/crypto-payouts")
async def admin_get_crypto_payouts(
    status: str = None,
    user: dict = Depends(require_role(["admin", "mod_p2p"]))
):
    """Get all crypto orders for admin/mod_p2p"""
    query = {}
    if status == "active":
        query["status"] = {"$in": ["pending", "paid", "waiting"]}
    elif status == "dispute":
        query["status"] = "dispute"
    elif status == "completed":
        query["status"] = "completed"
    elif status == "cancelled":
        query["status"] = "cancelled"
    
    orders = await db.crypto_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    # Enrich with merchant and buyer info
    for order in orders:
        merchant = await db.merchants.find_one({"id": order.get("merchant_id")}, {"_id": 0, "nickname": 1, "merchant_name": 1})
        if merchant:
            order["merchant_nickname"] = merchant.get("nickname") or merchant.get("merchant_name")
        
        conv = await db.unified_conversations.find_one(
            {"related_id": order["id"]},
            {"_id": 0, "id": 1}
        )
        order["conversation_id"] = conv["id"] if conv else None
    
    return orders


@router.get("/msg/admin/crypto-payouts")
async def admin_get_crypto_payout_conversations(
    user: dict = Depends(require_role(["admin", "mod_p2p"]))
):
    """Get crypto order conversations for admin panel messages"""
    convs = await db.unified_conversations.find(
        {
            "type": "crypto_order",
            "status": {"$nin": ["completed", "cancelled", "archived"]}
        },
        {"_id": 0}
    ).sort("updated_at", -1).to_list(200)
    
    for conv in convs:
        unread = await db.unified_messages.count_documents({
            "conversation_id": conv["id"],
            "read_by": {"$ne": user["id"]}
        })
        conv["unread_count"] = unread
        
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"]},
            {"_id": 0, "content": 1, "sender_nickname": 1, "created_at": 1},
            sort=[("created_at", -1)]
        )
        if last_msg:
            conv["last_message"] = last_msg
        
        order = await db.crypto_orders.find_one(
            {"id": conv.get("related_id")},
            {"_id": 0}
        )
        if order:
            conv["order"] = order
    
    return convs


@router.post("/admin/crypto-payouts/{order_id}/update-status")
async def admin_update_crypto_payout_status(
    order_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p"]))
):
    """Update crypto order status"""
    new_status = data.get("status")
    if new_status not in ["pending", "paid", "completed", "cancelled", "dispute"]:
        raise HTTPException(status_code=400, detail="Неверный статус")
    
    order = await db.crypto_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    
    update_data = {
        "status": new_status, 
        "updated_at": now_iso
    }
    
    offer = await db.crypto_sell_offers.find_one({"id": order.get("offer_id")}, {"_id": 0})
    
    if new_status == "completed":
        dispute_window = now + timedelta(days=5)
        update_data["completed_at"] = now_iso
        update_data["dispute_window_until"] = dispute_window.isoformat()
        
        usdt_amount = order.get("amount_usdt", 0)
        
        # Transfer USDT to buyer
        await db.traders.update_one(
            {"id": order.get("buyer_id")},
            {"$inc": {"balance_usdt": usdt_amount}}
        )
        
        # Deduct from platform balance
        await db.settings.update_one(
            {"type": "platform_balance"},
            {"$inc": {"balance_usdt": -usdt_amount}},
            upsert=True
        )
        
        if offer:
            await db.crypto_sell_offers.update_one(
                {"id": order.get("offer_id")},
                {"$set": {"status": "sold", "updated_at": now_iso}}
            )
    
    elif new_status == "cancelled":
        if offer:
            await db.crypto_sell_offers.update_one(
                {"id": order.get("offer_id")},
                {"$set": {
                    "status": "active",
                    "current_order_id": None,
                    "updated_at": now_iso
                }}
            )
    
    # Add to status history
    await db.crypto_orders.update_one(
        {"id": order_id},
        {
            "$set": update_data,
            "$push": {
                "status_history": {
                    "status": new_status,
                    "timestamp": now_iso,
                    "by": user.get("login", user.get("id")),
                    "role": user.get("admin_role", "admin"),
                    "action": f"status_changed_to_{new_status}"
                }
            }
        }
    )
    
    # Update conversation status
    await db.unified_conversations.update_one(
        {"related_id": order_id},
        {"$set": {"status": new_status, "updated_at": now_iso}}
    )
    
    # Add system message
    conv = await db.unified_conversations.find_one({"related_id": order_id}, {"_id": 0, "id": 1})
    if conv:
        status_labels = {
            "pending": "ожидает оплаты",
            "paid": "оплачен, ожидает подтверждения",
            "completed": "завершён ✅ USDT переведены покупателю",
            "cancelled": "отменён ❌ Заявка возвращена на витрину",
            "dispute": "открыт спор ⚠️"
        }
        msg_content = f"Статус заказа изменён: {status_labels.get(new_status, new_status)}"
        
        if new_status == "completed":
            msg_content += f"\n\n📅 Мерчант может открыть спор в течение 5 дней (до {(now + timedelta(days=5)).strftime('%d.%m.%Y')})"
        
        sys_msg = {
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_nickname": "Система",
            "sender_role": "system",
            "content": msg_content,
            "is_system": True,
            "created_at": now_iso
        }
        await db.unified_messages.insert_one(sys_msg)
    
    return {"status": "ok", "new_status": new_status}


@router.post("/merchant/crypto-orders/{order_id}/dispute")
async def merchant_open_crypto_dispute(
    order_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """Merchant opens a dispute on a completed crypto order (within 5 days)"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    order = await db.crypto_orders.find_one(
        {"id": order_id, "merchant_id": user["id"]},
        {"_id": 0}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    if order.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Спор можно открыть только по завершённой сделке")
    
    # Check dispute window
    dispute_until = order.get("dispute_window_until")
    if dispute_until:
        deadline = datetime.fromisoformat(dispute_until.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > deadline:
            raise HTTPException(status_code=400, detail="Срок для открытия спора истёк (5 дней)")
    
    reason = data.get("reason", "Мерчант открыл спор")
    now = datetime.now(timezone.utc).isoformat()
    
    # Update order status
    await db.crypto_orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "status": "dispute",
                "dispute_opened_at": now,
                "dispute_reason": reason,
                "dispute_type": "platform_vs_merchant",
                "updated_at": now
            },
            "$push": {
                "status_history": {
                    "status": "dispute",
                    "timestamp": now,
                    "by": user.get("login", user.get("id")),
                    "role": "merchant",
                    "reason": reason,
                    "action": "merchant_opened_dispute"
                }
            }
        }
    )
    
    conv = await db.unified_conversations.find_one({"related_id": order_id}, {"_id": 0})
    
    if conv:
        await db.unified_conversations.update_one(
            {"id": conv["id"]},
            {
                "$set": {
                    "status": "dispute",
                    "dispute_type": "platform_vs_merchant",
                    "updated_at": now
                },
                "$addToSet": {"participants": user["id"]}
            }
        )
        
        sys_msg = {
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_nickname": "Система",
            "sender_role": "system",
            "content": f"""🔴 СПОР: ПЛАТФОРМА ↔ МЕРЧАНТ

⚠️ Мерчант @{user.get('nickname', user.get('login'))} открыл спор!

📝 Причина: {reason}

━━━━━━━━━━━━━━━━━━━━━━━
📋 ДАННЫЕ СДЕЛКИ:
• USDT покупателю: {order.get('amount_usdt', 0)} USDT
• USDT от мерчанта: {order.get('usdt_from_merchant', order.get('amount_usdt', 0))} USDT
• К оплате: {order.get('amount_rub', 0):.2f} ₽
• Курс продажи: {order.get('sell_rate', order.get('rate', 0)):.2f} ₽/USDT
━━━━━━━━━━━━━━━━━━━━━━━
👤 Мерчант: @{order.get('merchant_nickname', 'N/A')}
🛒 Покупатель: @{order.get('buyer_nickname', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━

💳 Реквизиты: {order.get('card_number') or order.get('sbp_phone', 'N/A')} ({order.get('bank_name', 'N/A')})

⚖️ Решение спора:
• Мерчант выигрывает → Платформа выплачивает USDT мерчанту
• Мерчант проигрывает → USDT остаются на платформе

📂 Полная история сделки сохранена для доказательств.""",
            "is_system": True,
            "created_at": now
        }
        await db.unified_messages.insert_one(sys_msg)
        
        return {"status": "dispute_opened", "conversation_id": conv["id"]}
    else:
        raise HTTPException(status_code=404, detail="Чат сделки не найден")


@router.post("/admin/crypto-payouts/{order_id}/resolve-dispute")
async def admin_resolve_crypto_dispute(
    order_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p"]))
):
    """Resolve a crypto payout dispute"""
    winner = data.get("winner")
    if winner not in ["merchant", "platform"]:
        raise HTTPException(status_code=400, detail="winner должен быть 'merchant' или 'platform'")
    
    order = await db.crypto_orders.find_one({"id": order_id, "status": "dispute"}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Спор не найден")
    
    now = datetime.now(timezone.utc).isoformat()
    new_status = "dispute_resolved"
    
    await db.crypto_orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "status": new_status,
                "dispute_winner": winner,
                "dispute_resolved_at": now,
                "dispute_resolved_by": user.get("login"),
                "updated_at": now
            },
            "$push": {
                "status_history": {
                    "status": new_status,
                    "timestamp": now,
                    "by": user.get("login"),
                    "role": user.get("admin_role"),
                    "action": f"dispute_resolved_winner_{winner}"
                }
            }
        }
    )
    
    amount_usdt = order.get("amount_usdt", 0)
    usdt_from_merchant = order.get("usdt_from_merchant", amount_usdt)
    
    if winner == "merchant":
        await db.merchants.update_one(
            {"id": order.get("merchant_id")},
            {"$inc": {"balance_usdt": usdt_from_merchant}}
        )
        await db.settings.update_one(
            {"type": "platform_balance"},
            {"$inc": {"balance_usdt": -usdt_from_merchant}},
            upsert=True
        )
        result_msg = f"✅ СПОР РЕШЁН В ПОЛЬЗУ МЕРЧАНТА\n\n{usdt_from_merchant} USDT возвращены мерчанту @{order.get('merchant_nickname')} с баланса платформы."
    else:
        result_msg = f"✅ СПОР РЕШЁН В ПОЛЬЗУ ПЛАТФОРМЫ\n\n{usdt_from_merchant} USDT остаются на балансе платформы."
    
    conv = await db.unified_conversations.find_one({"related_id": order_id}, {"_id": 0})
    if conv:
        await db.unified_conversations.update_one(
            {"id": conv["id"]},
            {"$set": {"status": new_status, "updated_at": now}}
        )
        
        sys_msg = {
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_nickname": "Система",
            "sender_role": "system",
            "content": result_msg,
            "is_system": True,
            "created_at": now
        }
        await db.unified_messages.insert_one(sys_msg)
    
    return {"status": "resolved", "winner": winner}
