from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
from typing import Optional

from core.database import db
from core.auth import require_role, get_current_user
from .utils import find_shop_user
import uuid

router = APIRouter()

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
    
    is_active = data.get("is_active", True)
    
    result = await db.shop_products.update_one(
        {"id": product_id},
        {"$set": {"is_active": is_active}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    return {"status": "updated", "is_active": is_active}


@router.delete("/admin/products/{product_id}")
async def delete_product_admin(product_id: str, user: dict = Depends(get_current_user)):
    """Delete product by admin"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для админов")
    
    result = await db.shop_products.delete_one({"id": product_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Товар не найден")
        
    return {"status": "deleted"}


@router.get("/admin/inventory/monitoring")
async def get_inventory_monitoring(user: dict = Depends(require_role(["admin", "mod_market"]))):
    """Get inventory monitoring data"""
    # Low stock products
    low_stock = await db.shop_products.find(
        {"quantity": {"$lt": 5}, "is_infinite": False},
        {"_id": 0, "auto_content": 0}
    ).to_list(50)
    
    for p in low_stock:
        seller = await db.traders.find_one({"id": p["seller_id"]}, {"_id": 0, "nickname": 1})
        if seller:
            p["seller_nickname"] = seller.get("nickname", "")
            
    # Out of stock products
    out_of_stock = await db.shop_products.find(
        {"quantity": 0, "is_infinite": False},
        {"_id": 0, "auto_content": 0}
    ).to_list(50)
    
    for p in out_of_stock:
        seller = await db.traders.find_one({"id": p["seller_id"]}, {"_id": 0, "nickname": 1})
        if seller:
            p["seller_nickname"] = seller.get("nickname", "")
            
    return {
        "low_stock": low_stock,
        "out_of_stock": out_of_stock
    }


@router.post("/admin/transfer")
async def admin_transfer(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Admin transfer between users"""
    sender_id = data.get("sender_id")
    recipient_id = data.get("recipient_id")
    amount = data.get("amount")
    reason = data.get("reason", "Admin transfer")
    
    if not sender_id or not recipient_id or not amount:
        raise HTTPException(status_code=400, detail="Missing required fields")
        
    # Check sender balance
    sender = await db.traders.find_one({"id": sender_id})
    if not sender:
        sender = await db.merchants.find_one({"id": sender_id})
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
        
    if sender.get("balance_usdt", 0) < amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")
        
    # Execute transfer
    await db.traders.update_one({"id": sender_id}, {"$inc": {"balance_usdt": -amount}})
    await db.traders.update_one({"id": recipient_id}, {"$inc": {"balance_usdt": amount}})
    
    # Log
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": user["id"],
        "action": "admin_transfer",
        "details": f"Transferred {amount} USDT from {sender_id} to {recipient_id}. Reason: {reason}",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"status": "success"}

@router.get("/admin/shop-conversations")
async def admin_get_all_shop_conversations(user: dict = Depends(require_role(["admin", "mod_market"]))):
    """Get all shop conversations for admin/moderator"""
    conversations = await db.unified_conversations.find(
        {"type": "shop_support"},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    
    return conversations


@router.get("/admin/marketplace-orders")
async def admin_get_marketplace_orders(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(require_role(["admin", "mod_market"]))
):
    """Get marketplace orders for admin"""
    query = {}
    if status:
        query["status"] = status
        
    total = await db.marketplace_purchases.count_documents(query)
    orders = await db.marketplace_purchases.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).skip((page - 1) * limit).limit(limit).to_list(limit)
    
    # Enrich with seller/buyer info if needed
    for order in orders:
        if not order.get("seller_nickname"):
            seller = await db.traders.find_one({"id": order["seller_id"]}, {"nickname": 1})
            if seller:
                order["seller_nickname"] = seller.get("nickname")
                
        if not order.get("buyer_nickname"):
            buyer = await db.traders.find_one({"id": order["buyer_id"]}, {"nickname": 1})
            if not buyer:
                buyer = await db.merchants.find_one({"id": order["buyer_id"]}, {"nickname": 1})
            if buyer:
                order["buyer_nickname"] = buyer.get("nickname")
    
    return {
        "orders": orders,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@router.get("/admin/shop-withdrawals")
async def admin_get_shop_withdrawals(
    status: Optional[str] = None,
    user: dict = Depends(require_role(["admin", "mod_market"]))
):
    """Get shop withdrawal requests"""
    query = {"type": "shop_withdrawal"}
    if status:
        query["status"] = status
        
    withdrawals = await db.transactions.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    for w in withdrawals:
        user_doc = await db.traders.find_one({"id": w["user_id"]}, {"nickname": 1})
        if user_doc:
            w["user_nickname"] = user_doc.get("nickname")
            
    return withdrawals


@router.post("/admin/shop-withdrawals/{tx_id}/{action}")
async def admin_process_shop_withdrawal(
    tx_id: str,
    action: str,
    user: dict = Depends(require_role(["admin", "mod_market"]))
):
    """Approve or reject shop withdrawal"""
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    tx = await db.transactions.find_one({"id": tx_id, "type": "shop_withdrawal"})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    if tx["status"] != "pending":
        raise HTTPException(status_code=400, detail="Transaction already processed")
        
    if action == "approve":
        # Just update status, money already moved to frozen
        await db.transactions.update_one(
            {"id": tx_id},
            {"$set": {
                "status": "completed",
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "processed_by": user["id"]
            }}
        )
        
        # Unfreeze and deduct from user
        await db.traders.update_one(
            {"id": tx["user_id"]},
            {"$inc": {"frozen_usdt": -tx["amount"]}}
        )
        
    else:
        # Reject - return money to shop balance
        await db.transactions.update_one(
            {"id": tx_id},
            {"$set": {
                "status": "rejected",
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "processed_by": user["id"]
            }}
        )
        
        # Return to shop balance
        await db.traders.update_one(
            {"id": tx["user_id"]},
            {"$inc": {
                "frozen_usdt": -tx["amount"],
                "shop_balance": tx["amount"]
            }}
        )
        
    return {"status": "success"}
