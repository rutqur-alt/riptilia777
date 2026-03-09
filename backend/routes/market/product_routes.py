from fastapi import APIRouter, HTTPException, Depends, Body, File, UploadFile
from fastapi.responses import FileResponse
from datetime import datetime, timezone
from typing import Optional, List
import uuid
import os
import json

from core.database import db
from core.auth import get_current_user
from .models import ProductCreate, ProductUpdate
from .utils import find_shop_user, UPLOAD_DIR

router = APIRouter()

# ==================== PRODUCTS ====================

@router.get("/shop/products")
async def get_my_shop_products(user: dict = Depends(get_current_user)):
    """Get current user's shop products"""
    user_doc, _ = await find_shop_user(user["id"])
    
    if not user_doc or not user_doc.get("has_shop"):
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    products = await db.shop_products.find(
        {"seller_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Add stock count info
    for p in products:
        p["stock_count"] = len(p.get("auto_content", []))
        p["reserved_count"] = p.get("reserved_count", 0)
        
    return products


@router.post("/shop/products")
async def create_shop_product(data: ProductCreate, user: dict = Depends(get_current_user)):
    """Create a new product"""
    user_doc, _ = await find_shop_user(user["id"])
    
    if not user_doc or not user_doc.get("has_shop"):
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    if user_doc.get("shop_settings", {}).get("is_blocked"):
        raise HTTPException(status_code=403, detail="Магазин заблокирован")
        
    product_id = str(uuid.uuid4())
    
    # Process auto_content if provided as list of strings
    auto_content = data.auto_content
    
    product_doc = {
        "id": product_id,
        "seller_id": user["id"],
        "name": data.name,
        "description": data.description,
        "price": data.price,
        "currency": data.currency,
        "category": data.category,
        "image_url": data.image_url,
        "auto_content": auto_content,
        "quantity": len(auto_content) if auto_content else data.quantity,
        "is_active": data.is_active,
        "is_infinite": data.is_infinite,
        "price_variants": [v.model_dump() for v in data.price_variants],
        "attached_files": data.attached_files,
        "sold_count": 0,
        "reserved_count": 0,
        "views_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.shop_products.insert_one(product_doc)
    product_doc.pop("_id", None)
    
    return product_doc


@router.put("/shop/products/{product_id}")
async def update_shop_product(
    product_id: str, 
    data: ProductUpdate, 
    user: dict = Depends(get_current_user)
):
    """Update a product"""
    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    if "price_variants" in update_data:
        update_data["price_variants"] = [v.model_dump() if hasattr(v, "model_dump") else v for v in update_data["price_variants"]]
    
    await db.shop_products.update_one(
        {"id": product_id},
        {"$set": update_data}
    )
    
    return {"status": "updated"}


@router.delete("/shop/products/{product_id}")
async def delete_shop_product(product_id: str, user: dict = Depends(get_current_user)):
    """Delete a product"""
    result = await db.shop_products.delete_one({"id": product_id, "seller_id": user["id"]})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    return {"status": "deleted"}


# ==================== STOCK MANAGEMENT ====================

@router.post("/shop/products/{product_id}/stock")
async def add_shop_product_stock(
    product_id: str, 
    content: str = Body(..., embed=True),
    user: dict = Depends(get_current_user)
):
    """Add single item to stock"""
    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    await db.shop_products.update_one(
        {"id": product_id},
        {
            "$push": {"auto_content": content},
            "$inc": {"quantity": 1}
        }
    )
    
    return {"status": "added"}


@router.post("/shop/products/{product_id}/stock/bulk")
async def add_shop_product_stock_bulk(
    product_id: str, 
    content: str = Body(..., embed=True),
    user: dict = Depends(get_current_user)
):
    """Add multiple items to stock (newline separated)"""
    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    items = [item.strip() for item in content.split("\n") if item.strip()]
    
    if not items:
        raise HTTPException(status_code=400, detail="Нет данных для добавления")
        
    await db.shop_products.update_one(
        {"id": product_id},
        {
            "$push": {"auto_content": {"$each": items}},
            "$inc": {"quantity": len(items)}
        }
    )
    
    return {"status": "added", "count": len(items)}


@router.post("/shop/products/{product_id}/stock/upload")
async def upload_shop_product_stock(
    product_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """Upload stock from file"""
    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
        items = [item.strip() for item in text_content.split("\n") if item.strip()]
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Файл должен быть текстовым (UTF-8)")
        
    if not items:
        raise HTTPException(status_code=400, detail="Файл пуст")
        
    await db.shop_products.update_one(
        {"id": product_id},
        {
            "$push": {"auto_content": {"$each": items}},
            "$inc": {"quantity": len(items)}
        }
    )
    
    return {"status": "added", "count": len(items)}


@router.get("/shop/products/{product_id}/stock/download")
async def download_shop_product_stock(
    product_id: str,
    user: dict = Depends(get_current_user)
):
    """Download current stock as file"""
    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    stock = product.get("auto_content", [])
    content = "\n".join(stock)
    
    # Save to temp file
    filename = f"stock_{product_id}.txt"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return FileResponse(file_path, filename=f"stock_{product['name']}.txt")


@router.get("/shop/products/{product_id}/stock")
async def get_shop_product_stock(
    product_id: str,
    user: dict = Depends(get_current_user)
):
    """Get product stock items"""
    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    return {
        "stock": product.get("auto_content", []),
        "reserved_count": product.get("reserved_count", 0)
    }


@router.delete("/shop/products/{product_id}/stock/{index}")
async def delete_shop_product_stock_item(
    product_id: str,
    index: int,
    user: dict = Depends(get_current_user)
):
    """Delete specific stock item by index"""
    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    stock = product.get("auto_content", [])
    if index < 0 or index >= len(stock):
        raise HTTPException(status_code=400, detail="Неверный индекс")
        
    # Remove item at index
    stock.pop(index)
    
    await db.shop_products.update_one(
        {"id": product_id},
        {"$set": {"auto_content": stock, "quantity": len(stock)}}
    )
    
    return {"status": "deleted"}


@router.put("/shop/products/{product_id}/stock/{index}")
async def update_shop_product_stock_item(
    product_id: str,
    index: int,
    content: str = Body(..., embed=True),
    user: dict = Depends(get_current_user)
):
    """Update specific stock item by index"""
    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    stock = product.get("auto_content", [])
    if index < 0 or index >= len(stock):
        raise HTTPException(status_code=400, detail="Неверный индекс")
        
    stock[index] = content
    
    await db.shop_products.update_one(
        {"id": product_id},
        {"$set": {"auto_content": stock}}
    )
    
    return {"status": "updated"}
