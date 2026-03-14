from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from core.auth import require_role, get_current_user
from core.database import db

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
            # Limits - show in both RUB and USDT
            min_rub = offer.get("min_amount_rub", 0)
            max_rub = offer.get("amount_rub", 0)  # Max is the full offer amount
            offer["min_amount"] = round(min_rub / sell_rate, 2) if min_rub else 0
            offer["max_amount"] = round(max_rub / sell_rate, 2) if max_rub else usdt_for_buyer
            offer["min_amount_rub"] = min_rub
            offer["max_amount_rub"] = max_rub
            result.append(offer)
        # Old format offers
        elif offer.get("available_amount", 0) > 0:
            offer["amount_usdt"] = offer.get("available_amount", 0)
            offer["sell_rate"] = offer.get("rate", sell_rate)
            offer["min_amount"] = offer.get("min_amount", 0)
            offer["max_amount"] = offer.get("max_amount", offer.get("available_amount", 0))
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
    
    # Freeze USDT on merchant balance (move from available to frozen)
    await db.merchants.update_one(
        {"id": user["id"]},
        {"$inc": {"balance_usdt": -usdt_to_deduct, "frozen_balance": usdt_to_deduct}}
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
    
    # Return frozen funds back to available balance
    usdt_amount = offer.get("usdt_from_merchant", offer.get("available_amount", 0))
    await db.merchants.update_one(
        {"id": user["id"]},
        {
            "$inc": {
                "balance_usdt": usdt_amount,
                "frozen_balance": -usdt_amount
            }
        }
    )
    
    # Mark offer as cancelled
    await db.crypto_sell_offers.update_one(
        {"id": offer_id},
        {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"status": "cancelled"}


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
