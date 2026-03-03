"""
Merchant routes - Merchant shop and product management
Routes for merchant-specific shop operations
"""
from fastapi import APIRouter, HTTPException, Depends, Body
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


@router.get("/dashboard")
async def get_merchant_dashboard(user: dict = Depends(get_current_user)):
    """Get merchant dashboard data"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    merchant = await db.merchants.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0, "password": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")

    # Get trade stats
    trades = await db.trades.find({"merchant_id": user["id"]}, {"_id": 0}).to_list(1000)
    completed_trades = [t for t in trades if t.get("status") == "completed"]
    active_trades = [t for t in trades if t.get("status") in ["pending_payment", "payment_sent", "confirming"]]

    # Get recent payment links
    payment_links = await db.payment_links.find(
        {"merchant_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)

    # Get pending withdrawals
    pending_withdrawals = await db.withdrawals.count_documents({
        "user_id": user["id"], "status": "pending"
    })

    return {
        "merchant": merchant,
        "balance": merchant.get("balance", 0),
        "balance_rub": merchant.get("balance_rub", 0),
        "stats": {
            "total_trades": len(trades),
            "completed_trades": len(completed_trades),
            "active_trades": len(active_trades),
            "volume_usdt": round(sum(t.get("merchant_receives_usdt", 0) or t.get("amount", 0) for t in completed_trades), 2),
            # Use client_amount_rub (сумма пополнения клиента)
            "volume_rub": round(sum(t.get("client_amount_rub") or t.get("total_rub", 0) for t in completed_trades), 2),
        },
        "recent_payments": payment_links,
        "pending_withdrawals": pending_withdrawals,
        "status": merchant.get("status", "pending"),
        "commission_rate": merchant.get("commission_rate", 0),
        "api_key": merchant.get("api_key", ""),
    }


@router.get("/deals-archive")
async def get_merchant_deals_archive(limit: int = 50, offset: int = 0, user: dict = Depends(get_current_user)):
    """Get merchant's completed/cancelled deals archive"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    trades = await db.trades.find(
        {"merchant_id": user["id"], "status": {"$in": ["completed", "cancelled", "expired", "disputed"]}},
        {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)

    return trades


@router.get("/deals-archive/{order_id}")
async def get_merchant_deal_detail(order_id: str, user: dict = Depends(get_current_user)):
    """Get detailed info about a specific deal"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    trade = await db.trades.find_one(
        {"id": order_id, "merchant_id": user["id"]},
        {"_id": 0}
    )
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    return trade


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


# ================== MERCHANT DISPUTE MANAGEMENT (JWT-based) ==================

@router.get("/disputes")
async def get_merchant_disputes(status: str = None, user: dict = Depends(get_current_user)):
    """Get merchant's disputed trades"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    query = {"merchant_id": user["id"]}
    if status == "disputed":
        query["status"] = {"$in": ["disputed", "dispute"]}
    elif status == "resolved":
        query["status"] = {"$in": ["completed", "cancelled", "refunded"]}
        query["dispute_resolved_at"] = {"$exists": True}
    else:
        # All trades that have been disputed at some point
        query["$or"] = [
            {"status": {"$in": ["disputed", "dispute"]}},
            {"has_dispute": True},
            {"dispute_resolved_at": {"$exists": True}},
            {"disputed_at": {"$exists": True}}
        ]

    trades = await db.trades.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)

    result = []
    for trade in trades:
        invoice = await db.merchant_invoices.find_one(
            {"trade_id": trade["id"]}, {"_id": 0, "id": 1, "external_order_id": 1}
        )
        result.append({
            "id": trade["id"],
            "trade_id": trade["id"],
            "payment_id": invoice["id"] if invoice else None,
            "order_id": invoice.get("external_order_id") if invoice else None,
            "status": trade["status"],
            "amount_rub": trade.get("amount_rub"),
            "amount_usdt": trade.get("amount_usdt"),
            "trader_login": trade.get("trader_login", ""),
            "disputed_at": trade.get("disputed_at"),
            "disputed_by": trade.get("disputed_by"),
            "dispute_reason": trade.get("dispute_reason"),
            "dispute_resolved_at": trade.get("dispute_resolved_at"),
            "dispute_resolution": trade.get("dispute_resolution"),
            "created_at": trade.get("created_at")
        })

    return result


