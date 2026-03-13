from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from core.database import db
from .utils import SHOP_CATEGORIES, SHOP_CATEGORY_LABELS

router = APIRouter()

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

@router.get("/categories")
async def get_marketplace_categories():
    """Get list of available shop categories"""
    return {
        "categories": SHOP_CATEGORIES,
        "labels": SHOP_CATEGORY_LABELS
    }
