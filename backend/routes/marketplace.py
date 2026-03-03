"""
Marketplace routes - Public marketplace functionality
Routes for browsing shops, products, and making purchases
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


# ==================== SHOPS ====================

@router.get("/shops")
async def get_marketplace_shops(category: Optional[str] = None, search: Optional[str] = None):
    """Get all active shops for marketplace (traders and merchants)"""
    result = []

    trader_query = {
        "has_shop": True,
        "shop_settings.is_active": {"$ne": False},
        "shop_settings.is_blocked": {"$ne": True}
    }
    traders = await db.traders.find(trader_query, {
        "_id": 0,
        "id": 1,
        "nickname": 1,
        "shop_settings": 1,
        "created_at": 1
    }).to_list(100)

    for trader in traders:
        product_count = await db.shop_products.count_documents({
            "seller_id": trader["id"],
            "is_active": True
        })

        products = await db.shop_products.find(
            {"seller_id": trader["id"], "is_active": True},
            {"_id": 0, "auto_content": 1}
        ).to_list(100)
        total_stock = sum(len(p.get("auto_content", [])) for p in products)

        shop_settings = trader.get("shop_settings", {})
        shop_data = {
            "id": trader["id"],
            "nickname": trader.get("nickname", ""),
            "name": shop_settings.get("shop_name", trader.get("nickname", "")),
            "description": shop_settings.get("shop_description", ""),
            "logo": shop_settings.get("shop_logo"),
            "banner": shop_settings.get("shop_banner"),
            "type": "trader_shop",
            "seller_type": "trader",
            "categories": shop_settings.get("categories", []),
            "product_count": product_count,
            "total_stock": total_stock
        }

        if search:
            search_lower = search.lower()
            if search_lower not in shop_data["name"].lower() and search_lower not in shop_data.get("description", "").lower():
                continue

        if category and category not in shop_data.get("categories", []):
            continue

        result.append(shop_data)

    return result


@router.get("/shops/{shop_id}")
async def get_shop_details(shop_id: str):
    """Get trader shop details and its products"""
    shop = await db.traders.find_one({
        "id": shop_id,
        "has_shop": True,
        "shop_settings.is_blocked": {"$ne": True}
    }, {"_id": 0})

    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден или заблокирован")

    products = await db.shop_products.find({
        "seller_id": shop_id,
        "is_active": True
    }, {"_id": 0, "auto_content": 0}).sort("created_at", -1).to_list(100)

    products_with_stock = []
    for product in products:
        full_product = await db.shop_products.find_one(
            {"id": product["id"]}, {"_id": 0, "auto_content": 1, "reserved_count": 1}
        )
        stock_count = len(full_product.get("auto_content", []))
        reserved_count = full_product.get("reserved_count", 0)
        available = stock_count - reserved_count

        if available <= 0:
            continue

        product["stock_count"] = stock_count
        product["reserved_count"] = reserved_count
        products_with_stock.append(product)

    shop_settings = shop.get("shop_settings", {})

    return {
        "shop": {
            "id": shop["id"],
            "nickname": shop.get("nickname", ""),
            "name": shop_settings.get("shop_name", shop.get("nickname", "")),
            "description": shop_settings.get("shop_description", ""),
            "logo": shop_settings.get("shop_logo"),
            "banner": shop_settings.get("shop_banner"),
            "type": "trader_shop",
            "seller_type": "trader",
            "categories": shop_settings.get("categories", []),
            "commission_rate": shop_settings.get("commission_rate", 5.0)
        },
        "products": products_with_stock
    }


# ==================== PRODUCTS ====================

@router.get("/products")
async def get_marketplace_products(
    category: Optional[str] = None,
    shop_id: Optional[str] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort: str = "newest"
):
    """Get all trader shop products with filters"""
    query = {"is_active": True}

    if shop_id:
        query["seller_id"] = shop_id
    if category:
        query["category"] = category
    if min_price is not None:
        query["price"] = {"$gte": min_price}
    if max_price is not None:
        query.setdefault("price", {})["$lte"] = max_price

    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]

    sort_field = "created_at" if sort == "newest" else "price" if sort == "price_asc" else "price" if sort == "price_desc" else "created_at"
    sort_order = -1 if sort in ["newest", "price_desc"] else 1

    products = await db.shop_products.find(query, {"_id": 0, "auto_content": 0}).sort(sort_field, sort_order).to_list(100)

    result = []
    for product in products:
        full_product = await db.shop_products.find_one(
            {"id": product["id"]}, {"_id": 0, "auto_content": 1, "reserved_count": 1, "is_infinite": 1}
        )
        stock_count = len(full_product.get("auto_content", []))
        reserved_count = full_product.get("reserved_count", 0)
        available = stock_count - reserved_count
        is_infinite = full_product.get("is_infinite", False)

        if available <= 0 and not is_infinite:
            continue

        product["stock_count"] = stock_count
        product["reserved_count"] = reserved_count
        product["is_infinite"] = is_infinite

        shop = await db.traders.find_one({"id": product["seller_id"]}, {"_id": 0, "nickname": 1, "shop_settings": 1})
        if shop:
            if shop.get("shop_settings", {}).get("is_blocked"):
                continue
            product["shop_name"] = shop.get("shop_settings", {}).get("shop_name", shop.get("nickname", ""))
            product["shop_nickname"] = shop.get("nickname", "")
        result.append(product)

    return result


@router.get("/products/{product_id}")
async def get_product_details(product_id: str):
    """Get trader shop product details"""
    product = await db.shop_products.find_one({"id": product_id, "is_active": True}, {"_id": 0, "auto_content": 0})

    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    shop = await db.traders.find_one({"id": product.get("seller_id")}, {"_id": 0})
    if shop and shop.get("shop_settings", {}).get("is_blocked"):
        raise HTTPException(status_code=404, detail="Магазин заблокирован")

    full_product = await db.shop_products.find_one(
        {"id": product_id}, {"_id": 0, "auto_content": 1, "reserved_count": 1}
    )
    product["stock_count"] = len(full_product.get("auto_content", []))
    product["reserved_count"] = full_product.get("reserved_count", 0)

    if shop:
        product["shop"] = {
            "id": shop["id"],
            "nickname": shop.get("nickname", ""),
            "name": shop.get("shop_settings", {}).get("shop_name", ""),
            "logo": shop.get("shop_settings", {}).get("shop_logo")
        }

    settings = await db.commission_settings.find_one({}, {"_id": 0})
    guarantor_percent = settings.get("guarantor_commission_percent", 3.0) if settings else 3.0
    product["guarantor_commission_percent"] = guarantor_percent

    return product


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
            "commission_rate": commission_rate,
            "commission": platform_commission,
            "seller_receives": seller_receives,
            "guarantor_fee": guarantor_fee,
            "guarantor_percent": guarantor_percent,
            "total_with_guarantor": total_with_guarantor,
            "reserved_content": delivered_content,
            "delivered_content": None,
            "purchase_type": "guarantor",
            "status": "pending_confirmation",
            "auto_complete_at": auto_complete_at.isoformat(),
            "created_at": now.isoformat(),
            "completed_at": None
        }
        await db.marketplace_purchases.insert_one(purchase_doc)

        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": seller_id,
            "type": "new_guarantor_order",
            "title": "Новый заказ через гаранта",
            "message": f"Покупатель {user.get('nickname', user.get('login', ''))} заказал {product['name']} ({quantity} шт.) на {total_price:.2f} USDT",
            "data": {"purchase_id": purchase_id},
            "read": False,
            "created_at": now.isoformat()
        })

        # Create guarantor chat
        conv_id = str(uuid.uuid4())
        buyer_nick = user.get("nickname", user.get("login", "Покупатель"))
        seller_nick = seller.get("nickname", "Продавец")
        conv_title = f"Гарант: {product['name']} ({seller_nick} → {buyer_nick})"
        
        conv_doc = {
            "id": conv_id,
            "type": "marketplace_guarantor",
            "title": conv_title,
            "status": "active",
            "related_id": purchase_id,
            "purchase_id": purchase_id,
            "product_id": product_id,
            "product_name": product["name"],
            "total_amount": total_price,
            "buyer_id": user["id"],
            "buyer_nickname": buyer_nick,
            "seller_id": seller_id,
            "seller_nickname": seller_nick,
            "participants": [user["id"], seller_id],
            "delete_locked": True,
            "guarantor_auto_complete_at": auto_complete_at.isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        await db.unified_conversations.insert_one(conv_doc)

        system_messages = [
            {
                "id": str(uuid.uuid4()),
                "conversation_id": conv_id,
                "sender_id": "system",
                "sender_nickname": "Система",
                "sender_role": "system",
                "content": f"✅ Заказ #{purchase_id[:8]} создан. Сумма: {total_price:.2f} USDT\n\n📦 Товар: {product['name']} ({quantity} шт.)\n👤 Покупатель: @{user.get('nickname', user.get('login', ''))}\n🏪 Продавец: @{seller.get('nickname', '')}",
                "is_system": True,
                "created_at": now.isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "conversation_id": conv_id,
                "sender_id": "system",
                "sender_nickname": "Система",
                "sender_role": "system",
                "content": "⚖️ К сделке подключен Гарант (Модератор маркетплейса). Он будет следить за транзакцией и поможет в случае проблем.",
                "is_system": True,
                "created_at": now.isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "conversation_id": conv_id,
                "sender_id": "system",
                "sender_nickname": "Система",
                "sender_role": "system",
                "content": f"⚠️ ВНИМАНИЕ: Удаление сообщений в чатах Маркетплейса запрещено!\n\n⏰ Автоматическое завершение: {auto_complete_at.strftime('%d.%m.%Y %H:%M')}\n\nЕсли возникнут проблемы - обратитесь к Гаранту.",
                "is_system": True,
                "created_at": now.isoformat()
            }
        ]
        await db.unified_messages.insert_many(system_messages)

        return {
            "status": "success",
            "purchase_id": purchase_id,
            "conversation_id": conv_id,
            "purchase_type": "guarantor",
            "quantity": quantity,
            "total_price": total_price,
            "guarantor_fee": guarantor_fee,
            "total_with_guarantor": total_with_guarantor,
            "auto_complete_at": auto_complete_at.isoformat(),
            "message": f"Заказ оформлен через гаранта! Подтвердите получение в течение {guarantor_auto_days} дней."
        }


@router.post("/purchases/{purchase_id}/confirm")
async def confirm_guarantor_purchase(purchase_id: str, user: dict = Depends(get_current_user)):
    """Buyer confirms receipt of product, releasing escrow to seller"""
    purchase = await db.marketplace_purchases.find_one({"id": purchase_id}, {"_id": 0})

    if not purchase:
        raise HTTPException(status_code=404, detail="Покупка не найдена")

    if purchase["buyer_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Вы не являетесь покупателем")

    if purchase["status"] != "pending_confirmation":
        raise HTTPException(status_code=400, detail="Покупка уже завершена или отменена")

    if purchase["purchase_type"] != "guarantor":
        raise HTTPException(status_code=400, detail="Эта покупка не через гаранта")

    now = datetime.now(timezone.utc)
    product_id = purchase["product_id"]
    seller_id = purchase["seller_id"]
    quantity = purchase["quantity"]

    reserved_content = purchase.get("reserved_content", [])

    product = await db.shop_products.find_one({"id": product_id})
    if product:
        auto_content = product.get("auto_content", [])
        new_content = [c for c in auto_content if c not in reserved_content]
        await db.shop_products.update_one(
            {"id": product_id},
            {
                "$set": {"auto_content": new_content},
                "$inc": {"reserved_count": -quantity, "quantity": -quantity, "sold_count": quantity}
            }
        )

    total_with_guarantor = purchase.get("total_with_guarantor", purchase["total_price"])
    seller_receives = purchase["seller_receives"]
    guarantor_fee = purchase.get("guarantor_fee", 0)
    platform_commission = purchase["commission"]

    await db.traders.update_one(
        {"id": purchase["buyer_id"]},
        {"$inc": {"balance_escrow": -total_with_guarantor}}
    )

    await db.traders.update_one(
        {"id": seller_id},
        {"$inc": {"shop_balance": seller_receives}}
    )

    await db.marketplace_purchases.update_one(
        {"id": purchase_id},
        {"$set": {
            "status": "completed",
            "delivered_content": reserved_content,
            "completed_at": now.isoformat(),
            "confirmed_by": "buyer"
        }}
    )

    await db.commission_payments.insert_one({
        "id": str(uuid.uuid4()),
        "purchase_id": purchase_id,
        "buyer_id": purchase["buyer_id"],
        "seller_id": seller_id,
        "seller_type": "trader",
        "amount": platform_commission,
        "commission_rate": purchase["commission_rate"],
        "type": "marketplace_guarantor_platform",
        "created_at": now.isoformat()
    })

    if guarantor_fee > 0:
        await db.commission_payments.insert_one({
            "id": str(uuid.uuid4()),
            "purchase_id": purchase_id,
            "buyer_id": purchase["buyer_id"],
            "seller_id": seller_id,
            "seller_type": "trader",
            "amount": guarantor_fee,
            "commission_rate": purchase.get("guarantor_percent", 3.0),
            "type": "marketplace_guarantor_fee",
            "created_at": now.isoformat()
        })

    await db.traders.update_one(
        {"id": seller_id},
        {"$inc": {
            "shop_stats.total_sales": purchase["total_price"],
            "shop_stats.total_orders": 1,
            "shop_stats.total_commission_paid": platform_commission
        }}
    )

    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": seller_id,
        "type": "order_confirmed",
        "title": "Покупатель подтвердил получение",
        "message": f"Заказ #{purchase_id[:8]} завершён. На ваш торговый счёт зачислено {seller_receives:.2f} USDT",
        "data": {"purchase_id": purchase_id},
        "read": False,
        "created_at": now.isoformat()
    })

    return {
        "status": "success",
        "purchase_id": purchase_id,
        "delivered_content": reserved_content,
        "seller_received": seller_receives,
        "message": "Покупка подтверждена! Товар выдан."
    }


@router.post("/purchases/{purchase_id}/cancel")
async def cancel_guarantor_purchase(purchase_id: str, reason: str = "", user: dict = Depends(get_current_user)):
    """Cancel a pending guarantor purchase and refund buyer"""
    purchase = await db.marketplace_purchases.find_one({"id": purchase_id}, {"_id": 0})

    if not purchase:
        raise HTTPException(status_code=404, detail="Покупка не найдена")

    is_admin = user.get("role") == "admin"
    is_buyer = purchase["buyer_id"] == user["id"]

    if not is_buyer and not is_admin:
        raise HTTPException(status_code=403, detail="Только покупатель или администратор может отменить заказ")

    if purchase["status"] != "pending_confirmation":
        raise HTTPException(status_code=400, detail="Покупку нельзя отменить - она уже завершена или отменена")

    if purchase["purchase_type"] != "guarantor":
        raise HTTPException(status_code=400, detail="Мгновенные покупки нельзя отменить")

    now = datetime.now(timezone.utc)
    product_id = purchase["product_id"]
    quantity = purchase["quantity"]
    total_with_guarantor = purchase.get("total_with_guarantor", purchase["total_price"])

    await db.shop_products.update_one(
        {"id": product_id},
        {"$inc": {"reserved_count": -quantity}}
    )

    await db.traders.update_one(
        {"id": purchase["buyer_id"]},
        {"$inc": {"balance_escrow": -total_with_guarantor, "balance_usdt": total_with_guarantor}}
    )

    await db.marketplace_purchases.update_one(
        {"id": purchase_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": now.isoformat(),
            "cancelled_by": user["id"],
            "cancel_reason": reason
        }}
    )

    seller_id = purchase["seller_id"]
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": seller_id,
        "type": "order_cancelled",
        "title": "Заказ отменён",
        "message": f"Заказ #{purchase_id[:8]} на {purchase['product_name']} был отменён. Причина: {reason or 'не указана'}",
        "data": {"purchase_id": purchase_id},
        "read": False,
        "created_at": now.isoformat()
    })

    return {
        "status": "success",
        "purchase_id": purchase_id,
        "refunded_amount": total_with_guarantor,
        "message": "Заказ отменён, средства возвращены"
    }


@router.post("/purchases/{purchase_id}/dispute")
async def open_purchase_dispute(purchase_id: str, reason: str, user: dict = Depends(get_current_user)):
    """Open a dispute for a guarantor purchase"""
    purchase = await db.marketplace_purchases.find_one({"id": purchase_id}, {"_id": 0})

    if not purchase:
        raise HTTPException(status_code=404, detail="Покупка не найдена")

    is_buyer = purchase["buyer_id"] == user["id"]
    is_seller = purchase["seller_id"] == user["id"]

    if not is_buyer and not is_seller:
        raise HTTPException(status_code=403, detail="Только участники сделки могут открыть спор")

    if purchase["status"] not in ["pending_confirmation", "completed"]:
        raise HTTPException(status_code=400, detail="Спор можно открыть только для активных или завершённых заказов")

    if purchase["purchase_type"] != "guarantor":
        raise HTTPException(status_code=400, detail="Споры доступны только для покупок через гаранта")

    now = datetime.now(timezone.utc)

    await db.marketplace_purchases.update_one(
        {"id": purchase_id},
        {"$set": {
            "status": "disputed",
            "dispute_opened_at": now.isoformat(),
            "dispute_opened_by": user["id"],
            "dispute_reason": reason
        }}
    )

    other_party_id = purchase["seller_id"] if is_buyer else purchase["buyer_id"]

    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": other_party_id,
        "type": "dispute_opened",
        "title": "Открыт спор по заказу",
        "message": f"По заказу #{purchase_id[:8]} открыт спор. Причина: {reason}",
        "data": {"purchase_id": purchase_id},
        "read": False,
        "created_at": now.isoformat()
    })

    return {
        "status": "success",
        "purchase_id": purchase_id,
        "message": "Спор открыт. Администратор рассмотрит вашу заявку."
    }


@router.post("/purchases/{purchase_id}/resolve")
async def resolve_purchase_dispute(
    purchase_id: str,
    resolution: str,
    admin_note: str = "",
    user: dict = Depends(get_current_user)
):
    """Admin resolves a disputed purchase"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только администратор может разрешать споры")

    purchase = await db.marketplace_purchases.find_one({"id": purchase_id}, {"_id": 0})

    if not purchase:
        raise HTTPException(status_code=404, detail="Покупка не найдена")

    if purchase["status"] != "disputed":
        raise HTTPException(status_code=400, detail="Заказ не находится в споре")

    now = datetime.now(timezone.utc)
    product_id = purchase["product_id"]
    quantity = purchase["quantity"]
    total_with_guarantor = purchase.get("total_with_guarantor", purchase["total_price"])
    seller_receives = purchase["seller_receives"]

    if resolution == "refund_buyer":
        await db.shop_products.update_one(
            {"id": product_id},
            {"$inc": {"reserved_count": -quantity}}
        )

        await db.traders.update_one(
            {"id": purchase["buyer_id"]},
            {"$inc": {"balance_escrow": -total_with_guarantor, "balance_usdt": total_with_guarantor}}
        )

        await db.marketplace_purchases.update_one(
            {"id": purchase_id},
            {"$set": {
                "status": "refunded",
                "resolved_at": now.isoformat(),
                "resolved_by": user["id"],
                "resolution": "refund_buyer",
                "admin_note": admin_note
            }}
        )

        message = f"Спор решён в пользу покупателя. Возвращено {total_with_guarantor:.2f} USDT"

    elif resolution == "release_to_seller":
        reserved_content = purchase.get("reserved_content", [])
        product = await db.shop_products.find_one({"id": product_id})
        if product:
            auto_content = product.get("auto_content", [])
            new_content = [c for c in auto_content if c not in reserved_content]
            await db.shop_products.update_one(
                {"id": product_id},
                {
                    "$set": {"auto_content": new_content},
                    "$inc": {"reserved_count": -quantity, "quantity": -quantity, "sold_count": quantity}
                }
            )

        await db.traders.update_one(
            {"id": purchase["buyer_id"]},
            {"$inc": {"balance_escrow": -total_with_guarantor}}
        )

        await db.traders.update_one(
            {"id": purchase["seller_id"]},
            {"$inc": {"shop_balance": seller_receives}}
        )

        await db.marketplace_purchases.update_one(
            {"id": purchase_id},
            {"$set": {
                "status": "completed",
                "delivered_content": reserved_content,
                "resolved_at": now.isoformat(),
                "resolved_by": user["id"],
                "resolution": "release_to_seller",
                "admin_note": admin_note,
                "completed_at": now.isoformat()
            }}
        )

        message = "Спор решён в пользу продавца. Товар выдан покупателю."

    else:
        raise HTTPException(status_code=400, detail="Неверное решение. Используйте 'refund_buyer' или 'release_to_seller'")

    for party_id in [purchase["buyer_id"], purchase["seller_id"]]:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": party_id,
            "type": "dispute_resolved",
            "title": "Спор разрешён",
            "message": message,
            "data": {"purchase_id": purchase_id, "resolution": resolution},
            "read": False,
            "created_at": now.isoformat()
        })

    return {
        "status": "success",
        "purchase_id": purchase_id,
        "resolution": resolution,
        "message": message
    }


