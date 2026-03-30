"""
Shop routes - Trader shop management
Routes for shop applications, products, stock management, and shop dashboard
"""
from fastapi import APIRouter, HTTPException, Depends, Body, File, UploadFile
from fastapi.responses import FileResponse
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_validator
import uuid
import os
from pathlib import Path

from core.database import db
from core.auth import require_role, get_current_user
from models.schemas import ProductUpdate

router = APIRouter(tags=["shop"])

# Upload directory - resolve relative to this file
UPLOAD_DIR = str(Path(__file__).parent.parent / "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Shop categories - predefined list
SHOP_CATEGORIES = [
    "accounts",      # Аккаунты
    "software",      # Софт
    "databases",     # Базы данных
    "tools",         # Инструменты
    "guides",        # Гайды и схемы
    "keys",          # Ключи
    "financial",     # Финансовое
    "templates",     # Шаблоны
    "other"          # Другое
]

SHOP_CATEGORY_LABELS = {
    "accounts": "Аккаунты",
    "software": "Софт",
    "databases": "Базы данных",
    "tools": "Инструменты",
    "guides": "Гайды и схемы",
    "keys": "Ключи",
    "financial": "Финансовое",
    "templates": "Шаблоны",
    "other": "Другое"
}



# Helper function to find user in both traders and merchants collections
async def find_shop_user(user_id):
    """Find a user by ID in traders or merchants collection. Returns (user_doc, collection) or (None, None)."""
    trader = await db.traders.find_one({"id": user_id}, {"_id": 0})
    if trader:
        return trader, db.traders
    merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0})
    if merchant:
        return merchant, db.merchants
    return None, None

# ==================== PYDANTIC MODELS ====================

class ShopApplicationCreate(BaseModel):
    shop_name: str
    shop_description: str
    categories: List[str]
    telegram: str
    experience: Optional[str] = None

    @field_validator('categories')
    @classmethod
    def validate_categories(cls, v):
        for cat in v:
            if cat not in SHOP_CATEGORIES:
                raise ValueError(f'Недопустимая категория: {cat}. Допустимые: {", ".join(SHOP_CATEGORIES)}')
        return v


class ShopApplicationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    user_nickname: str
    shop_name: str
    shop_description: str
    categories: List[str]
    telegram: str
    experience: Optional[str] = None
    status: str
    admin_comment: Optional[str] = None
    created_at: str
    reviewed_at: Optional[str] = None


class PriceVariant(BaseModel):
    quantity: int
    price: float
    label: Optional[str] = None


class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    currency: str = "USDT"
    category: str
    image_url: Optional[str] = None
    quantity: int = 0
    auto_content: List[str] = []
    is_active: bool = True
    is_infinite: bool = False
    price_variants: List[PriceVariant] = []
    attached_files: List[str] = []


class ShopSettings(BaseModel):
    shop_name: str
    shop_description: Optional[str] = None
    shop_logo: Optional[str] = None
    shop_banner: Optional[str] = None
    categories: List[str] = []
    is_active: bool = True
    commission_rate: Optional[float] = None


# ==================== SHOP CATEGORIES ====================

@router.get("/shop/categories")
async def get_shop_categories():
    """Get list of available shop categories"""
    return {
        "categories": SHOP_CATEGORIES,
        "labels": SHOP_CATEGORY_LABELS
    }


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


# ==================== ADMIN: SHOP APPLICATIONS ====================

@router.get("/admin/shop-applications")
async def get_shop_applications(
    status: Optional[str] = None,
    user: dict = Depends(require_role(["admin", "mod_market"]))
):
    """Get all shop applications (admin or marketplace moderator)"""
    query = {}
    if status:
        query["status"] = status

    applications = await db.shop_applications.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)

    for app in applications:
        trader = await db.traders.find_one({"id": app["user_id"]}, {"_id": 0, "pending_shop_commission": 1, "shop_commission_set_by": 1})
        if trader:
            app["pending_commission"] = trader.get("pending_shop_commission", 5.0)
            app["commission_set_by"] = trader.get("shop_commission_set_by")

    return applications