@router.post("/disputes/{trade_id}/open")
async def merchant_open_dispute_jwt(trade_id: str, data: dict = Body(default={}), user: dict = Depends(get_current_user)):
    """Merchant opens a dispute on a trade (JWT auth)"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    trade = await db.trades.find_one({"id": trade_id, "merchant_id": user["id"]}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    if trade["status"] == "disputed":
        raise HTTPException(status_code=400, detail="Спор уже открыт")

    if trade["status"] not in ["paid", "pending"]:
        raise HTTPException(status_code=400, detail=f"Нельзя открыть спор для сделки в статусе '{trade['status']}'")

    reason = data.get("reason", "") or "Спор открыт мерчантом"

    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "disputed",
            "disputed_at": datetime.now(timezone.utc).isoformat(),
            "dispute_reason": reason,
            "disputed_by": f"merchant:{user['id']}"
        }}
    )

    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": f"\u26a0\ufe0f Спор открыт мерчантом! Причина: {reason}. Администратор подключится к чату.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)

    # Create/update unified conversation for admin
    existing_conv = await db.unified_conversations.find_one(
        {"related_id": trade_id, "type": {"$in": ["p2p_dispute", "p2p_trade"]}},
        {"_id": 0}
    )
    if existing_conv:
        await db.unified_conversations.update_one(
            {"id": existing_conv["id"]},
            {"$set": {"status": "disputed", "archived": False, "resolved": False}}
        )
    else:
        merchant = await db.merchants.find_one({"id": user["id"]}, {"_id": 0})
        merchant_name = merchant.get("name", merchant.get("login", "Merchant")) if merchant else "Merchant"
        new_conv = {
            "id": str(uuid.uuid4()),
            "type": "p2p_dispute",
            "related_id": trade_id,
            "status": "disputed",
            "title": f"Спор: {trade.get('amount_usdt', 0)} USDT ({merchant_name})",
            "participants": [trade.get("trader_id"), f"merchant:{user['id']}"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "archived": False,
            "resolved": False,
            "unread_counts": {}
        }
        await db.unified_conversations.insert_one(new_conv)

    try:
        from routes.ws_routes import ws_manager
        if ws_manager:
            await ws_manager.broadcast(f"trade_{trade_id}", {
                "type": "status_update", "status": "disputed", "trade_id": trade_id
            })
    except Exception:
        pass

    return {"status": "disputed", "trade_id": trade_id}


@router.get("/disputes/{trade_id}/messages")
async def get_merchant_dispute_messages_jwt(trade_id: str, user: dict = Depends(get_current_user)):
    """Get messages for a disputed trade (merchant JWT auth)"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    trade = await db.trades.find_one({"id": trade_id, "merchant_id": user["id"]}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    messages = await db.trade_messages.find(
        {"trade_id": trade_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)

    return messages


