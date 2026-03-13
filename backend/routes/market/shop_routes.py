from fastapi import APIRouter, HTTPException, Depends, Body, File, UploadFile
from fastapi.responses import FileResponse
from datetime import datetime, timezone
from typing import Optional, List
import uuid
import os
from pathlib import Path

from core.database import db
from core.auth import get_current_user
from .models import ShopApplicationCreate, ShopSettings
from .utils import find_shop_user, SHOP_CATEGORY_LABELS, UPLOAD_DIR

router = APIRouter()

# ==================== SHOP APPLICATION ====================

@router.post("/shop/apply")
async def apply_for_shop(data: ShopApplicationCreate, user: dict = Depends(get_current_user)):
    """Submit application to open a shop"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только трейдеры и мерчанты могут подать заявку на магазин")

    # Check in both collections
    user_doc, _ = await find_shop_user(user["id"])
    if not user_doc:
        user_doc = await db.merchants.find_one({"id": user["id"]}, {"_id": 0})
    if user_doc and user_doc.get("has_shop"):
        raise HTTPException(status_code=400, detail="У вас уже есть магазин")

    existing = await db.shop_applications.find_one({
        "user_id": user["id"],
        "status": "pending"
    }, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="У вас уже есть заявка на рассмотрении")

    if len(data.shop_name) < 3 or len(data.shop_name) > 50:
        raise HTTPException(status_code=400, detail="Название магазина должно быть от 3 до 50 символов")
    if len(data.shop_description) < 20:
        raise HTTPException(status_code=400, detail="Описание должно быть не менее 20 символов")
    if not data.categories or len(data.categories) == 0:
        raise HTTPException(status_code=400, detail="Укажите хотя бы одну категорию")

    application_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_nickname": user.get("nickname", user.get("login", "")),
        "shop_name": data.shop_name,
        "shop_description": data.shop_description,
        "categories": data.categories,
        "telegram": data.telegram,
        "experience": data.experience,
        "status": "pending",
        "admin_comment": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_at": None,
        "reviewed_by": None
    }

    await db.shop_applications.insert_one(application_doc)

    # Create unified_conversation for shop application chat
    conv_id = str(uuid.uuid4())
    conv_doc = {
        "id": conv_id,
        "type": "shop_application",
        "status": "pending",
        "related_id": application_doc["id"],
        "participants": [
            {"user_id": user["id"], "role": "applicant", "name": user.get("nickname", user.get("login", ""))}
        ],
        "title": f"🏪 Заявка: {data.shop_name}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_conversations.insert_one(conv_doc)

    # Send welcome message
    welcome_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"🏪 Заявка на открытие магазина: {data.shop_name}\n\nКатегории: {', '.join([SHOP_CATEGORY_LABELS.get(c, c) for c in data.categories])}\nОписание: {data.shop_description}\nTelegram: {data.telegram}\n\nВаша заявка принята! Модератор маркетплейса рассмотрит её в ближайшее время.",
        "is_system": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(welcome_msg)

    application_doc.pop("_id", None)
    return application_doc


@router.get("/shop/my-application")
async def get_my_shop_application(user: dict = Depends(get_current_user)):
    """Get current user's shop application"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    user_doc, _ = await find_shop_user(user["id"])
    if not user_doc:
        user_doc = await db.merchants.find_one({"id": user["id"]}, {"_id": 0})
    if user_doc and user_doc.get("has_shop"):
        return {"has_shop": True, "shop_settings": user_doc.get("shop_settings", {}), "application": None}

    application = await db.shop_applications.find_one(
        {"user_id": user["id"]},
        {"_id": 0}
    )

    return {"has_shop": False, "application": application}

# ==================== SHOP MANAGEMENT ====================

@router.get("/shop/my-shop")
async def get_my_trader_shop(user: dict = Depends(get_current_user)):
    """Get current user's shop settings"""
    user_doc, _ = await find_shop_user(user["id"])
    
    if not user_doc or not user_doc.get("has_shop"):
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    return {
        "shop_settings": user_doc.get("shop_settings", {}),
        "shop_balance": user_doc.get("shop_balance", 0.0)
    }


@router.put("/shop/my-shop")
async def update_my_trader_shop(data: ShopSettings, user: dict = Depends(get_current_user)):
    """Update shop settings"""
    user_doc, collection = await find_shop_user(user["id"])
    
    if not user_doc or not user_doc.get("has_shop"):
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    current_settings = user_doc.get("shop_settings", {})
    
    # Update allowed fields
    current_settings["shop_name"] = data.shop_name
    current_settings["shop_description"] = data.shop_description
    current_settings["shop_logo"] = data.shop_logo
    current_settings["shop_banner"] = data.shop_banner
    current_settings["categories"] = data.categories
    current_settings["is_active"] = data.is_active
    
    await collection.update_one(
        {"id": user["id"]},
        {"$set": {"shop_settings": current_settings}}
    )
    
    return {"status": "updated", "shop_settings": current_settings}


@router.put("/shop/settings")
async def update_shop_settings(data: ShopSettings, user: dict = Depends(get_current_user)):
    """Update shop settings (alias for my-shop)"""
    return await update_my_trader_shop(data, user)


