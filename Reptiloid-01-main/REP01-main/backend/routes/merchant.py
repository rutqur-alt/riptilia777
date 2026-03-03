"""
Merchant routes - Merchant shop and product management
Routes for merchant-specific shop operations
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List
import uuid

from core.database import db
from core.auth import get_current_user
from models.schemas import ProductCreate, ProductUpdate


# Import ShopSettings from shop routes
from pydantic import BaseModel
from typing import Optional


class ShopSettings(BaseModel):
    shop_name: str
    shop_description: Optional[str] = None
    shop_logo: Optional[str] = None
    shop_banner: Optional[str] = None
    categories: List[str] = []
    is_active: bool = True
    commission_rate: Optional[float] = None


router = APIRouter(prefix="/merchant", tags=["merchant"])


@router.get("/shop")
async def get_my_shop(user: dict = Depends(get_current_user)):
    """Get merchant's shop settings"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    merchant = await db.merchants.find_one({"id": user["id"]}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")

    return merchant.get("shop_settings", {
        "shop_name": merchant.get("merchant_name", ""),
        "shop_description": "",
        "shop_logo": None,
        "shop_banner": None,
        "categories": [],
        "is_active": True
    })


@router.put("/shop")
async def update_my_shop(data: ShopSettings, user: dict = Depends(get_current_user)):
    """Update merchant's shop settings"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    await db.merchants.update_one(
        {"id": user["id"]},
        {"$set": {"shop_settings": data.model_dump()}}
    )

    return {"status": "updated"}


@router.get("/products")
async def get_my_products(user: dict = Depends(get_current_user)):
    """Get merchant's products"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    products = await db.products.find({"merchant_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)

    for product in products:
        product["stock_count"] = len(product.get("auto_content", []))
        del product["auto_content"]

    return products


@router.post("/products")
async def create_product(data: ProductCreate, user: dict = Depends(get_current_user)):
    """Create a new product"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    product_doc = {
        "id": str(uuid.uuid4()),
        "merchant_id": user["id"],
        "name": data.name,
        "description": data.description,
        "price": data.price,
        "currency": data.currency,
        "category": data.category,
        "image_url": data.image_url,
        "quantity": data.quantity,
        "auto_content": data.auto_content,
        "is_active": data.is_active,
        "sold_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await db.products.insert_one(product_doc)

    response = {**product_doc}
    response["stock_count"] = len(response.get("auto_content", []))
    del response["auto_content"]

    return response


@router.put("/products/{product_id}")
async def update_product(product_id: str, data: ProductUpdate, user: dict = Depends(get_current_user)):
    """Update a product"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    product = await db.products.find_one({"id": product_id, "merchant_id": user["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    if update_data:
        await db.products.update_one({"id": product_id}, {"$set": update_data})

    return {"status": "updated"}


@router.post("/products/{product_id}/stock")
async def add_product_stock(product_id: str, content: List[str], user: dict = Depends(get_current_user)):
    """Add stock (auto-delivery content) to product"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    product = await db.products.find_one({"id": product_id, "merchant_id": user["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    await db.products.update_one(
        {"id": product_id},
        {
            "$push": {"auto_content": {"$each": content}},
            "$inc": {"quantity": len(content)}
        }
    )

    return {"status": "added", "added_count": len(content)}


@router.delete("/products/{product_id}")
async def delete_product(product_id: str, user: dict = Depends(get_current_user)):
    """Delete a product"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    result = await db.products.delete_one({"id": product_id, "merchant_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Товар не найден")

    return {"status": "deleted"}


@router.get("/purchases")
async def get_merchant_purchases(user: dict = Depends(get_current_user)):
    """Get merchant's sales history"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    purchases = await db.marketplace_purchases.find(
        {"seller_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    return purchases