@router.post("/disputes/{trade_id}/messages")
async def merchant_send_dispute_message_jwt(trade_id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Merchant sends a message in dispute chat (JWT auth)"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    trade = await db.trades.find_one({"id": trade_id, "merchant_id": user["id"]}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    if trade["status"] not in ["disputed", "paid", "completed"]:
        raise HTTPException(status_code=400, detail=f"Нельзя писать в чат сделки со статусом '{trade['status']}'")

    content = data.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")

    merchant = await db.merchants.find_one({"id": user["id"]}, {"_id": 0})
    merchant_name = merchant.get("name", merchant.get("login", "Merchant")) if merchant else "Merchant"

    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": user["id"],
        "sender_type": "merchant",
        "sender_role": "merchant",
        "sender_nickname": merchant_name,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(msg)

    try:
        from routes.ws_routes import ws_manager
        if ws_manager:
            await ws_manager.broadcast(f"trade_{trade_id}", {
                "type": "new_message",
                "message": {k: v for k, v in msg.items() if k != "_id"}
            })
    except Exception:
        pass

    return {k: v for k, v in msg.items() if k != "_id"}


@router.get("/analytics")
async def get_merchant_analytics(user: dict = Depends(get_current_user)):
    """Comprehensive merchant analytics - deposits, payouts, commissions, history"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")
    
    merchant_id = user["id"]
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0})
    if not merchant:
        raise HTTPException(status_code=404, detail="Мерчант не найден")
    
    deposit_trades = await db.trades.find(
        {"merchant_id": merchant_id, "status": "completed"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    
    # Use client_amount_rub (сумма пополнения клиента), not amount_rub (сумма оплаты)
    total_deposits_usdt = sum(t.get("merchant_receives_usdt", 0) or t.get("amount_usdt", 0) for t in deposit_trades)
    total_deposits_rub = sum(t.get("client_amount_rub") or t.get("amount_rub", 0) for t in deposit_trades)
    # Commission in USDT - use merchant_commission field
    total_deposit_commission = sum(t.get("merchant_commission", 0) or 0 for t in deposit_trades)
    deposits_count = len(deposit_trades)
    
    active_trades = await db.trades.count_documents(
        {"merchant_id": merchant_id, "status": {"$in": ["pending", "paid"]}}
    )
    disputed_trades = await db.trades.count_documents(
        {"merchant_id": merchant_id, "status": "disputed"}
    )
    cancelled_trades = await db.trades.count_documents(
        {"merchant_id": merchant_id, "status": "cancelled"}
    )
    
    sell_offers = await db.crypto_sell_offers.find(
        {"merchant_id": merchant_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    
    active_offers = [o for o in sell_offers if o.get("status") == "active"]
    completed_offers = [o for o in sell_offers if o.get("status") in ("completed", "in_progress")]
    cancelled_offers = [o for o in sell_offers if o.get("status") == "cancelled"]
    
    total_payout_usdt = sum(o.get("usdt_from_merchant", 0) for o in sell_offers if o.get("status") != "cancelled")
    total_payout_rub = sum(o.get("amount_rub", 0) for o in sell_offers if o.get("status") != "cancelled")
    total_payout_profit_platform = sum(o.get("platform_profit", 0) for o in sell_offers if o.get("status") != "cancelled")
    
    crypto_orders = await db.crypto_orders.find(
        {"merchant_id": merchant_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    
    completed_orders = [o for o in crypto_orders if o.get("status") == "completed"]
    pending_orders = [o for o in crypto_orders if o.get("status") in ("pending", "pending_payment")]
    disputed_orders = [o for o in crypto_orders if o.get("status") == "dispute"]
    
    invoices = await db.merchant_invoices.find(
        {"merchant_id": merchant_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    
    total_invoices = len(invoices)
    paid_invoices = len([i for i in invoices if i.get("status") == "paid"])
    pending_invoices = len([i for i in invoices if i.get("status") == "pending"])
    expired_invoices = len([i for i in invoices if i.get("status") == "expired"])
    
    withdrawals = await db.merchant_withdrawals.find(
        {"merchant_id": merchant_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    total_withdrawn = sum(w.get("amount", 0) for w in withdrawals if w.get("status") == "completed")
    pending_withdrawals = [w for w in withdrawals if w.get("status") == "pending"]
    
    recent = []
    for t in deposit_trades[:10]:
        recent.append({
            "id": t.get("id"),
            "type": "deposit",
            "amount_usdt": t.get("merchant_receives_usdt", 0) or t.get("amount_usdt", 0),
            # Use client_amount_rub (сумма пополнения клиента)
            "amount_rub": t.get("client_amount_rub") or t.get("amount_rub", 0),
            "commission": t.get("merchant_commission", 0),
            "status": t.get("status"),
            "created_at": t.get("created_at"),
            "completed_at": t.get("completed_at"),
            "trader": t.get("trader_login", "")
        })
    
    for o in sell_offers[:10]:
        recent.append({
            "id": o.get("id"),
            "type": "payout",
            "amount_usdt": o.get("usdt_from_merchant", 0),
            "amount_rub": o.get("amount_rub", 0),
            "commission_pct": o.get("withdrawal_commission", 0),
            "platform_profit": o.get("platform_profit", 0),
            "status": o.get("status"),
            "created_at": o.get("created_at"),
            "merchant_rate": o.get("merchant_rate", 0),
            "sell_rate": o.get("sell_rate", 0)
        })
    
    recent.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    
    settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = settings.get("base_rate", 100.0) if settings else 100.0
    sell_rate = settings.get("sell_rate", 110.0) if settings else 110.0
    
    wc = merchant.get("withdrawal_commission", 3.0)
    merchant_rate = base_rate * (1 - wc / 100)
    
    return {
        "merchant": {
            "id": merchant_id,
            "name": merchant.get("merchant_name", ""),
            "nickname": merchant.get("nickname", ""),
            "balance_usdt": merchant.get("balance_usdt", 0),
            "frozen_balance": merchant.get("frozen_balance", 0),
            "commission_rate": merchant.get("commission_rate", 0),
            "withdrawal_commission": wc,
            "fee_model": merchant.get("fee_model", "merchant_pays"),
            "total_commission_paid": merchant.get("total_commission_paid", 0),
            "status": merchant.get("status", "active")
        },
        "deposits": {
            "total_usdt": round(total_deposits_usdt, 4),
            "total_rub": round(total_deposits_rub, 2),
            "total_commission": round(total_deposit_commission, 4),
            "count": deposits_count,
            "active_count": active_trades,
            "disputed_count": disputed_trades,
            "cancelled_count": cancelled_trades
        },
        "payouts": {
            "total_usdt_deducted": round(total_payout_usdt, 4),
            "total_rub": round(total_payout_rub, 2),
            "platform_profit": round(total_payout_profit_platform, 4),
            "active_count": len(active_offers),
            "completed_count": len(completed_offers),
            "cancelled_count": len(cancelled_offers),
            "orders_pending": len(pending_orders),
            "orders_completed": len(completed_orders),
            "orders_disputed": len(disputed_orders)
        },
        "invoices": {
            "total": total_invoices,
            "paid": paid_invoices,
            "pending": pending_invoices,
            "expired": expired_invoices
        },
        "withdrawals": {
            "total_withdrawn": round(total_withdrawn, 4),
            "pending_count": len(pending_withdrawals)
        },
        "rates": {
            "base_rate": base_rate,
            "sell_rate": sell_rate,
            "merchant_rate": round(merchant_rate, 2),
            "withdrawal_commission_pct": wc
        },
        "recent_activity": recent[:20]
    }


@router.get("/trades/{trade_id}/chat")
async def get_merchant_trade_chat(trade_id: str, user: dict = Depends(get_current_user)):
    """Get chat messages for any merchant trade (deposit or payout)"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")

    # Check in trades collection
    trade = await db.trades.find_one({"id": trade_id, "merchant_id": user["id"]}, {"_id": 0})
    
    # Also check in crypto_orders collection
    if not trade:
        trade = await db.crypto_orders.find_one({"id": trade_id, "merchant_id": user["id"]}, {"_id": 0})
    
    # Also check in crypto_sell_offers collection (withdrawal requests)
    if not trade:
        trade = await db.crypto_sell_offers.find_one({"id": trade_id, "merchant_id": user["id"]}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    messages = await db.trade_messages.find(
        {"trade_id": trade_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)

    return {
        "trade": trade,
        "messages": messages
    }


@router.get("/merchant/payout-history")
async def get_merchant_payout_history(user: dict = Depends(get_current_user)):
    """Get merchant's completed/cancelled payout offers with associated orders"""
    if user.get("role") != "merchant":
        raise HTTPException(status_code=403, detail="Доступно только для мерчантов")
    
    user_id = user["id"]
    
    # Get all sell offers (payouts) for this merchant
    offers = await db.crypto_sell_offers.find(
        {"merchant_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Get all crypto orders for this merchant
    orders = await db.crypto_orders.find(
        {"merchant_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Enrich orders with chat availability
    for o in orders:
        msg_count = await db.trade_messages.count_documents({"trade_id": o["id"]})
        o["has_chat"] = msg_count > 0
        o["message_count"] = msg_count
    
    return {
        "offers": offers,
        "orders": orders
    }