@router.get("/my-purchases")
async def get_my_marketplace_purchases(user: dict = Depends(get_current_user)):
    """Get current user's marketplace purchases"""
    purchases = await db.marketplace_purchases.find(
        {"buyer_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    for purchase in purchases:
        seller = await db.traders.find_one({"id": purchase.get("seller_id")}, {"_id": 0, "nickname": 1, "display_name": 1})
        if not seller:
            seller = await db.merchants.find_one({"id": purchase.get("seller_id")}, {"_id": 0, "nickname": 1, "display_name": 1})
        if seller:
            purchase["seller_nickname"] = seller.get("display_name") or seller.get("nickname", "Unknown")
        
        # Add unread guarantor message count for this purchase
        if purchase.get("purchase_type") == "guarantor":
            conv = await db.unified_conversations.find_one(
                {"type": "marketplace_guarantor", "related_id": purchase.get("id")},
                {"_id": 0, "id": 1}
            )
            if conv:
                unread = await db.unified_messages.count_documents({
                    "conversation_id": conv["id"],
                    "sender_id": {"$ne": user["id"]},
                    "read_by": {"$not": {"$elemMatch": {"$eq": user["id"]}}}
                })
                purchase["unread_messages"] = unread
            else:
                purchase["unread_messages"] = 0
        else:
            purchase["unread_messages"] = 0

    return purchases



@router.post("/purchases/{purchase_id}/mark-viewed")
async def mark_purchase_viewed(purchase_id: str, user: dict = Depends(get_current_user)):
    """Mark a marketplace purchase as viewed (clears badge)"""
    purchase = await db.marketplace_purchases.find_one(
        {"id": purchase_id, "buyer_id": user["id"]}, {"_id": 0}
    )
    if not purchase:
        raise HTTPException(status_code=404, detail="Покупка не найдена")
    await db.marketplace_purchases.update_one(
        {"id": purchase_id},
        {"$set": {"viewed": True}}
    )
    return {"status": "ok"}


@router.get("/categories")
async def get_marketplace_categories():
    """Get all unique categories from products"""
    categories = await db.shop_products.distinct("category", {"is_active": True})
    return categories

@router.get("/purchases/{purchase_id}/guarantor-chat")
async def get_guarantor_chat_info(purchase_id: str, user: dict = Depends(get_current_user)):
    """Get guarantor purchase info including conversation_id for chat"""
    purchase = await db.marketplace_purchases.find_one(
        {"id": purchase_id, "purchase_type": "guarantor"}, {"_id": 0}
    )
    if not purchase:
        raise HTTPException(status_code=404, detail="Гарант-заказ не найден")
    
    user_id = user["id"]
    is_admin = user.get("admin_role") in ["owner", "admin", "mod_market"]
    
    if user_id != purchase.get("buyer_id") and user_id != purchase.get("seller_id") and not is_admin:
        raise HTTPException(status_code=403, detail="Нет доступа к этому заказу")
    
    # Find conversation
    conv = await db.unified_conversations.find_one(
        {"type": "marketplace_guarantor", "related_id": purchase_id}, {"_id": 0}
    )
    
    conversation_id = conv.get("id") if conv else None
    
    # Determine user role in this deal
    role = "admin"
    if user_id == purchase.get("buyer_id"):
        role = "buyer"
    elif user_id == purchase.get("seller_id"):
        role = "seller"
    
    return {
        "purchase": purchase,
        "conversation_id": conversation_id,
        "role": role,
        "conversation": conv
    }

