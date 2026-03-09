from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid
from typing import List, Optional

from core.auth import require_role, get_current_user, log_admin_action
from core.database import db
from .utils import get_staff_display_name

router = APIRouter()

# ==================== ADMIN: DISPUTES ====================

@router.get("/msg/admin/disputes")
async def get_admin_disputes(user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Get all disputed trades for admin chat hub"""
    trades = await db.trades.find(
        {"status": "disputed"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    result = []
    for trade in trades:
        # Check if this is a QR aggregator dispute
        is_qr = trade.get("is_qr_aggregator", False)
        # Try to get conversation to check is_qr_aggregator_dispute flag
        conv = await db.unified_conversations.find_one(
            {"type": "p2p_dispute", "related_id": trade.get("id")},
            {"_id": 0, "is_qr_aggregator_dispute": 1, "id": 1}
        )
        if not conv:
            conv = await db.unified_conversations.find_one(
                {"type": "p2p_dispute", "trade_id": trade.get("id")},
                {"_id": 0, "is_qr_aggregator_dispute": 1, "id": 1}
            )
        is_qr_dispute = is_qr or (conv.get("is_qr_aggregator_dispute", False) if conv else False)
        conv_id = conv.get("id") if conv else None
        result.append({
            "id": conv_id or trade.get("id"),
            "trade": trade,
            "title": f"Спор: {trade.get('amount_usdt', trade.get('amount', 0))} USDT",
            "subtitle": f"@{trade.get('buyer_nickname', 'покупатель')} vs @{trade.get('seller_nickname', trade.get('trader_login', 'продавец'))}",
            "type": "p2p_dispute",
            "status": trade.get("status"),
            "created_at": trade.get("created_at"),
            "is_qr_aggregator_dispute": is_qr_dispute
        })
    
    return result


# ==================== ADMIN: CRYPTO PAYOUTS ====================

@router.get("/msg/admin/crypto-payouts")
async def get_admin_crypto_payouts(user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Get crypto payout orders for admin chat hub"""
    orders = await db.crypto_orders.find(
        {"status": {"$in": ["pending", "processing", "paid"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    result = []
    for order in orders:
        buyer = await db.traders.find_one({"id": order.get("buyer_id")}, {"_id": 0, "nickname": 1, "login": 1})
        buyer_name = buyer.get("nickname", buyer.get("login", "")) if buyer else ""
        result.append({
            "id": order.get("id"),
            "order": order,
            "title": f"Покупка {order.get('amount_usdt', '?')} USDT",
            "subtitle": f"@{buyer_name}",
            "buyer_nickname": buyer_name,
            "amount_usdt": order.get("amount_usdt"),
            "type": "crypto_order",
            "status": order.get("status"),
            "created_at": order.get("created_at")
        })
    
    return result


# ==================== ADMIN: MERCHANT APPLICATIONS ====================

@router.get("/msg/admin/merchant-applications")
async def get_admin_merchant_applications(user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Get merchant applications for admin chat hub"""
    # Try unified conversations first
    convs = await db.unified_conversations.find(
        {"type": "merchant_application"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    if convs:
        for conv in convs:
            if conv.get("merchant_id"):
                merchant = await db.merchants.find_one({"id": conv["merchant_id"]}, {"_id": 0, "merchant_name": 1, "merchant_type": 1, "nickname": 1})
                if merchant:
                    conv["merchant_name"] = merchant.get("merchant_name", "")
                    conv["merchant_type"] = merchant.get("merchant_type", "")
                    conv["nickname"] = merchant.get("nickname", "")
        return convs
    
    # Fallback to pending merchants
    merchants = await db.merchants.find(
        {"status": "pending"},
        {"_id": 0, "password_hash": 0, "password": 0}
    ).to_list(100)
    
    result = []
    for m in merchants:
        result.append({
            "id": f"merchant_{m['id']}",
            "related_id": m["id"],
            "merchant_id": m["id"],
            "title": m.get("merchant_name", ""),
            "subtitle": f"@{m.get('nickname', m.get('login', ''))} • {m.get('merchant_type', '')}",
            "merchant_name": m.get("merchant_name", ""),
            "nickname": m.get("nickname", m.get("login", "")),
            "merchant_type": m.get("merchant_type", ""),
            "type": "merchant_application",
            "status": "pending",
            "created_at": m.get("created_at")
        })
    
    return result


# ==================== ADMIN: SHOP APPLICATIONS ====================

@router.get("/msg/admin/shop-applications")
async def get_admin_shop_applications(user: dict = Depends(require_role(["admin", "mod_market"]))):
    """Get shop applications for admin chat hub"""
    convs = await db.unified_conversations.find(
        {"type": "shop_application"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    if convs:
        return convs
    
    # Fallback to pending shop applications
    apps = await db.shop_applications.find(
        {"status": "pending"},
        {"_id": 0}
    ).to_list(100)
    
    result = []
    for app in apps:
        user_info = await db.traders.find_one({"id": app.get("user_id")}, {"_id": 0, "nickname": 1, "login": 1})
        result.append({
            "id": f"shop_{app['id']}",
            "related_id": app["id"],
            "title": app.get("shop_name", ""),
            "subtitle": f"@{user_info.get('nickname', user_info.get('login', '')) if user_info else ''}",
            "shop_name": app.get("shop_name", ""),
            "user_nickname": user_info.get("nickname", "") if user_info else "",
            "type": "shop_application",
            "status": "pending",
            "created_at": app.get("created_at")
        })
    
    return result


# ==================== ADMIN: ARCHIVED CONVERSATIONS ====================

@router.get("/msg/admin/archived")
async def get_admin_archived(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get archived conversations for admin"""
    convs = await db.unified_conversations.find(
        {"archived": True},
        {"_id": 0}
    ).sort("updated_at", -1).limit(100).to_list(100)
    return convs


# ==================== ADMIN: STAFF LIST ====================

@router.get("/msg/admin/staff-list")
async def get_admin_staff_list(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get list of all staff members"""
    staff = await db.admins.find({}, {"_id": 0, "password_hash": 0, "password": 0}).to_list(100)
    return staff


# ==================== ADMIN: SEARCH CONVERSATIONS ====================

@router.get("/msg/admin/search")
async def search_admin_conversations(q: str = "", user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Search conversations by query"""
    if not q:
        return []
    
    # Search in unified conversations
    convs = await db.unified_conversations.find(
        {"$or": [
            {"title": {"$regex": q, "$options": "i"}},
            {"subtitle": {"$regex": q, "$options": "i"}}
        ]},
        {"_id": 0}
    ).limit(50).to_list(50)
    
    # Also search in trades
    trades = await db.trades.find(
        {"$or": [
            {"buyer_nickname": {"$regex": q, "$options": "i"}},
            {"seller_nickname": {"$regex": q, "$options": "i"}},
            {"trader_login": {"$regex": q, "$options": "i"}}
        ]},
        {"_id": 0}
    ).limit(20).to_list(20)
    
    for trade in trades:
        if not any(c.get("related_id") == trade["id"] for c in convs):
            convs.append({
                "id": trade["id"],
                "related_id": trade["id"],
                "title": f"Сделка: {trade.get('amount', 0)} USDT",
                "subtitle": f"@{trade.get('buyer_nickname', '')} ↔ @{trade.get('seller_nickname', trade.get('trader_login', ''))}",
                "type": "p2p_trade",
                "status": trade.get("status"),
                "created_at": trade.get("created_at")
            })
    
    return convs


# ==================== ADMIN: GUARANTOR ORDERS ====================

@router.get("/msg/admin/guarantor-orders")
async def get_admin_guarantor_orders(
    include_resolved: bool = False,
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Get all guarantor deals for admin moderation - includes both P2P and marketplace guarantor deals"""
    # 1. Fetch P2P guarantor deals
    p2p_query = {}
    if not include_resolved:
        p2p_query["status"] = {"$in": ["pending_counterparty", "pending_payment", "funded", "disputed"]}
    
    p2p_orders = await db.guarantor_deals.find(p2p_query, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    # Enrich P2P orders with user info
    for order in p2p_orders:
        order["deal_type"] = "p2p"
        creator = await db.traders.find_one({"id": order.get("creator_id")}, {"_id": 0, "nickname": 1, "login": 1})
        if creator:
            order["creator_nickname"] = creator.get("nickname", creator.get("login", "Unknown"))
        if order.get("counterparty_id"):
            counterparty = await db.traders.find_one({"id": order["counterparty_id"]}, {"_id": 0, "nickname": 1, "login": 1})
            if counterparty:
                order["counterparty_nickname"] = counterparty.get("nickname", counterparty.get("login", "Unknown"))
        # Format for unified display
        order["title"] = order.get("title", "P2P Гарант-сделка")
        order["subtitle"] = f"P2P сделка - {order.get('amount', 0)} {order.get('currency', 'USDT')}"
        order["data"] = {
            "buyer_nickname": order.get("creator_nickname", "") if order.get("creator_role") == "buyer" else order.get("counterparty_nickname", ""),
            "seller_nickname": order.get("counterparty_nickname", "") if order.get("creator_role") == "buyer" else order.get("creator_nickname", ""),
            "total_price": order.get("amount", 0),
            "amount": order.get("amount", 0),
            "product_name": order.get("title", "P2P Гарант-сделка"),
        }

    # 2. Fetch marketplace guarantor purchases
    mkt_query = {"purchase_type": "guarantor"}
    if not include_resolved:
        mkt_query["status"] = {"$in": ["pending_confirmation", "pending", "disputed"]}
    
    mkt_orders = await db.marketplace_purchases.find(mkt_query, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    # Enrich marketplace orders
    for order in mkt_orders:
        order["deal_type"] = "marketplace"
        # Find conversation for this purchase
        conv = await db.unified_conversations.find_one(
            {"type": "marketplace_guarantor", "related_id": order["id"]},
            {"_id": 0, "id": 1}
        )
        order["conversation_id"] = conv["id"] if conv else None
        order["title"] = f"Маркетплейс: {order.get('product_name', 'Товар')}"
        order["subtitle"] = f"Маркетплейс гарант - {order.get('total_price', 0)} USDT"
        order["data"] = {
            "buyer_nickname": order.get("buyer_nickname", ""),
            "seller_nickname": order.get("seller_nickname", ""),
            "total_price": order.get("total_price", 0),
            "amount": order.get("total_with_guarantor", order.get("total_price", 0)),
            "product_name": order.get("product_name", ""),
            "guarantor_fee": order.get("guarantor_fee", 0),
        }

    # Combine both types
    all_orders = p2p_orders + mkt_orders
    # Sort by created_at descending
    all_orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return all_orders


@router.post("/msg/admin/guarantor-orders/{deal_id}/resolve")
async def admin_resolve_guarantor_order(
    deal_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Admin resolves a guarantor deal dispute"""
    deal = await db.guarantor_deals.find_one({"id": deal_id}, {"_id": 0})
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    resolution = data.get("resolution")  # "complete" or "refund"
    reason = data.get("reason", "")
    
    buyer_id = deal["creator_id"] if deal.get("creator_role") == "buyer" else deal.get("counterparty_id")
    seller_id = deal.get("counterparty_id") if deal.get("creator_role") == "buyer" else deal["creator_id"]
    
    now = datetime.now(timezone.utc).isoformat()
    
    if resolution == "complete":
        # Complete deal - transfer to seller minus commission
        seller_receives = deal["amount"] - deal.get("commission", 0)
        if seller_id:
            await db.traders.update_one(
                {"id": seller_id},
                {"$inc": {"balance_usdt": seller_receives}}
            )
        await db.guarantor_deals.update_one(
            {"id": deal_id},
            {"$set": {"status": "completed", "completed_at": now, "resolved_by": user["id"], "resolution_reason": reason}}
        )
    elif resolution == "refund":
        # Refund to buyer
        if buyer_id:
            await db.traders.update_one(
                {"id": buyer_id},
                {"$inc": {"balance_usdt": deal["amount"]}}
            )
        await db.guarantor_deals.update_one(
            {"id": deal_id},
            {"$set": {"status": "refunded", "completed_at": now, "resolved_by": user["id"], "resolution_reason": reason}}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution. Use 'complete' or 'refund'")
    
    return {"status": "resolved", "resolution": resolution}

@router.post("/msg/admin/marketplace-guarantor/{purchase_id}/resolve")
async def admin_resolve_marketplace_guarantor(
    purchase_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Admin resolves a marketplace guarantor purchase"""
    purchase = await db.marketplace_purchases.find_one({"id": purchase_id, "purchase_type": "guarantor"}, {"_id": 0})
    if not purchase:
        raise HTTPException(status_code=404, detail="Marketplace guarantor purchase not found")
    
    resolution = data.get("resolution")  # "complete" or "refund"
    reason = data.get("reason", "")
    now = datetime.now(timezone.utc).isoformat()
    
    buyer_id = purchase["buyer_id"]
    seller_id = purchase["seller_id"]
    total_price = purchase["total_price"]
    total_with_guarantor = purchase.get("total_with_guarantor", total_price)
    commission_rate = purchase.get("commission_rate", 5.0)
    platform_commission = total_price * (commission_rate / 100)
    seller_receives = total_price - platform_commission
    guarantor_fee = purchase.get("guarantor_fee", 0)
    
    if resolution == "complete":
        # Release funds to seller
        await db.traders.update_one(
            {"id": seller_id},
            {"$inc": {"shop_balance": seller_receives}}
        )
        # Release escrow from buyer
        await db.traders.update_one(
            {"id": buyer_id},
            {"$inc": {"balance_escrow": -total_with_guarantor}}
        )
        # Deliver content if available
        reserved = purchase.get("reserved_content", [])
        product_id = purchase.get("product_id")
        if reserved and product_id:
            await db.shop_products.update_one(
                {"id": product_id},
                {"$set": {"auto_content": []}, "$inc": {"reserved_count": -purchase.get("quantity", 1)}}
            )
        # Record commission
        await db.commission_payments.insert_one({
            "id": str(uuid.uuid4()),
            "purchase_id": purchase_id,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "amount": total_price,
            "commission": platform_commission,
            "guarantor_fee": guarantor_fee,
            "type": "marketplace_guarantor",
            "created_at": now
        })
        
        await db.marketplace_purchases.update_one(
            {"id": purchase_id},
            {"$set": {"status": "completed", "completed_at": now, "resolved_by": user["id"], "resolution_reason": reason}}
        )
    elif resolution == "refund":
        # Refund to buyer (full amount including guarantor fee)
        await db.traders.update_one(
            {"id": buyer_id},
            {"$inc": {"balance_usdt": total_with_guarantor, "balance_escrow": -total_with_guarantor}}
        )
        
        # Return stock
        reserved = purchase.get("reserved_content", [])
        product_id = purchase.get("product_id")
        if reserved and product_id:
            await db.shop_products.update_one(
                {"id": product_id},
                {"$push": {"auto_content": {"$each": reserved}}, "$inc": {"stock": purchase.get("quantity", 1), "reserved_count": -purchase.get("quantity", 1)}}
            )
            
        await db.marketplace_purchases.update_one(
            {"id": purchase_id},
            {"$set": {"status": "refunded", "completed_at": now, "resolved_by": user["id"], "resolution_reason": reason}}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution. Use 'complete' or 'refund'")
    
    return {"status": "resolved", "resolution": resolution}


@router.post("/msg/guarantor/decision")
async def guarantor_order_decision(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Make decision on guarantor order (legacy endpoint for compatibility)"""
    deal_id = data.get("deal_id")
    decision = data.get("decision")
    
    if not deal_id or not decision:
        raise HTTPException(status_code=400, detail="Missing deal_id or decision")
        
    # Check if it's a marketplace deal
    mkt_deal = await db.marketplace_purchases.find_one({"id": deal_id}, {"_id": 0})
    if mkt_deal:
        return await admin_resolve_marketplace_guarantor(deal_id, {"resolution": decision, "reason": "Decision via legacy endpoint"}, user)
        
    # Check if it's a P2P deal
    p2p_deal = await db.guarantor_deals.find_one({"id": deal_id}, {"_id": 0})
    if p2p_deal:
        return await admin_resolve_guarantor_order(deal_id, {"resolution": decision, "reason": "Decision via legacy endpoint"}, user)
        
    raise HTTPException(status_code=404, detail="Deal not found")


@router.post("/msg/guarantor/set-deadline")
async def guarantor_set_deadline(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Set deadline for guarantor deal"""
    deal_id = data.get("deal_id")
    hours = data.get("hours", 24)
    
    if not deal_id:
        raise HTTPException(status_code=400, detail="Missing deal_id")
        
    deadline = datetime.now(timezone.utc) + timedelta(hours=hours)
    
    # Try P2P deal
    res = await db.guarantor_deals.update_one(
        {"id": deal_id},
        {"$set": {"deadline": deadline.isoformat()}}
    )
    
    if res.modified_count == 0:
        # Try marketplace deal
        res = await db.marketplace_purchases.update_one(
            {"id": deal_id},
            {"$set": {"deadline": deadline.isoformat()}}
        )
        
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Deal not found")
        
    return {"status": "updated", "deadline": deadline.isoformat()}


# ==================== STAFF CHAT ====================

@router.get("/msg/staff-chat")
async def get_staff_chat(user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))):
    """Get general staff chat messages"""
    messages = await db.staff_messages.find({}, {"_id": 0}).sort("created_at", 1).limit(100).to_list(100)
    return messages


@router.post("/msg/staff-chat")
async def send_staff_message(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))
):
    """Send message to general staff chat"""
    content = data.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
        
    msg = {
        "id": str(uuid.uuid4()),
        "sender_id": user["id"],
        "sender_name": user.get("nickname", user.get("login", "Staff")),
        "sender_role": user.get("admin_role", "staff"),
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.staff_messages.insert_one(msg)
    
    # Broadcast via WebSocket if available
    try:
        from routes.ws_routes import ws_manager
        if ws_manager:
            await ws_manager.broadcast("staff_chat", {"type": "message", **msg})
    except ImportError:
        pass
        
    return msg


@router.get("/msg/staff/online")
async def get_online_staff(user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))):
    """Get list of online staff members"""
    # In a real app, this would check websocket connections or last activity
    # For now, return recent active admins
    five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    
    online_staff = await db.admins.find(
        {"last_active": {"$gte": five_min_ago}},
        {"_id": 0, "id": 1, "login": 1, "nickname": 1, "admin_role": 1}
    ).to_list(100)
    
    return online_staff


# ==================== STAFF PRIVATE MESSAGES ====================

@router.get("/msg/staff/messages")
async def get_staff_messages(user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))):
    """Get private messages for current staff user"""
    messages = await db.staff_private_messages.find(
        {"$or": [{"sender_id": user["id"]}, {"recipient_id": user["id"]}]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    return messages


@router.post("/msg/staff/messages")
async def send_staff_private_message(
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))
):
    """Send private message to another staff member"""
    recipient_id = data.get("recipient_id")
    content = data.get("content", "").strip()
    
    if not recipient_id or not content:
        raise HTTPException(status_code=400, detail="Recipient and content required")
        
    recipient = await db.admins.find_one({"id": recipient_id})
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
        
    msg = {
        "id": str(uuid.uuid4()),
        "sender_id": user["id"],
        "sender_name": user.get("nickname", user.get("login", "Staff")),
        "recipient_id": recipient_id,
        "recipient_name": recipient.get("nickname", recipient.get("login", "Staff")),
        "content": content,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.staff_private_messages.insert_one(msg)
    return msg


# ==================== MERCHANT COMMISSION ====================

@router.post("/admin/merchant/{merchant_id}/pending-commission")
async def set_pending_commission(merchant_id: str, data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Set pending commission for merchant (before approval)"""
    commission = data.get("commission", 0.5)
    admin_role = user.get("admin_role", "admin")
    
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0, "commission_set_by": 1})
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    if merchant.get("commission_set_by") and admin_role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Только админ может изменить комиссию")
    
    await db.merchants.update_one(
        {"id": merchant_id},
        {"$set": {
            "pending_commission": commission,
            "commission_set_by": user["id"],
            "commission_set_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"status": "saved", "commission": commission}


# ==================== CHAT MANAGEMENT (ADD/REMOVE STAFF) ====================

@router.post("/msg/conversations/{conversation_id}/add-staff")
async def add_staff_to_conversation(
    conversation_id: str, 
    data: dict = Body(...), 
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))
):
    """Add a staff member to a conversation"""
    staff_id = data.get("staff_id")
    if not staff_id:
        raise HTTPException(status_code=400, detail="staff_id обязателен")
    
    # Check if conversation exists
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    # Check if conversation is closed
    if conv.get("status") == "closed":
        raise HTTPException(status_code=400, detail="Невозможно добавить персонал в закрытый чат")
    
    # Check if staff member exists
    staff = await db.admins.find_one({"id": staff_id}, {"_id": 0})
    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    
    # Check if staff is already in participants
    participants = conv.get("participants", [])
    staff_participants = conv.get("staff_participants", [])
    
    if staff_id in participants or staff_id in staff_participants:
        raise HTTPException(status_code=400, detail="Сотрудник уже добавлен в чат")
    
    # Add staff to conversation
    now = datetime.now(timezone.utc).isoformat()
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {
            "$addToSet": {"staff_participants": staff_id},
            "$set": {"updated_at": now}
        }
    )
    
    # Get role label for system message
    role_labels = {
        "owner": "👑 Владелец",
        "admin": "🔴 Администратор",
        "mod_p2p": "🟡 Модератор P2P",
        "mod_market": "🟡 Гарант",
        "support": "🔵 Поддержка"
    }
    role_label = role_labels.get(staff.get("admin_role", ""), staff.get("admin_role", "Персонал"))
    
    # Add system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"🔔 {role_label} @{staff.get('login', 'Сотрудник')} добавлен в чат сотрудником @{user.get('login', 'персонал')}",
        "is_system": True,
        "created_at": now
    }
    await db.unified_messages.insert_one(system_msg)
    
    # Create notification for added staff
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": staff_id,
        "type": "added_to_conversation",
        "title": "Вы добавлены в чат",
        "message": f"Сотрудник @{user.get('login')} добавил вас в чат",
        "conversation_id": conversation_id,
        "is_read": False,
        "created_at": now
    })
    
    # Log action
    await log_admin_action(user["id"], "add_staff_to_conversation", "conversation", conversation_id, {
        "added_staff_id": staff_id,
        "added_staff_login": staff.get("login")
    })
    
    return {"status": "added", "staff_login": staff.get("login"), "staff_role": staff.get("admin_role")}


@router.get("/msg/admin/staff-list")
async def get_staff_for_adding(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get list of staff members that can be added to conversations"""
    staff = await db.admins.find(
        {"id": {"$ne": user["id"]}},  # Exclude current user
        {"_id": 0, "password_hash": 0, "password": 0}
    ).to_list(100)
    
    # Add role labels
    role_labels = {
        "owner": "👑 Владелец",
        "admin": "🔴 Админ",
        "mod_p2p": "🟡 P2P Мод",
        "mod_market": "🟡 Гарант",
        "support": "🔵 Поддержка"
    }
    
    for s in staff:
        s["role_label"] = role_labels.get(s.get("admin_role", ""), s.get("admin_role", ""))
    
    return staff


@router.delete("/msg/conversations/{conversation_id}/staff/{staff_id}")
async def remove_staff_from_conversation(
    conversation_id: str,
    staff_id: str,
    user: dict = Depends(require_role(["admin"]))
):
    """Remove a staff member from a conversation (admin only)"""
    conv = await db.unified_conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    # Remove staff from conversation
    await db.unified_conversations.update_one(
        {"id": conversation_id},
        {"$pull": {"staff_participants": staff_id}}
    )
    
    # Get staff info for message
    staff = await db.admins.find_one({"id": staff_id}, {"login": 1, "_id": 0})
    staff_login = staff.get("login", "Сотрудник") if staff else "Сотрудник"
    
    # Add system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_nickname": "Система",
        "sender_role": "system",
        "content": f"❌ Сотрудник @{staff_login} удалён из чата",
        "is_system": True,
        "created_at": now
    }
    await db.unified_messages.insert_one(system_msg)
    
    return {"status": "removed", "staff_login": staff_login}
