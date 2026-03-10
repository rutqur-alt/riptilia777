"""
Trader routes - profile, stats, transactions, referrals
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import uuid
from typing import Optional
from pydantic import BaseModel

from core.database import db
from core.auth import require_role, hash_password, verify_password
from models.schemas import (
    ChangePasswordRequest, Toggle2FARequest, TraderResponse, TraderUpdate
)

router = APIRouter(tags=["traders"])


# Payment Detail Models
class PaymentDetailCreate(BaseModel):
    payment_type: Optional[str] = "card"
    bank_name: Optional[str] = None
    card_number: Optional[str] = None
    holder_name: Optional[str] = None
    phone_number: Optional[str] = None
    operator_name: Optional[str] = None
    qr_link: Optional[str] = None
    qr_data: Optional[str] = None
    comment: Optional[str] = None
    min_amount_rub: Optional[float] = 100.0
    max_amount_rub: Optional[float] = 500000.0
    daily_limit_rub: Optional[float] = 1500000.0
    priority: Optional[int] = 10
    is_active: Optional[bool] = True


class PaymentDetailUpdate(PaymentDetailCreate):
    pass


@router.post("/traders/change-password")
async def change_password(data: ChangePasswordRequest, user: dict = Depends(require_role(["trader"]))):
    """Change trader's password"""
    trader = await db.traders.find_one({"id": user["id"]})
    
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    # Support both 'password_hash' and 'password' field names
    stored_hash = trader.get("password_hash") or trader.get("password", "")
    if not stored_hash or not verify_password(data.current_password, stored_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не менее 6 символов")
    
    new_hash = hash_password(data.new_password)
    # Update both fields for compatibility
    await db.traders.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": new_hash, "password": new_hash, "password_changed_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"status": "success", "message": "Пароль успешно изменён"}