@router.post("/admin/shop-applications/commission/{user_id}")
async def set_shop_pending_commission(user_id: str, data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_market"]))):
    """Set pending commission for shop (before approval)"""
    commission = data.get("commission", 5.0)
    admin_role = user.get("admin_role", "admin")

    trader = await db.traders.find_one({"id": user_id}, {"_id": 0, "shop_commission_set_by": 1, "id": 1})
    if not trader:
        raise HTTPException(status_code=404, detail="User not found")

    if trader.get("shop_commission_set_by") and admin_role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Только админ может изменить комиссию")

    await db.traders.update_one(
        {"id": user_id},
        {"$set": {
            "pending_shop_commission": commission,
            "shop_commission_set_by": user["id"],
            "shop_commission_set_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    return {"status": "saved", "commission": commission}


@router.post("/admin/shop-applications/{application_id}/review")
async def review_shop_application(
    application_id: str,
    decision: str,
    comment: Optional[str] = None,
    user: dict = Depends(require_role(["admin", "mod_market"]))
):
    """Approve or reject shop application"""
    if decision not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="decision должен быть 'approve' или 'reject'")

    application = await db.shop_applications.find_one({"id": application_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    if application["status"] != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже рассмотрена")

    new_status = "approved" if decision == "approve" else "rejected"

    await db.shop_applications.update_one(
        {"id": application_id},
        {"$set": {
            "status": new_status,
            "admin_comment": comment,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": user["id"]
        }}
    )

    if decision == "approve":
        trader, target_collection = await find_shop_user(application["user_id"])
        if not trader:
            trader = await db.merchants.find_one({"id": application["user_id"]}, {"_id": 0, "pending_shop_commission": 1})
            target_collection = db.merchants
        commission_rate = trader.get("pending_shop_commission", 5.0) if trader else 5.0

        shop_desc = application.get("shop_description") or application.get("description", "")
        shop_cats = application.get("categories", [])

        await target_collection.update_one(
            {"id": application["user_id"]},
            {"$set": {
                "has_shop": True,
                "shop_settings": {
                    "shop_name": application["shop_name"],
                    "shop_description": shop_desc,
                    "categories": shop_cats,
                    "shop_logo": None,
                    "shop_banner": None,
                    "is_active": True,
                    "commission_rate": commission_rate
                },
                "shop_balance": 0.0
            }}
        )

        await db.admin_logs.insert_one({
            "id": str(uuid.uuid4()),
            "admin_id": user["id"],
            "admin_login": user.get("nickname", user.get("login", "")),
            "action": "shop_application_approved",
            "target_id": application["user_id"],
            "details": f"Магазин '{application['shop_name']}' одобрен",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    else:
        await db.admin_logs.insert_one({
            "id": str(uuid.uuid4()),
            "admin_id": user["id"],
            "admin_login": user.get("nickname", user.get("login", "")),
            "action": "shop_application_rejected",
            "target_id": application["user_id"],
            "details": f"Заявка на магазин '{application['shop_name']}' отклонена: {comment or 'без комментария'}",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    # Auto-archive the unified conversation
    await db.unified_conversations.update_many(
        {"type": "shop_application", "related_id": application_id},
        {"$set": {
            "status": new_status,
            "resolved": True,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolved_by": user["id"],
            "archived": True
        }}
    )

    return {"status": new_status}


@router.put("/admin/shops/{shop_id}/commission")
async def update_shop_commission(
    shop_id: str,
    commission_rate: float,
    user: dict = Depends(get_current_user)
):
    """Update commission rate for a trader shop"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для админов")

    if commission_rate < 0 or commission_rate > 100:
        raise HTTPException(status_code=400, detail="Комиссия должна быть от 0 до 100%")

    trader = await db.traders.find_one({"id": shop_id, "has_shop": True}, {"_id": 0})
    if not trader:
        trader = await db.merchants.find_one({"id": shop_id, "has_shop": True}, {"_id": 0})
    if trader:
        await db.traders.update_one(
            {"id": shop_id},
            {"$set": {"shop_settings.commission_rate": commission_rate}}
        )
        await db.admin_logs.insert_one({
            "id": str(uuid.uuid4()),
            "admin_id": user["id"],
            "admin_login": user.get("nickname", user.get("login", "")),
            "action": "shop_commission_changed",
            "target_id": shop_id,
            "details": f"Комиссия магазина {trader.get('shop_settings', {}).get('shop_name', '')} изменена на {commission_rate}%",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        return {"status": "updated", "commission_rate": commission_rate}

    raise HTTPException(status_code=404, detail="Магазин не найден")


@router.get("/admin/products")
async def get_all_products_admin(user: dict = Depends(get_current_user)):
    """Get all products for admin panel"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для админов")

    products = await db.shop_products.find({}, {"_id": 0, "auto_content": 0}).sort("created_at", -1).to_list(200)
    
    for product in products:
        seller = await db.traders.find_one({"id": product.get("seller_id")}, {"_id": 0, "nickname": 1, "shop_settings": 1})
        if not seller:
            seller = await db.merchants.find_one({"id": product.get("seller_id")}, {"_id": 0, "nickname": 1, "shop_settings": 1})
        if seller:
            product["shop_name"] = seller.get("shop_settings", {}).get("shop_name", seller.get("nickname", ""))
        product["title"] = product.get("name", "")
    
    return products


@router.post("/admin/products/{product_id}/toggle")
async def toggle_product_admin(product_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Toggle product active status"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для админов")
    
    await db.shop_products.update_one(
        {"id": product_id},
        {"$set": {"is_active": data.get("is_active", False)}}
    )
    return {"status": "updated"}


@router.delete("/admin/products/{product_id}")
async def delete_product_admin(product_id: str, user: dict = Depends(get_current_user)):
    """Delete a product (admin)"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для админов")
    
    await db.shop_products.delete_one({"id": product_id})
    return {"status": "deleted"}


@router.get("/admin/inventory-monitoring")
async def get_inventory_monitoring(user: dict = Depends(get_current_user)):
    """Get inventory monitoring data"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для админов")

    result = []
    products = await db.shop_products.find({}, {"_id": 0}).to_list(200)

    for product in products:
        sales = await db.marketplace_purchases.count_documents({
            "product_id": product["id"],
            "status": "completed"
        })

        stock = len(product.get("auto_content", []))
        reserved = product.get("reserved_count", 0)
        sold = product.get("sold_count", 0)
        has_discrepancy = sold != sales

        result.append({
            "id": product["id"],
            "name": product["name"],
            "seller_nickname": product.get("seller_nickname", ""),
            "stock": stock,
            "reserved": reserved,
            "available": stock - reserved,
            "sold_count": sold,
            "actual_sales": sales,
            "has_discrepancy": has_discrepancy
        })

    result.sort(key=lambda x: (not x["has_discrepancy"], x["name"]))
    return result


@router.post("/admin/transfer")
async def admin_transfer(
    target_user_id: str,
    amount: float,
    reason: str,
    user: dict = Depends(get_current_user)
):
    """Admin manual transfer to user's trading balance"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для админов")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")

    target, _ = await find_shop_user(target_user_id)
    if not target:
        # Also check users collection
        target = await db.users.find_one({"id": target_user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    await db.traders.update_one(
        {"id": target_user_id},
        {"$inc": {"balance_usdt": amount}}
    )

    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": user["id"],
        "admin_login": user.get("nickname", user.get("login", "")),
        "action": "manual_transfer",
        "target_id": target_user_id,
        "details": f"Перевод {amount} USDT для {target.get('nickname', target.get('login', ''))}. Причина: {reason}",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"status": "transferred", "amount": amount}


# ==================== SHOP DASHBOARD ====================

@router.get("/shop/dashboard")
async def get_shop_dashboard(user: dict = Depends(get_current_user)):
    """Get shop dashboard with stats"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    trader, user_col = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    shop_settings = trader.get("shop_settings", {})

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)

    today_sales = await db.marketplace_purchases.find({
        "seller_id": user["id"],
        "status": "completed",
        "created_at": {"$gte": today_start.isoformat()}
    }, {"_id": 0}).to_list(1000)

    week_sales = await db.marketplace_purchases.find({
        "seller_id": user["id"],
        "status": "completed",
        "created_at": {"$gte": week_start.isoformat()}
    }, {"_id": 0}).to_list(1000)

    month_sales = await db.marketplace_purchases.find({
        "seller_id": user["id"],
        "status": "completed",
        "created_at": {"$gte": month_start.isoformat()}
    }, {"_id": 0}).to_list(1000)

    product_count = await db.shop_products.count_documents({"seller_id": user["id"]})
    products = await db.shop_products.find({"seller_id": user["id"]}, {"_id": 0, "auto_content": 1}).to_list(100)
    total_stock = sum(len(p.get("auto_content", [])) for p in products)

    return {
        "shop": {
            "name": shop_settings.get("shop_name", ""),
            "commission_rate": shop_settings.get("commission_rate", 5.0),
            "shop_balance": trader.get("shop_balance", 0.0),
            "is_active": shop_settings.get("is_active", True)
        },
        "stats": {
            "today": {
                "orders": len(today_sales),
                "revenue": sum(s.get("seller_receives", 0) for s in today_sales),
                "commission": sum(s.get("commission", 0) for s in today_sales)
            },
            "week": {
                "orders": len(week_sales),
                "revenue": sum(s.get("seller_receives", 0) for s in week_sales),
                "commission": sum(s.get("commission", 0) for s in week_sales)
            },
            "month": {
                "orders": len(month_sales),
                "revenue": sum(s.get("seller_receives", 0) for s in month_sales),
                "commission": sum(s.get("commission", 0) for s in month_sales)
            }
        },
        "inventory": {
            "product_count": product_count,
            "total_stock": total_stock
        }
    }


@router.get("/shop/orders")
async def get_shop_orders(
    status: Optional[str] = None,
    purchase_type: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get shop orders/purchases"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    trader, _ = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    query = {"seller_id": user["id"]}
    if status:
        query["status"] = status
    if purchase_type:
        query["purchase_type"] = purchase_type

    orders = await db.marketplace_purchases.find(query, {"_id": 0, "delivered_content": 0}).sort("created_at", -1).to_list(100)
    return orders


@router.get("/shop/finances")
async def get_shop_finances(user: dict = Depends(get_current_user)):
    """Get shop financial history"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    trader, _ = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    sales = await db.marketplace_purchases.find(
        {"seller_id": user["id"], "status": "completed"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    withdrawals = await db.shop_withdrawals.find(
        {"seller_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    transfers = await db.shop_transfers.find(
        {"$or": [{"from_id": user["id"]}, {"to_id": user["id"]}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    return {
        "balance": trader.get("shop_balance", 0.0),
        "reserved": trader.get("shop_balance_reserved", 0.0),
        "commission_rate": trader.get("shop_settings", {}).get("commission_rate", 5.0),
        "sales": sales,
        "withdrawals": withdrawals,
        "transfers": transfers
    }


@router.post("/shop/transfer")
async def transfer_shop_balance(
    target_nickname: str,
    amount: float,
    user: dict = Depends(get_current_user)
):
    """Transfer funds from shop balance to another user"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")

    trader, _ = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    if trader.get("shop_balance", 0) < amount:
        raise HTTPException(status_code=400, detail=f"Недостаточно средств. Баланс: {trader.get('shop_balance', 0)} USDT")

    target_user = await db.traders.find_one({"nickname": target_nickname}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Пользователь @{target_nickname} не найден")

    if target_user["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Нельзя перевести самому себе")

    # ATOMIC: Check and deduct shop_balance to prevent race conditions
    deduct_result = await db.traders.update_one(
        {"id": user["id"], "shop_balance": {"$gte": amount}},
        {"$inc": {"shop_balance": -amount}}
    )
    if deduct_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Недостаточно средств (параллельный запрос)")

    await db.traders.update_one(
        {"id": target_user["id"]},
        {"$inc": {"balance_usdt": amount}}
    )

    transfer_doc = {
        "id": str(uuid.uuid4()),
        "from_id": user["id"],
        "from_nickname": user.get("nickname", ""),
        "to_id": target_user["id"],
        "to_nickname": target_nickname,
        "amount": amount,
        "type": "shop_transfer",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.shop_transfers.insert_one(transfer_doc)

    return {"status": "transferred", "amount": amount, "to": target_nickname}


@router.post("/shop/withdraw")
async def request_shop_withdrawal(
    amount: float,
    method: str,
    details: str,
    user: dict = Depends(get_current_user)
):
    """Request withdrawal from shop balance"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    trader, user_col = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")

    if trader.get("shop_balance", 0) < amount:
        raise HTTPException(status_code=400, detail=f"Недостаточно средств. Баланс: {trader.get('shop_balance', 0)} USDT")

    # ATOMIC: Transfer to account balance with balance check to prevent race conditions
    withdraw_result = await user_col.update_one(
        {"id": user["id"], "shop_balance": {"$gte": amount}},
        {"$inc": {"shop_balance": -amount, "balance_usdt": amount}}
    )
    if withdraw_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Недостаточно средств (параллельный запрос)")

    withdrawal_doc = {
        "id": str(uuid.uuid4()),
        "seller_id": user["id"],
        "seller_nickname": user.get("nickname", ""),
        "amount": amount,
        "method": "to_balance",
        "details": "Вывод на баланс аккаунта",
        "status": "approved",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_at": datetime.now(timezone.utc).isoformat()
    }
    await db.shop_withdrawals.insert_one(withdrawal_doc)

    return {"status": "approved", "message": f"{amount} USDT переведено на баланс аккаунта"}


# ==================== SHOP SETTINGS ====================

@router.get("/shop/my-shop")
async def get_my_trader_shop(user: dict = Depends(get_current_user)):
    """Get trader's shop settings"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    trader, _ = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    return trader.get("shop_settings", {})


@router.put("/shop/my-shop")
async def update_my_trader_shop(data: ShopSettings, user: dict = Depends(get_current_user)):
    """Update trader's shop settings"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    trader, _ = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    await db.traders.update_one(
        {"id": user["id"]},
        {"$set": {"shop_settings": data.model_dump()}}
    )

    return {"status": "updated"}


@router.put("/shop/settings")
async def update_shop_settings(
    shop_logo: Optional[str] = None,
    shop_banner: Optional[str] = None,
    shop_description: Optional[str] = None,
    allow_direct_purchase: Optional[bool] = None,
    user: dict = Depends(get_current_user)
):
    """Update shop settings"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    trader, user_col = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    update_data = {}
    if shop_logo is not None:
        update_data["shop_settings.shop_logo"] = shop_logo
    if shop_banner is not None:
        update_data["shop_settings.shop_banner"] = shop_banner
    if shop_description is not None:
        update_data["shop_settings.shop_description"] = shop_description
    if allow_direct_purchase is not None:
        update_data["shop_settings.allow_direct_purchase"] = allow_direct_purchase

    if update_data:
        await user_col.update_one({"id": user["id"]}, {"$set": update_data})

    return {"status": "updated"}


# ==================== SHOP FILE UPLOAD ====================

@router.post("/shop/upload")
async def upload_shop_file(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload image or document for shop/product"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf", "text/plain"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Недопустимый тип файла. Разрешены: JPG, PNG, GIF, WebP, PDF, TXT")

    is_image = file.content_type.startswith("image/")
    max_size = 2 * 1024 * 1024 if is_image else 1 * 1024 * 1024

    content = await file.read()
    if len(content) > max_size:
        limit_text = "2MB" if is_image else "1MB"
        raise HTTPException(status_code=400, detail=f"Файл слишком большой. Максимум {limit_text}")

    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = f"{UPLOAD_DIR}/{filename}"

    if is_image and len(content) > 500 * 1024:
        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(content))

            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
                ext = 'jpg'
                filename = f"{uuid.uuid4()}.{ext}"
                filepath = f"{UPLOAD_DIR}/{filename}"

            max_dimension = 1920
            if max(img.size) > max_dimension:
                ratio = max_dimension / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            output = io.BytesIO()
            img.save(output, format='JPEG', quality=80, optimize=True)
            content = output.getvalue()
        except Exception as e:
            print(f"Image compression failed: {e}")

    with open(filepath, "wb") as f:
        f.write(content)

    file_url = f"/api/uploads/{filename}"
    return {"url": file_url, "filename": filename, "size": len(content)}


@router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str):
    """Serve uploaded file"""
    filepath = f"{UPLOAD_DIR}/{filename}"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Файл не найден")

    ext = filename.split(".")[-1].lower()
    content_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "pdf": "application/pdf",
        "txt": "text/plain"
    }
    content_type = content_types.get(ext, "application/octet-stream")

    return FileResponse(filepath, media_type=content_type)


# ==================== SHOP PRODUCTS ====================

@router.get("/shop/products")
async def get_my_shop_products(user: dict = Depends(get_current_user)):
    """Get trader's shop products"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    trader, user_col = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    products = await db.shop_products.find({"seller_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)

    for product in products:
        product["stock_count"] = len(product.get("auto_content", []))
        if "auto_content" in product:
            del product["auto_content"]

    return products


@router.post("/shop/products")
async def create_shop_product(data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Create a product in trader's shop"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    trader, user_col = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    shop_settings = trader.get("shop_settings", {})
    if shop_settings.get("is_blocked"):
        raise HTTPException(status_code=403, detail="Ваш магазин заблокирован")

    name = data.get("name") or data.get("title", "")
    description = data.get("description", "")
    price = data.get("price", 0)
    category = data.get("category", "")

    if not name:
        raise HTTPException(status_code=400, detail="Название товара обязательно")
    if not price or float(price) <= 0:
        raise HTTPException(status_code=400, detail="Укажите корректную цену")

    price_variants = []
    if data.get("price_variants"):
        for pv in data["price_variants"]:
            price_variants.append({
                "quantity": pv.get("quantity", 1),
                "price": pv.get("price", price),
                "label": pv.get("label") or f"{pv.get('quantity', 1)} шт."
            })

    product_id = str(uuid.uuid4())
    product_doc = {
        "id": product_id,
        "seller_id": user["id"],
        "seller_nickname": user.get("nickname", ""),
        "seller_type": "trader",
        "name": name,
        "description": description,
        "price": float(price),
        "currency": data.get("currency", "USDT"),
        "category": category,
        "image_url": data.get("image_url", ""),
        "quantity": data.get("quantity", 0),
        "auto_content": data.get("auto_content") or [],
        "is_active": data.get("is_active", True),
        "is_infinite": data.get("is_infinite", False),
        "attached_files": data.get("attached_files") or [],
        "price_variants": price_variants,
        "sold_count": 0,
        "reserved_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await db.shop_products.insert_one(product_doc)

    response = {
        "id": product_id,
        "seller_id": user["id"],
        "seller_nickname": user.get("nickname", ""),
        "seller_type": "trader",
        "name": name,
        "description": description,
        "price": float(price),
        "currency": data.get("currency", "USDT"),
        "category": category,
        "image_url": data.get("image_url", ""),
        "quantity": data.get("quantity", 0),
        "is_active": product_doc["is_active"],
        "price_variants": price_variants,
        "sold_count": 0,
        "stock_count": len(data.get("auto_content") or []),
        "created_at": product_doc["created_at"]
    }

    return response


@router.put("/shop/products/{product_id}")
async def update_shop_product(product_id: str, data: ProductUpdate, user: dict = Depends(get_current_user)):
    """Update a product"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    if update_data:
        await db.shop_products.update_one({"id": product_id}, {"$set": update_data})

    return {"status": "updated"}


@router.delete("/shop/products/{product_id}")
async def delete_shop_product(product_id: str, user: dict = Depends(get_current_user)):
    """Delete a product"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    result = await db.shop_products.delete_one({"id": product_id, "seller_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Товар не найден")

    return {"status": "deleted"}


# ==================== SHOP STOCK MANAGEMENT ====================

@router.post("/shop/products/{product_id}/stock")
async def add_shop_product_stock(product_id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Add stock item (text, file, photo) to product"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    stock_item = {
        "id": str(uuid.uuid4()),
        "text": data.get("text", ""),
        "file_url": data.get("file_url"),
        "photo_url": data.get("photo_url"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await db.shop_products.update_one(
        {"id": product_id},
        {
            "$push": {"auto_content": stock_item},
            "$inc": {"quantity": 1}
        }
    )

    return {"status": "added", "item": stock_item}


@router.post("/shop/products/{product_id}/stock/bulk")
async def add_shop_product_stock_bulk(product_id: str, items: List[dict] = Body(...), user: dict = Depends(get_current_user)):
    """Add multiple stock items to product"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    stock_items = []
    for item in items:
        stock_items.append({
            "id": str(uuid.uuid4()),
            "text": item.get("text", ""),
            "file_url": item.get("file_url"),
            "photo_url": item.get("photo_url"),
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    await db.shop_products.update_one(
        {"id": product_id},
        {
            "$push": {"auto_content": {"$each": stock_items}},
            "$inc": {"quantity": len(stock_items)}
        }
    )

    return {"status": "added", "added_count": len(stock_items)}


@router.post("/shop/products/{product_id}/upload-stock")
async def upload_shop_product_stock(product_id: str, content: str = Body(...), user: dict = Depends(get_current_user)):
    """Upload stock from text (one item per line)"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    lines = [line.strip() for line in content.strip().split('\n') if line.strip()]

    if not lines:
        raise HTTPException(status_code=400, detail="Файл пустой или не содержит данных")

    stock_items = []
    for line in lines:
        stock_items.append({
            "id": str(uuid.uuid4()),
            "text": line,
            "file_url": None,
            "photo_url": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    await db.shop_products.update_one(
        {"id": product_id},
        {
            "$push": {"auto_content": {"$each": stock_items}},
            "$inc": {"quantity": len(stock_items)}
        }
    )

    return {"status": "uploaded", "added_count": len(stock_items)}


@router.get("/shop/products/{product_id}/download-stock")
async def download_shop_product_stock(product_id: str, user: dict = Depends(get_current_user)):
    """Download remaining stock as text"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    auto_content = product.get("auto_content", [])
    texts = []
    for item in auto_content:
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, dict):
            texts.append(item.get("text", ""))

    return {"content": "\n".join(texts), "count": len(auto_content)}


@router.get("/shop/products/{product_id}/stock")
async def get_shop_product_stock(product_id: str, user: dict = Depends(get_current_user)):
    """Get stock items for a product"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    auto_content = product.get("auto_content", [])
    items = []
    for item in auto_content:
        if isinstance(item, str):
            items.append({"id": str(uuid.uuid4()), "text": item, "file_url": None, "photo_url": None})
        else:
            items.append(item)

    return {"items": items, "count": len(items)}


@router.delete("/shop/products/{product_id}/stock/{item_id}")
async def delete_shop_product_stock_item(product_id: str, item_id: str, user: dict = Depends(get_current_user)):
    """Delete a specific stock item"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    auto_content = product.get("auto_content", [])
    new_content = [item for item in auto_content if not (isinstance(item, dict) and item.get("id") == item_id)]

    if len(new_content) == len(auto_content):
        raise HTTPException(status_code=404, detail="Элемент не найден")

    await db.shop_products.update_one(
        {"id": product_id},
        {"$set": {"auto_content": new_content, "quantity": len(new_content)}}
    )

    return {"status": "deleted"}


@router.put("/shop/products/{product_id}/stock/{item_id}")
async def update_shop_product_stock_item(product_id: str, item_id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Update a specific stock item"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    product = await db.shop_products.find_one({"id": product_id, "seller_id": user["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    auto_content = product.get("auto_content", [])
    updated = False

    for i, item in enumerate(auto_content):
        if isinstance(item, dict) and item.get("id") == item_id:
            auto_content[i] = {
                "id": item_id,
                "text": data.get("text", item.get("text", "")),
                "file_url": data.get("file_url", item.get("file_url")),
                "photo_url": data.get("photo_url", item.get("photo_url")),
                "created_at": item.get("created_at", datetime.now(timezone.utc).isoformat())
            }
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Элемент не найден")

    await db.shop_products.update_one(
        {"id": product_id},
        {"$set": {"auto_content": auto_content}}
    )

    return {"status": "updated"}


@router.post("/shop/products/{product_id}/reserve")
async def reserve_product_stock(product_id: str, quantity: int = 1, user: dict = Depends(get_current_user)):
    """Reserve product stock for a pending purchase"""
    product = await db.shop_products.find_one({"id": product_id, "is_active": True}, {"_id": 0})
    if not product:
        product = await db.products.find_one({"id": product_id, "is_active": True}, {"_id": 0})

    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    available = len(product.get("auto_content", [])) - product.get("reserved_count", 0)
    if available < quantity:
        raise HTTPException(status_code=400, detail=f"Недостаточно товара. Доступно: {available}")

    collection = db.shop_products if product.get("seller_type") == "trader" else db.products
    await collection.update_one(
        {"id": product_id},
        {"$inc": {"reserved_count": quantity}}
    )

    reservation_id = str(uuid.uuid4())
    await db.product_reservations.insert_one({
        "id": reservation_id,
        "product_id": product_id,
        "quantity": quantity,
        "user_id": user["id"],
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    })

    return {"reservation_id": reservation_id, "quantity": quantity, "expires_in": "24h"}


@router.post("/shop/products/release-reservation/{reservation_id}")
async def release_product_reservation(reservation_id: str, user: dict = Depends(get_current_user)):
    """Release a product reservation"""
    reservation = await db.product_reservations.find_one(
        {"id": reservation_id, "user_id": user["id"], "status": "active"},
        {"_id": 0}
    )

    if not reservation:
        raise HTTPException(status_code=404, detail="Резервация не найдена")

    product_id = reservation["product_id"]
    quantity = reservation["quantity"]

    product = await db.shop_products.find_one({"id": product_id}, {"_id": 0})
    collection = db.shop_products if product else db.products

    await collection.update_one(
        {"id": product_id},
        {"$inc": {"reserved_count": -quantity}}
    )

    await db.product_reservations.update_one(
        {"id": reservation_id},
        {"$set": {"status": "released", "released_at": datetime.now(timezone.utc).isoformat()}}
    )

    return {"status": "released"}


# ==================== SHOP SALES ====================

@router.get("/shop/sales")
async def get_shop_sales(user: dict = Depends(get_current_user)):
    """Get trader's shop sales history"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    sales = await db.marketplace_purchases.find(
        {"seller_id": user["id"]},
        {"_id": 0, "delivered_content": 0}
    ).sort("created_at", -1).to_list(100)

    return sales


# ==================== SHOP MESSAGES ====================

@router.post("/shop/{shop_id}/messages")
async def send_message_to_shop(shop_id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Send a message to a shop"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")

    shop = await db.traders.find_one({"id": shop_id, "has_shop": True}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Магазин не найден")

    shop_name = shop.get("shop_settings", {}).get("shop_name", shop.get("nickname", "Магазин"))

    conversation = await db.shop_conversations.find_one({
        "shop_id": shop_id,
        "customer_id": user["id"]
    })

    if not conversation:
        conversation_id = str(uuid.uuid4())
        conversation = {
            "id": conversation_id,
            "shop_id": shop_id,
            "shop_name": shop_name,
            "customer_id": user["id"],
            "customer_nickname": user.get("nickname", "Пользователь"),
            "messages": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "unread_shop": 0,
            "unread_customer": 0
        }
        await db.shop_conversations.insert_one(conversation)
    else:
        conversation_id = conversation["id"]

    msg = {
        "id": str(uuid.uuid4()),
        "sender_type": "customer",
        "sender_id": user["id"],
        "sender_name": user.get("nickname", "Пользователь"),
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await db.shop_conversations.update_one(
        {"id": conversation_id},
        {
            "$push": {"messages": msg},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$inc": {"unread_shop": 1}
        }
    )

    return {"status": "sent", "conversation_id": conversation_id}


@router.get("/shop/messages")
async def get_shop_conversations(user: dict = Depends(get_current_user)):
    """Get all conversations for shop owner"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    trader, _ = await find_shop_user(user["id"])
    if not trader or not trader.get("has_shop"):
        raise HTTPException(status_code=404, detail="У вас нет магазина")

    conversations = await db.shop_conversations.find(
        {"shop_id": user["id"]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(100)

    return conversations


@router.get("/shop/messages/{conversation_id}")
async def get_shop_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    """Get conversation messages"""
    conversation = await db.shop_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conversation:
        raise HTTPException(status_code=404, detail="Переписка не найдена")

    if conversation["shop_id"] != user["id"] and conversation["customer_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Нет доступа")

    if conversation["shop_id"] == user["id"]:
        await db.shop_conversations.update_one(
            {"id": conversation_id},
            {"$set": {"unread_shop": 0}}
        )
    else:
        await db.shop_conversations.update_one(
            {"id": conversation_id},
            {"$set": {"unread_customer": 0}}
        )

    return conversation


@router.post("/shop/messages/{conversation_id}/reply")
async def shop_reply(conversation_id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Shop owner replies to customer"""
    if user.get("role") not in ("trader", "merchant"):
        raise HTTPException(status_code=403, detail="Только для трейдеров и мерчантов")

    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")

    conversation = await db.shop_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conversation:
        raise HTTPException(status_code=404, detail="Переписка не найдена")

    if conversation["shop_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Это не ваш магазин")

    trader, _ = await find_shop_user(user["id"])
    shop_name = trader.get("shop_settings", {}).get("shop_name", "Магазин")

    msg = {
        "id": str(uuid.uuid4()),
        "sender_type": "shop",
        "sender_id": user["id"],
        "sender_name": shop_name,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await db.shop_conversations.update_one(
        {"id": conversation_id},
        {
            "$push": {"messages": msg},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$inc": {"unread_customer": 1}
        }
    )

    return {"status": "sent"}


@router.get("/my/shop-conversations")
async def get_my_shop_conversations(user: dict = Depends(get_current_user)):
    """Get all shop conversations for current user (buyer side)"""
    conversations = await db.shop_conversations.find(
        {"customer_id": user["id"]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(100)

    return conversations


@router.get("/my/shop-conversations/{conversation_id}")
async def get_my_shop_conversation_detail(conversation_id: str, user: dict = Depends(get_current_user)):
    """Get specific shop conversation for buyer"""
    conversation = await db.shop_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conversation:
        raise HTTPException(status_code=404, detail="Переписка не найдена")

    if conversation["customer_id"] != user["id"] and conversation["shop_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Нет доступа")

    # Mark as read for customer
    if conversation["customer_id"] == user["id"]:
        await db.shop_conversations.update_one(
            {"id": conversation_id},
            {"$set": {"unread_customer": 0}}
        )

    return conversation


@router.post("/my/shop-conversations/{conversation_id}/reply")
async def buyer_reply_to_shop(conversation_id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Buyer replies to shop conversation"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")

    conversation = await db.shop_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conversation:
        raise HTTPException(status_code=404, detail="Переписка не найдена")

    if conversation["customer_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Это не ваша переписка")

    msg = {
        "id": str(uuid.uuid4()),
        "sender_type": "customer",
        "sender_id": user["id"],
        "sender_name": user.get("nickname", "Покупатель"),
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await db.shop_conversations.update_one(
        {"id": conversation_id},
        {
            "$push": {"messages": msg},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$inc": {"unread_shop": 1}
        }
    )

    return {"status": "sent"}


@router.get("/admin/shop-conversations")
async def admin_get_all_shop_conversations(user: dict = Depends(get_current_user)):
    """Admin: get all shop conversations"""
    if user.get("role") not in ["admin", "moderator"]:
        raise HTTPException(status_code=403, detail="Только для администратора")

    conversations = await db.shop_conversations.find(
        {},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(200)

    return conversations


@router.get("/admin/marketplace-orders")
async def admin_get_marketplace_orders(
    status: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Admin: get all marketplace orders with enrichment"""
    if user.get("role") not in ["admin", "moderator"]:
        raise HTTPException(status_code=403, detail="Только для администратора")

    query = {}
    if status:
        query["status"] = status

    orders = await db.marketplace_purchases.find(
        query,
        {"_id": 0, "delivered_content": 0, "reserved_content": 0}
    ).sort("created_at", -1).to_list(200)

    # Enrich with seller/buyer info
    for order in orders:
        seller = await db.traders.find_one({"id": order.get("seller_id")}, {"_id": 0, "nickname": 1, "shop_settings": 1})
        if seller:
            order["shop_name"] = seller.get("shop_settings", {}).get("shop_name", seller.get("nickname", ""))
        buyer = await db.traders.find_one({"id": order.get("buyer_id")}, {"_id": 0, "nickname": 1})
        if buyer:
            order["buyer_nickname"] = buyer.get("nickname", "")

    return orders


# ==================== ADMIN: SHOP WITHDRAWALS ====================

@router.get("/admin/shop-withdrawals")
async def admin_get_shop_withdrawals(
    status: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Admin: get all shop withdrawal requests"""
    if user.get("role") not in ["admin", "moderator"]:
        raise HTTPException(status_code=403, detail="Только для администратора")

    query = {}
    if status:
        query["status"] = status

    withdrawals = await db.shop_withdrawals.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)

    for w in withdrawals:
        seller = await db.traders.find_one({"id": w.get("seller_id")}, {"_id": 0, "nickname": 1, "shop_settings": 1})
        if seller:
            w["shop_name"] = seller.get("shop_settings", {}).get("shop_name", seller.get("nickname", ""))

    return withdrawals


@router.post("/admin/shop-withdrawals/{withdrawal_id}/approve")
async def admin_approve_withdrawal(
    withdrawal_id: str,
    data: dict = Body({}),
    user: dict = Depends(get_current_user)
):
    """Admin approves a shop withdrawal request"""
    if user.get("role") not in ["admin"]:
        raise HTTPException(status_code=403, detail="Только для администратора")

    withdrawal = await db.shop_withdrawals.find_one({"id": withdrawal_id}, {"_id": 0})
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Заявка на вывод не найдена")

    if withdrawal["status"] != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже обработана")

    tx_hash = data.get("tx_hash", "")

    await db.shop_withdrawals.update_one(
        {"id": withdrawal_id},
        {"$set": {
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": user["id"],
            "tx_hash": tx_hash
        }}
    )

    # Check both collections for the seller
    seller_doc = await db.traders.find_one({"id": withdrawal["seller_id"]})
    seller_col = db.traders if seller_doc else db.merchants
    await seller_col.update_one(
        {"id": withdrawal["seller_id"]},
        {"$inc": {"shop_balance_reserved": -withdrawal["amount"]}}
    )

    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": withdrawal["seller_id"],
        "type": "withdrawal_approved",
        "title": "Вывод одобрен",
        "message": f"Ваш запрос на вывод {withdrawal['amount']:.2f} USDT одобрен" + (f". TX: {tx_hash}" if tx_hash else ""),
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"status": "approved"}


@router.post("/admin/shop-withdrawals/{withdrawal_id}/reject")
async def admin_reject_withdrawal(
    withdrawal_id: str,
    data: dict = Body({}),
    user: dict = Depends(get_current_user)
):
    """Admin rejects a shop withdrawal request"""
    if user.get("role") not in ["admin"]:
        raise HTTPException(status_code=403, detail="Только для администратора")

    withdrawal = await db.shop_withdrawals.find_one({"id": withdrawal_id}, {"_id": 0})
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Заявка на вывод не найдена")

    if withdrawal["status"] != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже обработана")

    reason = data.get("reason", "")

    await db.shop_withdrawals.update_one(
        {"id": withdrawal_id},
        {"$set": {
            "status": "rejected",
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "rejected_by": user["id"],
            "reject_reason": reason
        }}
    )

    # Return funds to shop balance - check both collections
    seller_doc = await db.traders.find_one({"id": withdrawal["seller_id"]})
    seller_col = db.traders if seller_doc else db.merchants
    await seller_col.update_one(
        {"id": withdrawal["seller_id"]},
        {"$inc": {
            "shop_balance": withdrawal["amount"],
            "shop_balance_reserved": -withdrawal["amount"]
        }}
    )

    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": withdrawal["seller_id"],
        "type": "withdrawal_rejected",
        "title": "Вывод отклонён",
        "message": f"Ваш запрос на вывод {withdrawal['amount']:.2f} USDT отклонён" + (f". Причина: {reason}" if reason else ""),
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"status": "rejected"}