@router.post("/shop/upload")
async def upload_shop_file(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload shop logo or banner"""
    user_doc, _ = await find_shop_user(user["id"])
    
    if not user_doc or not user_doc.get("has_shop"):
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Только изображения")
        
    # Generate filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"shop_{user['id']}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Save file
    with open(file_path, "wb") as buffer:
        import shutil
        shutil.copyfileobj(file.file, buffer)
        
    return {"url": f"/api/shop/uploads/{filename}"}


@router.get("/shop/uploads/{filename}")
async def get_uploaded_file(filename: str):
    """Serve uploaded shop file"""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(file_path)

# ==================== SHOP DASHBOARD ====================

@router.get("/shop/dashboard")
async def get_shop_dashboard(user: dict = Depends(get_current_user)):
    """Get shop dashboard stats"""
    user_doc, _ = await find_shop_user(user["id"])
    
    if not user_doc or not user_doc.get("has_shop"):
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    shop_stats = user_doc.get("shop_stats", {
        "total_sales": 0.0,
        "total_orders": 0,
        "total_commission_paid": 0.0
    })
    
    # Calculate active products
    active_products = await db.shop_products.count_documents({
        "seller_id": user["id"],
        "is_active": True
    })
    
    # Calculate pending orders
    pending_orders = await db.marketplace_purchases.count_documents({
        "seller_id": user["id"],
        "status": "pending_confirmation"
    })
    
    # Recent orders
    recent_orders = await db.marketplace_purchases.find(
        {"seller_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    # Calculate total stock value
    products = await db.shop_products.find(
        {"seller_id": user["id"]},
        {"price": 1, "auto_content": 1, "reserved_count": 1}
    ).to_list(1000)
    
    total_stock_value = 0
    for p in products:
        stock = len(p.get("auto_content", [])) - p.get("reserved_count", 0)
        if stock > 0:
            total_stock_value += stock * p.get("price", 0)
            
    return {
        "shop_balance": user_doc.get("shop_balance", 0.0),
        "stats": shop_stats,
        "active_products": active_products,
        "pending_orders": pending_orders,
        "total_stock_value": total_stock_value,
        "recent_orders": recent_orders,
        "commission_rate": user_doc.get("shop_settings", {}).get("commission_rate", 5.0)
    }


@router.get("/shop/orders")
async def get_shop_orders(
    status: Optional[str] = None, 
    page: int = 1, 
    limit: int = 20,
    user: dict = Depends(get_current_user)
):
    """Get shop orders history"""
    user_doc, _ = await find_shop_user(user["id"])
    
    if not user_doc or not user_doc.get("has_shop"):
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    query = {"seller_id": user["id"]}
    if status:
        query["status"] = status
        
    total = await db.marketplace_purchases.count_documents(query)
    orders = await db.marketplace_purchases.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).skip((page - 1) * limit).limit(limit).to_list(limit)
    
    return {
        "orders": orders,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }


@router.get("/shop/finances")
async def get_shop_finances(
    page: int = 1, 
    limit: int = 20,
    user: dict = Depends(get_current_user)
):
    """Get shop financial history (sales, transfers)"""
    user_doc, _ = await find_shop_user(user["id"])
    
    if not user_doc or not user_doc.get("has_shop"):
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    # Get sales (from purchases)
    sales_query = {"seller_id": user["id"], "status": "completed"}
    
    # Get transfers/withdrawals (from transactions or commission_payments)
    # For now, we'll just return sales history as finances
    
    total = await db.marketplace_purchases.count_documents(sales_query)
    transactions = await db.marketplace_purchases.find(
        sales_query,
        {"_id": 0}
    ).sort("completed_at", -1).skip((page - 1) * limit).limit(limit).to_list(limit)
    
    # Format as transactions
    formatted_txs = []
    for tx in transactions:
        formatted_txs.append({
            "id": tx["id"],
            "type": "sale",
            "amount": tx["seller_receives"],
            "description": f"Продажа: {tx['product_name']} ({tx['quantity']} шт.)",
            "created_at": tx["completed_at"],
            "status": "completed"
        })
        
    return {
        "transactions": formatted_txs,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
        "shop_balance": user_doc.get("shop_balance", 0.0)
    }


@router.post("/shop/transfer-balance")
async def transfer_shop_balance(
    amount: float = Body(..., embed=True),
    user: dict = Depends(get_current_user)
):
    """Transfer funds from shop balance to main balance"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")
        
    user_doc, collection = await find_shop_user(user["id"])
    
    if not user_doc or not user_doc.get("has_shop"):
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    shop_balance = user_doc.get("shop_balance", 0.0)
    
    if shop_balance < amount:
        raise HTTPException(status_code=400, detail="Недостаточно средств на балансе магазина")
        
    # Atomic transfer
    await collection.update_one(
        {"id": user["id"]},
        {"$inc": {
            "shop_balance": -amount,
            "balance_usdt": amount
        }}
    )
    
    # Log transaction
    await db.transactions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "type": "shop_transfer",
        "amount": amount,
        "currency": "USDT",
        "description": "Перевод с баланса магазина на основной счет",
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"status": "success", "message": f"Переведено {amount:.2f} USDT на основной баланс"}


@router.post("/shop/withdraw")
async def request_shop_withdrawal(
    amount: float = Body(..., embed=True),
    user: dict = Depends(get_current_user)
):
    """Request withdrawal from shop balance (legacy, now uses transfer-balance)"""
    # Redirect to transfer-balance logic for now, or implement external withdrawal
    # For now, we'll just transfer to main balance as per recent changes
    return await transfer_shop_balance(amount, user)


@router.get("/shop/sales")
async def get_shop_sales(user: dict = Depends(get_current_user)):
    """Get shop sales statistics"""
    user_doc, _ = await find_shop_user(user["id"])
    
    if not user_doc or not user_doc.get("has_shop"):
        raise HTTPException(status_code=404, detail="Магазин не найден")
        
    return user_doc.get("shop_stats", {
        "total_sales": 0.0,
        "total_orders": 0,
        "total_commission_paid": 0.0
    })