@router.post("/traders/toggle-2fa")
async def toggle_2fa(data: Toggle2FARequest, user: dict = Depends(require_role(["trader"]))):
    """Enable or disable 2FA for trader"""
    await db.traders.update_one(
        {"id": user["id"]},
        {"$set": {"two_fa_enabled": data.enabled, "two_fa_updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"status": "success", "two_fa_enabled": data.enabled}


@router.get("/traders/me", response_model=TraderResponse)
async def get_trader_profile(user: dict = Depends(require_role(["trader"]))):
    trader = await db.traders.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0, "password": 0})
    
    if not trader:
        raise HTTPException(status_code=404, detail="Трейдер не найден")
    
    # Generate referral code if missing
    if not trader.get("referral_code"):
        ref_code = f"T{uuid.uuid4().hex[:6].upper()}"
        await db.traders.update_one(
            {"id": user["id"]},
            {"$set": {"referral_code": ref_code, "referral_earnings": 0.0}}
        )
        trader["referral_code"] = ref_code
        trader["referral_earnings"] = 0.0
    
    if "has_shop" not in trader:
        trader["has_shop"] = bool(trader.get("shop_settings", {}).get("approved", False))
    
    return trader


@router.get("/traders/stats")
async def get_trader_stats(user: dict = Depends(require_role(["trader"]))):
    """Get sales and purchases statistics for current trader"""
    # Продажи (как трейдер)
    sales = await db.trades.find({"trader_id": user["id"], "status": "completed"}).to_list(1000)
    sales_count = len(sales)
    sales_volume = sum(t.get("amount_usdt", 0) for t in sales)
    
    # Покупки (как покупатель)
    purchases = await db.trades.find({"buyer_id": user["id"], "buyer_type": "trader", "status": "completed"}).to_list(1000)
    purchases_count = len(purchases)
    purchases_volume = sum(t.get("amount_usdt", 0) for t in purchases)
    
    # Общее количество успешных сделок (продажи + покупки)
    successful_trades = sales_count + purchases_count
    
    return {
        "salesCount": sales_count,
        "salesVolume": sales_volume,
        "purchasesCount": purchases_count,
        "purchasesVolume": purchases_volume,
        "successful_trades": successful_trades  # Для проверки доступа к покупке
    }


@router.get("/traders/transactions")
async def get_trader_transactions(user: dict = Depends(require_role(["trader"]))):
    """Get all financial transactions for the trader"""
    transactions = []
    trader_id = user["id"]
    
    # 1. OFFER CREATION - debits
    offers = await db.offers.find({"trader_id": trader_id}, {"_id": 0}).to_list(500)
    for offer in offers:
        reserved_commission = offer.get("reserved_commission", offer["amount_usdt"] * 0.01)
        total_reserved = offer["amount_usdt"] + reserved_commission
        transactions.append({
            "id": f"offer_{offer['id'][:8]}",
            "type": "offer_created",
            "amount": -total_reserved,
            "description": f"Создание объявления на {offer['amount_usdt']} USDT",
            "reference_type": "offer",
            "reference_id": offer["id"],
            "created_at": offer["created_at"],
            "status": "active" if offer.get("is_active") else "closed"
        })
        
        if not offer.get("is_active"):
            available = offer.get("available_usdt", 0)
            sold = offer.get("sold_usdt", 0)
            commission_rate = offer.get("commission_rate", 1.0)
            correct_commission = sold * (commission_rate / 100)
            commission_refund = reserved_commission - correct_commission
            total_refund = available + max(0, commission_refund)
            
            if total_refund > 0:
                transactions.append({
                    "id": f"offer_close_{offer['id'][:8]}",
                    "type": "offer_closed",
                    "amount": total_refund,
                    "description": f"Закрытие объявления (возврат {available:.2f} + комиссия {max(0, commission_refund):.2f})",
                    "reference_type": "offer",
                    "reference_id": offer["id"],
                    "created_at": offer.get("updated_at", offer["created_at"]),
                    "status": "completed"
                })
    
    # 2. P2P TRADES - commissions
    sales = await db.trades.find({"trader_id": trader_id, "status": "completed"}, {"_id": 0}).to_list(500)
    for sale in sales:
        commission = sale.get("trader_commission", 0)
        if commission > 0:
            transactions.append({
                "id": f"sale_comm_{sale['id']}",
                "type": "commission",
                "amount": -commission,
                "description": f"Комиссия P2P объявления ({sale['amount_usdt']} USDT)",
                "reference_type": "trade",
                "reference_id": sale["id"],
                "created_at": sale.get("completed_at", sale["created_at"]),
                "status": "completed"
            })
    
    # 3. PURCHASES COMPLETED
    purchases = await db.trades.find({
        "buyer_id": trader_id, 
        "buyer_type": "trader", 
        "status": "completed"
    }, {"_id": 0}).to_list(500)
    for purchase in purchases:
        seller = await db.traders.find_one({"id": purchase["trader_id"]}, {"_id": 0, "login": 1})
        seller_info = f" от @{seller['login']}" if seller else ""
        
        transactions.append({
            "id": f"purchase_{purchase['id']}",
            "type": "purchase_completed",
            "amount": purchase["amount_usdt"],
            "description": f"Покупка {purchase['amount_usdt']} USDT{seller_info}",
            "reference_type": "trade",
            "reference_id": purchase["id"],
            "created_at": purchase.get("completed_at", purchase["created_at"]),
            "status": "completed"
        })
    
    # 4. MARKETPLACE PURCHASES - debits
    market_purchases = await db.marketplace_purchases.find({"buyer_id": trader_id}, {"_id": 0}).to_list(500)
    for mp in market_purchases:
        product = await db.marketplace_products.find_one({"id": mp["product_id"]}, {"_id": 0, "title": 1})
        shop = await db.traders.find_one({"id": mp["seller_id"]}, {"_id": 0, "shop_settings": 1})
        shop_name = shop.get("shop_settings", {}).get("name", "Магазин") if shop else "Магазин"
        product_title = product["title"] if product else "Товар"
        
        transactions.append({
            "id": f"market_{mp['id'][:8]}",
            "type": "marketplace_purchase",
            "amount": -mp["total_price"],
            "description": f"Покупка: {product_title[:30]} в {shop_name}",
            "reference_type": "marketplace",
            "reference_id": mp["id"],
            "created_at": mp["created_at"],
            "status": mp["status"]
        })
    
    # 5. MARKETPLACE SALES - credits
    market_sales = await db.marketplace_purchases.find({
        "seller_id": trader_id,
        "status": {"$in": ["completed", "delivered"]}
    }, {"_id": 0}).to_list(500)
    for ms in market_sales:
        product = await db.marketplace_products.find_one({"id": ms["product_id"]}, {"_id": 0, "title": 1})
        buyer = await db.traders.find_one({"id": ms["buyer_id"]}, {"_id": 0, "login": 1})
        product_title = product["title"] if product else "Товар"
        buyer_info = f" от @{buyer['login']}" if buyer else ""
        
        commission_rate = ms.get("commission_rate", 0.05)
        commission_amount = ms["total_price"] * commission_rate
        seller_receives = ms["total_price"] - commission_amount
        
        transactions.append({
            "id": f"market_sale_{ms['id'][:8]}",
            "type": "marketplace_sale",
            "amount": seller_receives,
            "description": f"Продажа: {product_title[:30]}{buyer_info}",
            "reference_type": "marketplace",
            "reference_id": ms["id"],
            "created_at": ms.get("completed_at", ms["created_at"]),
            "status": "completed"
        })
        
        if commission_amount > 0:
            transactions.append({
                "id": f"market_comm_{ms['id'][:8]}",
                "type": "commission",
                "amount": -commission_amount,
                "description": f"Комиссия маркетплейса ({commission_rate*100:.1f}%)",
                "reference_type": "marketplace",
                "reference_id": ms["id"],
                "created_at": ms.get("completed_at", ms["created_at"]),
                "status": "completed"
            })
    
    # 6. TRANSFERS SENT
    transfers_sent = await db.transfers.find({"from_id": trader_id}, {"_id": 0}).to_list(500)
    for tr in transfers_sent:
        recipient_info = f"@{tr.get('to_nickname', 'Unknown')}"
        transactions.append({
            "id": f"transfer_out_{tr['id'][:8]}",
            "type": "transfer_sent",
            "amount": -tr["amount"],
            "description": f"Перевод {recipient_info}",
            "reference_type": "transfer",
            "reference_id": tr["id"],
            "created_at": tr["created_at"],
            "status": "completed"
        })
    
    # 7. TRANSFERS RECEIVED
    transfers_received = await db.transfers.find({"to_id": trader_id}, {"_id": 0}).to_list(500)
    for tr in transfers_received:
        sender_info = f"@{tr.get('from_nickname', 'Unknown')}"
        transactions.append({
            "id": f"transfer_in_{tr['id'][:8]}",
            "type": "transfer_received",
            "amount": tr["amount"],
            "description": f"Перевод от {sender_info}",
            "reference_type": "transfer",
            "reference_id": tr["id"],
            "created_at": tr["created_at"],
            "status": "completed"
        })
    
    # 8. REFERRAL EARNINGS
    trader = await db.traders.find_one({"id": trader_id}, {"_id": 0})
    if trader and trader.get("referral_earnings", 0) > 0:
        transactions.append({
            "id": "referral_earnings",
            "type": "referral_bonus",
            "amount": trader["referral_earnings"],
            "description": "Реферальные начисления",
            "reference_type": "referral",
            "reference_id": trader.get("referral_code", ""),
            "created_at": trader.get("created_at", datetime.now(timezone.utc).isoformat()),
            "status": "completed"
        })
    
    transactions.sort(key=lambda x: x.get("created_at") or "1970-01-01", reverse=True)
    
    return transactions


@router.get("/traders/referral")
async def get_trader_referral_info(user: dict = Depends(require_role(["trader"]))):
    """Get referral info and referred users with multi-level data"""
    trader = await db.traders.find_one({"id": user["id"]}, {"_id": 0})
    
    # Get direct referrals (level 1)
    referred_traders = await db.traders.find(
        {"referred_by": user["id"]},
        {"_id": 0, "id": 1, "login": 1, "nickname": 1, "created_at": 1}
    ).to_list(100)
    
    referred_merchants = await db.merchants.find(
        {"referred_by": user["id"]},
        {"_id": 0, "id": 1, "login": 1, "merchant_name": 1, "created_at": 1}
    ).to_list(100)
    
    # Get referral balance (multi-level system)
    referral_balance = trader.get("referral_balance_usdt", 0)
    
    # Get referral history from new system
    referral_history = await db.referral_history.find(
        {"referrer_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    # Calculate stats by level
    level_stats = []
    for level in [1, 2, 3]:
        count = await db.referrals.count_documents({
            "referrer_id": user["id"],
            "level": level
        })
        level_stats.append({"level": level, "count": count})
    
    # Build referral link (use relative path so it works on any domain)
    site_url = ""
    ref_code = trader.get("referral_code", "")
    
    return {
        "referral_code": ref_code,
        "referral_link": f"{site_url}/auth?ref={ref_code}",
        "referral_earnings": trader.get("referral_earnings", 0),
        "referral_balance_usdt": referral_balance,
        "referrals_count": len(referred_traders) + len(referred_merchants),
        "referred_traders": referred_traders,
        "referred_merchants": referred_merchants,
        "level_stats": level_stats,
        "history": referral_history
    }


@router.put("/traders/me")
async def update_trader_profile(data: TraderUpdate, user: dict = Depends(require_role(["trader"]))):
    """Update trader profile"""
    update_data = {}
    if data.display_name is not None:
        update_data["display_name"] = data.display_name
        update_data["nickname"] = data.display_name
    if data.accepted_merchant_types is not None:
        update_data["accepted_merchant_types"] = data.accepted_merchant_types
    
    if update_data:
        await db.traders.update_one({"id": user["id"]}, {"$set": update_data})
    
    return {"status": "updated"}


@router.post("/traders/deposit")
async def create_deposit_request(amount: float = 0, user: dict = Depends(require_role(["trader"]))):
    """Test deposit - add USDT to trader balance (for testing/demo purposes)"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")
    if amount > 100000:
        raise HTTPException(status_code=400, detail="Максимальная сумма пополнения: 100,000 USDT")

    await db.traders.update_one(
        {"id": user["id"]},
        {"$inc": {"balance_usdt": amount}}
    )

    # Log the deposit transaction
    await db.transactions.insert_one({
        "id": str(uuid.uuid4()),
        "trader_id": user["id"],
        "type": "deposit",
        "amount": amount,
        "description": f"Пополнение баланса на {amount} USDT",
        "from_platform": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    trader = await db.traders.find_one({"id": user["id"]}, {"_id": 0, "balance_usdt": 1})
    return {
        "status": "success",
        "message": f"Баланс пополнен на {amount} USDT",
        "new_balance": trader.get("balance_usdt", 0)
    }


@router.get("/traders/me/stats")
async def get_trader_detailed_stats(user: dict = Depends(require_role(["trader"]))):
    """Get detailed statistics for trader"""
    trades = await db.trades.find({"trader_id": user["id"]}).to_list(1000)
    
    completed = sum(1 for t in trades if t.get("status") == "completed")
    cancelled = sum(1 for t in trades if t.get("status") == "cancelled")
    disputed = sum(1 for t in trades if t.get("status") == "disputed")
    
    total_volume_usdt = sum(t.get("amount_usdt", 0) for t in trades if t.get("status") == "completed")
    total_volume_rub = sum(t.get("amount_rub", 0) for t in trades if t.get("status") == "completed")
    
    completed_trades = [t for t in trades if t.get("status") == "completed"]
    
    # Calculate average rate - use price_rub or calculate from amounts
    total_rate = 0
    rate_count = 0
    for t in completed_trades:
        rate = t.get("price_rub") or t.get("rate")
        if not rate and t.get("amount_rub") and t.get("amount_usdt"):
            rate = t["amount_rub"] / t["amount_usdt"]
        if rate and rate > 0:
            total_rate += rate
            rate_count += 1
    avg_rate = total_rate / rate_count if rate_count > 0 else 0
    
    avg_time_minutes = 0
    if completed_trades:
        times = []
        for t in completed_trades:
            if t.get("completed_at") and t.get("created_at"):
                try:
                    start = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(t["completed_at"].replace("Z", "+00:00"))
                    times.append((end - start).total_seconds() / 60)
                except:
                    pass
        if times:
            avg_time_minutes = sum(times) / len(times)
    
    return {
        "total_trades": len(trades),
        "completed_trades": completed,
        "cancelled_trades": cancelled,
        "disputed_trades": disputed,
        "total_volume_usdt": total_volume_usdt,
        "total_volume_rub": total_volume_rub,
        "avg_rate": avg_rate,
        "avg_time_minutes": round(avg_time_minutes, 1)
    }



# ================== PAYMENT DETAILS ==================

@router.get("/trader/payment-details")
async def get_payment_details(user: dict = Depends(require_role(["trader"]))):
    """Получить платёжные реквизиты трейдера"""
    trader_id = user["id"]
    
    details = await db.payment_details.find(
        {"trader_id": trader_id},
        {"_id": 0}
    ).to_list(50)
    
    return details


@router.post("/trader/payment-details")
async def create_payment_detail(
    data: PaymentDetailCreate,
    user: dict = Depends(require_role(["trader"]))
):
    """Добавить платёжный реквизит"""
    trader_id = user["id"]
    
    detail = {
        "id": f"pd_{uuid.uuid4().hex[:12]}",
        "trader_id": trader_id,
        "payment_type": data.payment_type or "card",
        "bank_name": data.bank_name,
        "card_number": data.card_number,
        "holder_name": data.holder_name,
        "phone_number": data.phone_number,
        "operator_name": data.operator_name,
        "qr_link": data.qr_link or data.qr_data,
        "qr_data": data.qr_data or data.qr_link,
        "comment": data.comment,
        "is_active": data.is_active if data.is_active is not None else True,
        "min_amount_rub": data.min_amount_rub or 100,
        "max_amount_rub": data.max_amount_rub or 500000,
        "daily_limit_rub": data.daily_limit_rub or 1500000,
        "used_today_rub": 0,
        "priority": data.priority or 10,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.payment_details.insert_one(detail)
    detail.pop("_id", None)
    
    return {"success": True, "detail": detail}


@router.put("/trader/payment-details/{detail_id}")
async def update_payment_detail(
    detail_id: str,
    data: PaymentDetailUpdate,
    user: dict = Depends(require_role(["trader"]))
):
    """Обновить платёжный реквизит"""
    trader_id = user["id"]
    
    existing = await db.payment_details.find_one({
        "id": detail_id,
        "trader_id": trader_id
    })
    
    if not existing:
        raise HTTPException(status_code=404, detail="Реквизит не найден")
    
    update_data = {
        "payment_type": data.payment_type or existing.get("payment_type"),
        "bank_name": data.bank_name,
        "card_number": data.card_number,
        "holder_name": data.holder_name,
        "phone_number": data.phone_number,
        "operator_name": data.operator_name,
        "qr_link": data.qr_link or data.qr_data,
        "qr_data": data.qr_data or data.qr_link,
        "comment": data.comment,
        "is_active": data.is_active if data.is_active is not None else existing.get("is_active", True),
        "min_amount_rub": data.min_amount_rub or existing.get("min_amount_rub", 100),
        "max_amount_rub": data.max_amount_rub or existing.get("max_amount_rub", 500000),
        "daily_limit_rub": data.daily_limit_rub or existing.get("daily_limit_rub", 1500000),
        "priority": data.priority or existing.get("priority", 10),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.payment_details.update_one(
        {"id": detail_id, "trader_id": trader_id},
        {"$set": update_data}
    )
    
    return {"success": True, "message": "Реквизит обновлён"}


@router.delete("/trader/payment-details/{detail_id}")
async def delete_payment_detail(
    detail_id: str,
    user: dict = Depends(require_role(["trader"]))
):
    """Удалить платёжный реквизит"""
    trader_id = user["id"]
    
    result = await db.payment_details.delete_one({
        "id": detail_id,
        "trader_id": trader_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Реквизит не найден")
    
    return {"success": True, "message": "Реквизит удалён"}
