from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from core.database import db
from core.auth import get_current_user
from .utils import create_marketplace_notification

router = APIRouter()

# ==================== PURCHASES ====================

@router.post("/products/{product_id}/buy")
async def buy_product(
    product_id: str,
    quantity: int = 1,
    variant_quantity: Optional[int] = None,
    purchase_type: str = "instant",
    user: dict = Depends(get_current_user)
):
    """Buy a product with auto-delivery or via guarantor escrow"""
    # Block merchants from making purchases
    if user.get("role") == "merchant":
        raise HTTPException(status_code=403, detail="Мерчанты не могут совершать покупки в маркетплейсе")
    if quantity < 1:
        raise HTTPException(status_code=400, detail="Количество должно быть больше 0")

    product = await db.shop_products.find_one({"id": product_id, "is_active": True})
    product_collection = db.shop_products

    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    seller_id = product.get("seller_id")
    seller = await db.traders.find_one({"id": seller_id}, {"_id": 0})
    if not seller:
        raise HTTPException(status_code=404, detail="Продавец не найден")

    if seller.get("shop_settings", {}).get("is_blocked"):
        raise HTTPException(status_code=403, detail="Магазин заблокирован")

    allow_direct = seller.get("shop_settings", {}).get("allow_direct_purchase", True)
    if purchase_type == "instant" and not allow_direct:
        raise HTTPException(status_code=400, detail="Продавец разрешает только покупки через гаранта")

    available_stock = len(product.get("auto_content", [])) - product.get("reserved_count", 0)
    if available_stock < quantity:
        raise HTTPException(status_code=400, detail=f"Недостаточно товара. Доступно: {available_stock} шт.")

    total_price = product["price"] * quantity

    if variant_quantity:
        price_variants = product.get("price_variants", [])
        matching_variant = next((v for v in price_variants if v["quantity"] == variant_quantity), None)
        if matching_variant:
            total_price = matching_variant["price"]
            quantity = variant_quantity
    else:
        price_variants = product.get("price_variants", [])
        matching_variant = next((v for v in price_variants if v["quantity"] == quantity), None)
        if matching_variant:
            total_price = matching_variant["price"]

    settings = await db.commission_settings.find_one({}, {"_id": 0})
    guarantor_percent = settings.get("guarantor_commission_percent", 3.0) if settings else 3.0
    guarantor_auto_days = settings.get("guarantor_auto_complete_days", 3) if settings else 3

    guarantor_fee = 0
    total_with_guarantor = total_price
    if purchase_type == "guarantor":
        guarantor_fee = total_price * (guarantor_percent / 100)
        total_with_guarantor = total_price + guarantor_fee

    buyer = await db.traders.find_one({"id": user["id"]}, {"_id": 0})
    buyer_collection = "traders"
    if not buyer:
        buyer = await db.merchants.find_one({"id": user["id"]}, {"_id": 0})
        buyer_collection = "merchants"
    if not buyer:
        raise HTTPException(status_code=403, detail="Только пользователи могут покупать товары")

    required_amount = total_with_guarantor if purchase_type == "guarantor" else total_price
    if buyer.get("balance_usdt", 0) < required_amount:
        raise HTTPException(status_code=400, detail=f"Недостаточно средств. Необходимо: {required_amount:.2f} USDT, у вас: {buyer.get('balance_usdt', 0):.2f} USDT")

    commission_rate = seller.get("shop_settings", {}).get("commission_rate", 5.0)
    platform_commission = total_price * (commission_rate / 100)
    seller_receives = total_price - platform_commission

    delivered_content = []
    auto_content = product.get("auto_content", [])
    for i in range(quantity):
        if auto_content and len(auto_content) > i:
            delivered_content.append(auto_content[i])

    purchase_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    if purchase_type == "instant":
        # ============ INSTANT PURCHASE ============
        if delivered_content:
            await product_collection.update_one(
                {"id": product_id},
                {"$set": {"auto_content": auto_content[quantity:]}}
            )

        await product_collection.update_one(
            {"id": product_id},
            {"$inc": {"quantity": -quantity, "sold_count": quantity}}
        )

        # Deduct from buyer (could be trader or merchant)
        buyer_db = db.traders if buyer_collection == "traders" else db.merchants
        await buyer_db.update_one(
            {"id": user["id"]},
            {"$inc": {"balance_usdt": -total_price}}
        )

        await db.traders.update_one(
            {"id": seller_id},
            {"$inc": {"shop_balance": seller_receives}}
        )

        purchase_doc = {
            "id": purchase_id,
            "product_id": product_id,
            "product_name": product["name"],
            "quantity": quantity,
            "buyer_id": user["id"],
            "buyer_nickname": user.get("nickname", user.get("login", "")),
            "seller_id": seller_id,
            "seller_nickname": seller.get("nickname", ""),
            "seller_type": "trader",
            "price_per_unit": product["price"],
            "total_price": total_price,
            "commission_rate": commission_rate,
            "commission": platform_commission,
            "seller_receives": seller_receives,
            "guarantor_fee": 0,
            "delivered_content": delivered_content,
            "purchase_type": "instant",
            "status": "completed",
            "created_at": now.isoformat(),
            "completed_at": now.isoformat()
        }
        await db.marketplace_purchases.insert_one(purchase_doc)

        await db.commission_payments.insert_one({
            "id": str(uuid.uuid4()),
            "purchase_id": purchase_id,
            "buyer_id": user["id"],
            "seller_id": seller_id,
            "seller_type": "trader",
            "amount": platform_commission,
            "commission_rate": commission_rate,
            "type": "marketplace_instant",
            "created_at": now.isoformat()
        })

        await db.traders.update_one(
            {"id": seller_id},
            {"$inc": {
                "shop_stats.total_sales": total_price,
                "shop_stats.total_orders": 1,
                "shop_stats.total_commission_paid": platform_commission
            }}
        )
        
        # Notify seller about instant purchase
        await create_marketplace_notification(
            seller_id,
            "shop_new_order",
            "Новая покупка в магазине",
            f"Куплен товар '{product['name']}' ({quantity} шт.) на {total_price:.2f} USDT",
            "/trader/shop",
            purchase_id
        )

        return {
            "status": "success",
            "purchase_id": purchase_id,
            "purchase_type": "instant",
            "quantity": quantity,
            "total_price": total_price,
            "commission": platform_commission,
            "delivered_content": delivered_content if delivered_content else None,
            "message": f"Товар куплен! ({quantity} шт.)"
        }

    else:
        # ============ GUARANTOR PURCHASE ============
        await product_collection.update_one(
            {"id": product_id},
            {"$inc": {"reserved_count": quantity}}
        )

        # Deduct from buyer (could be trader or merchant)
        buyer_db = db.traders if buyer_collection == "traders" else db.merchants
        await buyer_db.update_one(
            {"id": user["id"]},
            {"$inc": {"balance_usdt": -total_with_guarantor, "balance_escrow": total_with_guarantor}}
        )

        auto_complete_at = now + timedelta(days=guarantor_auto_days)

        purchase_doc = {
            "id": purchase_id,
            "product_id": product_id,
            "product_name": product["name"],
            "quantity": quantity,
            "buyer_id": user["id"],
            "buyer_nickname": user.get("nickname", user.get("login", "")),
            "seller_id": seller_id,
            "seller_nickname": seller.get("nickname", ""),
            "seller_type": "trader",
            "price_per_unit": product["price"],
            "total_price": total_price,
            "total_with_guarantor": total_with_guarantor,
            "commission_rate": commission_rate,
            "commission": platform_commission,
            "seller_receives": seller_receives,
            "guarantor_fee": guarantor_fee,
            "reserved_content": delivered_content,
            "purchase_type": "guarantor",
            "status": "pending_confirmation",
            "created_at": now.isoformat(),
            "auto_complete_at": auto_complete_at.isoformat()
        }
        await db.marketplace_purchases.insert_one(purchase_doc)
        
        # Notify seller about guarantor order
        await create_marketplace_notification(
            seller_id,
            "shop_new_order",
            "Новый заказ (Гарант)",
            f"Заказ на товар '{product['name']}' ({quantity} шт.) через гаранта",
            "/trader/shop",
            purchase_id
        )

        return {
            "status": "pending_confirmation",
            "purchase_id": purchase_id,
            "purchase_type": "guarantor",
            "quantity": quantity,
            "total_price": total_with_guarantor,
            "auto_complete_at": auto_complete_at.isoformat(),
            "message": "Средства зарезервированы. Товар будет выдан после подтверждения."
        }

@router.get("/my-purchases")
async def get_my_marketplace_purchases(user: dict = Depends(get_current_user)):
    """Get current user's marketplace purchases"""
    purchases = await db.marketplace_purchases.find(
        {"buyer_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return purchases

@router.post("/purchases/{purchase_id}/view")
async def mark_purchase_viewed(purchase_id: str, user: dict = Depends(get_current_user)):
    """Mark purchase as viewed (clear notification badge)"""
    result = await db.marketplace_purchases.update_one(
        {"id": purchase_id, "buyer_id": user["id"]},
        {"$set": {"viewed": True}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Purchase not found")
        
    return {"status": "success"}
