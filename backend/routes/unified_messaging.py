"""
Unified Messaging Routes - Migrated from server.py
Handles the unified messaging system, staff chat, and message management
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone, timedelta
import uuid

from core.auth import require_role, get_current_user
from core.database import db

try:
    from routes.ws_routes import ws_manager
except ImportError:
    ws_manager = None

async def _ws_broadcast(channel: str, data: dict):
    if ws_manager:
        await ws_manager.broadcast(channel, data)

router = APIRouter(tags=["messaging"])


# ==================== MESSAGE ROLE CONFIGURATION ====================

MSG_ROLE_COLORS = {
    "user": "#FFFFFF", "buyer": "#FFFFFF", "p2p_seller": "#FFFFFF",
    "shop_owner": "#8B5CF6", "merchant": "#F97316",
    "mod_p2p": "#F59E0B", "mod_market": "#F59E0B",
    "support": "#3B82F6", "admin": "#EF4444", "owner": "#EF4444",
    "system": "#6B7280"
}

MSG_ROLE_ICONS = {"p2p_seller": "💱", "mod_market": "⚖️", "shop_owner": "🏪", "merchant": "🏢"}

MSG_ROLE_NAMES = {
    "user": "Пользователь", "buyer": "Покупатель", "p2p_seller": "Продавец",
    "shop_owner": "Магазин", "merchant": "Мерчант",
    "mod_p2p": "Модератор P2P", "mod_market": "Гарант",
    "support": "Поддержка", "admin": "Администратор", "owner": "Владелец",
    "system": "Система"
}


def get_msg_role_info(role: str, name: str) -> dict:
    """Get display info for message sender"""
    return {
        "name": name,
        "role": role,
        "role_name": MSG_ROLE_NAMES.get(role, role),
        "color": MSG_ROLE_COLORS.get(role, "#FFFFFF"),
        "icon": MSG_ROLE_ICONS.get(role, "")
    }


def can_user_delete_msg(conv_type: str, conv_status: str, user_role: str, is_sender: bool, msg_age_sec: int) -> tuple:
    """Check if user can delete message according to spec"""
    FIVE_MIN = 300
    
    # Admin can delete ALL messages everywhere
    if user_role in ["admin", "owner"]:
        return True, "admin"
    
    # Moderators
    if user_role in ["mod_p2p", "mod_market"]:
        if conv_status == "dispute":
            if is_sender and msg_age_sec <= FIVE_MIN:
                return True, "mod_own"
            if not is_sender:
                return False, "mod_cannot_delete_others_in_dispute"
            return False, "expired"
        if conv_type in ["forum_topic", "support_ticket"]:
            if not is_sender:
                return True, "mod_delete_others"
            if msg_age_sec <= FIVE_MIN:
                return True, "mod_own"
            return False, "expired"
        if conv_type in ["internal_discussion", "staff_chat"]:
            if is_sender and msg_age_sec <= FIVE_MIN:
                return True, "mod_own"
            return False, "denied"
        return False, "mod_no_access"
    
    # Support
    if user_role == "support":
        if conv_type == "support_ticket":
            if not is_sender:
                return True, "support_delete_others"
            if is_sender and msg_age_sec <= FIVE_MIN:
                return True, "support_own"
            return False, "expired"
        if conv_type == "forum_topic":
            if not is_sender:
                return True, "support_delete_others"
            if msg_age_sec <= FIVE_MIN:
                return True, "support_own"
            return False, "expired"
        return False, "denied"
    
    # Regular users
    if conv_status == "dispute":
        return False, "dispute_locked"
    
    if conv_type == "p2p_trade":
        if is_sender and msg_age_sec <= FIVE_MIN:
            return True, "own"
        return False, "p2p_locked_or_expired"
    
    if conv_type == "p2p_merchant":
        if is_sender and msg_age_sec <= FIVE_MIN:
            return True, "own"
        return False, "p2p_merchant_locked_or_expired"
    
    if conv_type in ["marketplace", "marketplace_guarantor"]:
        return False, "marketplace_locked"
    
    if conv_type == "merchant_application":
        return False, "application_locked"
    
    if conv_type == "shop_application":
        return False, "application_locked"
    
    if conv_type == "forum_topic":
        if is_sender and msg_age_sec <= FIVE_MIN:
            return True, "own"
        return False, "expired"
    
    if conv_type == "support_ticket":
        if is_sender and msg_age_sec <= FIVE_MIN:
            return True, "own"
        return False, "expired"
    
    return False, "denied"


# ==================== UNIFIED CONVERSATIONS ====================

@router.get("/msg/conversations")
async def get_user_conversations(user: dict = Depends(get_current_user)):
    """Get all conversations for current user"""
    user_id = user["id"]
    admin_role = user.get("admin_role")
    
    if admin_role:
        query = {
            "$or": [
                {"participants.user_id": user_id},
                {"participants": user_id},
                {"staff_participants": user_id}
            ]
        }
    else:
        query = {
            "$or": [
                {"participants.user_id": user_id},
                {"participants": user_id},
                {"target_user_id": user_id}
            ]
        }
    
    conversations = await db.unified_conversations.find(query, {"_id": 0}).sort("updated_at", -1).to_list(100)
    
    for conv in conversations:
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"], "is_deleted": {"$ne": True}},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        conv["last_message"] = last_msg
        conv["unread_count"] = conv.get("unread_counts", {}).get(user_id, 0)
    
    return conversations


@router.get("/msg/conversations/{conv_id}")
async def get_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    """Get conversation details with messages"""
    user_id = user["id"]
    
    conv = await db.unified_conversations.find_one({"id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    participants = conv.get("participants", [])
    participant_ids = []
    for p in participants:
        if isinstance(p, str):
            participant_ids.append(p)
        elif isinstance(p, dict):
            participant_ids.append(p.get("user_id", ""))
    
    if user_id not in participant_ids and user.get("admin_role") not in ["owner", "admin", "mod_p2p", "mod_market", "support"]:
        raise HTTPException(status_code=403, detail="Нет доступа к чату")
    
    messages = await db.unified_messages.find(
        {"conversation_id": conv_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    await db.unified_conversations.update_one(
        {"id": conv_id},
        {"$set": {f"unread_counts.{user_id}": 0}}
    )
    
    for msg in messages:
        msg["sender_info"] = get_msg_role_info(msg.get("sender_role", "user"), msg.get("sender_name", ""))
    
    return {
        "conversation": conv,
        "messages": messages,
        "role_colors": MSG_ROLE_COLORS,
        "role_names": MSG_ROLE_NAMES
    }


@router.post("/msg/conversations/{conv_id}/send")
async def send_message_to_conv(
    conv_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    """Send message to conversation"""
    user_id = user["id"]
    content = data.get("content", "").strip()
    attachments = data.get("attachments", [])
    
    if not content and not attachments:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    conv = await db.unified_conversations.find_one({"id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    participants = conv.get("participants", []) or conv.get("staff_participants", [])
    participant_ids = []
    for p in participants:
        if isinstance(p, str):
            participant_ids.append(p)
        elif isinstance(p, dict):
            participant_ids.append(p.get("user_id", ""))
    
    is_admin = user.get("admin_role") in ["owner", "admin", "mod_p2p", "mod_market", "support"]
    if user_id not in participant_ids and not is_admin:
        raise HTTPException(status_code=403, detail="Вы не участник этого чата")
    
    sender_role = "user"
    sender_name = user.get("nickname", user.get("login", "User"))
    
    if user.get("admin_role"):
        sender_role = user["admin_role"]
        sender_name = user.get("login", "Admin")
    
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "sender_id": user_id,
        "sender_role": sender_role,
        "sender_name": sender_name,
        "content": content,
        "attachments": attachments,
        "is_system": False,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.unified_messages.insert_one(msg)
    
    all_participants = conv.get("participants", []) or conv.get("staff_participants", [])
    update_unread = {}
    for p in all_participants:
        p_id = p if isinstance(p, str) else p.get("user_id", "")
        if p_id and p_id != user_id:
            update_unread[f"unread_counts.{p_id}"] = 1
    
    await db.unified_conversations.update_one(
        {"id": conv_id},
        {
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat(), "last_message_at": msg["created_at"]},
            "$inc": update_unread
        }
    )
    
    msg.pop("_id", None)
    msg["sender_info"] = get_msg_role_info(sender_role, sender_name)
    await _ws_broadcast(f"conv_{conv_id}", {"type": "message", **msg})
    
    # Also broadcast to trade channel if this is a trade-related conversation
    if conv.get("type") in ["p2p_trade", "p2p_dispute"] and conv.get("related_id"):
        await _ws_broadcast(f"trade_{conv['related_id']}", {"type": "message", **msg})
    
    return msg


@router.delete("/msg/messages/{msg_id}")
async def delete_message(msg_id: str, user: dict = Depends(get_current_user)):
    """Delete a message (with permission check)"""
    user_id = user["id"]
    user_role = user.get("admin_role", "user")
    
    msg = await db.unified_messages.find_one({"id": msg_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    
    if msg.get("is_deleted"):
        raise HTTPException(status_code=400, detail="Сообщение уже удалено")
    
    if msg.get("is_system"):
        raise HTTPException(status_code=400, detail="Системные сообщения нельзя удалить")
    
    conv = await db.unified_conversations.find_one({"id": msg["conversation_id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    created = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))
    age_sec = (datetime.now(timezone.utc) - created).total_seconds()
    is_sender = msg["sender_id"] == user_id
    
    can_delete, reason = can_user_delete_msg(
        conv.get("type", ""),
        conv.get("status", "active"),
        user_role,
        is_sender,
        age_sec
    )
    
    if not can_delete:
        error_msgs = {
            "locked": "В P2P и Marketplace чатах удаление запрещено",
            "dispute": "В споре удаление сообщений заблокировано",
            "expired": "Можно удалить только в течение 5 минут",
            "denied": "Нет прав на удаление"
        }
        raise HTTPException(status_code=403, detail=error_msgs.get(reason, "Нельзя удалить"))
    
    await db.unified_messages.update_one(
        {"id": msg_id},
        {"$set": {
            "is_deleted": True,
            "deleted_by": user_id,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "delete_reason": reason
        }}
    )
    
    return {"status": "deleted", "reason": reason}


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
        result.append({
            "id": trade.get("id"),
            "trade": trade,
            "title": f"Спор: {trade.get('amount', 0)} USDT",
            "subtitle": f"@{trade.get('buyer_nickname', 'покупатель')} vs @{trade.get('seller_nickname', trade.get('trader_login', 'продавец'))}",
            "type": "p2p_dispute",
            "status": trade.get("status"),
            "created_at": trade.get("created_at")
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
            "amount": platform_commission + guarantor_fee,
            "commission_rate": commission_rate,
            "type": "marketplace_guarantor_admin",
            "created_at": now
        })
        await db.marketplace_purchases.update_one(
            {"id": purchase_id},
            {"$set": {
                "status": "completed",
                "completed_at": now,
                "delivered_content": reserved,
                "resolved_by": user["id"],
                "resolution_reason": reason
            }}
        )
        # Update seller stats
        await db.traders.update_one(
            {"id": seller_id},
            {"$inc": {
                "shop_stats.total_sales": total_price,
                "shop_stats.total_orders": 1,
                "shop_stats.total_commission_paid": platform_commission
            }}
        )
        # Send system message to conversation
        conv = await db.unified_conversations.find_one(
            {"type": "marketplace_guarantor", "related_id": purchase_id},
            {"_id": 0, "id": 1}
        )
        if conv:
            await db.unified_messages.insert_one({
                "id": str(uuid.uuid4()),
                "conversation_id": conv["id"],
                "sender_id": "system",
                "sender_nickname": "Система",
                "sender_role": "system",
                "content": f"Администратор подтвердил сделку. Средства переведены продавцу.\n\nПричина: {reason or 'Не указана'}",
                "is_system": True,
                "created_at": now
            })
            await db.unified_conversations.update_one(
                {"id": conv["id"]},
                {"$set": {"status": "completed", "updated_at": now}}
            )
        
        return {"status": "resolved", "resolution": "complete"}
    
    elif resolution == "refund":
        # Refund buyer
        await db.traders.update_one(
            {"id": buyer_id},
            {"$inc": {"balance_usdt": total_with_guarantor, "balance_escrow": -total_with_guarantor}}
        )
        # Release reserved product stock
        product_id = purchase.get("product_id")
        if product_id:
            reserved_content = purchase.get("reserved_content", [])
            if reserved_content:
                await db.shop_products.update_one(
                    {"id": product_id},
                    {"$push": {"auto_content": {"$each": reserved_content}}, "$inc": {"reserved_count": -purchase.get("quantity", 1)}}
                )
            else:
                await db.shop_products.update_one(
                    {"id": product_id},
                    {"$inc": {"reserved_count": -purchase.get("quantity", 1)}}
                )
        await db.marketplace_purchases.update_one(
            {"id": purchase_id},
            {"$set": {
                "status": "refunded",
                "completed_at": now,
                "resolved_by": user["id"],
                "resolution_reason": reason
            }}
        )
        # Send system message to conversation
        conv = await db.unified_conversations.find_one(
            {"type": "marketplace_guarantor", "related_id": purchase_id},
            {"_id": 0, "id": 1}
        )
        if conv:
            await db.unified_messages.insert_one({
                "id": str(uuid.uuid4()),
                "conversation_id": conv["id"],
                "sender_id": "system",
                "sender_nickname": "Система",
                "sender_role": "system",
                "content": f"Администратор отменил сделку. Средства возвращены покупателю.\n\nПричина: {reason or 'Не указана'}",
                "is_system": True,
                "created_at": now
            })
            await db.unified_conversations.update_one(
                {"id": conv["id"]},
                {"$set": {"status": "refunded", "updated_at": now}}
            )
        
        return {"status": "resolved", "resolution": "refund"}
    
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution. Use 'complete' or 'refund'")


# ==================== GUARANTOR ORDER ACTIONS ====================

@router.post("/msg/guarantor/order/{order_id}/decision")
async def guarantor_order_decision(
    order_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Make a decision on a guarantor order"""
    deal = await db.guarantor_deals.find_one({"id": order_id}, {"_id": 0})
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    decision = data.get("decision")  # "approve", "reject", "complete", "refund"
    reason = data.get("reason", "")
    now = datetime.now(timezone.utc).isoformat()
    
    if decision == "approve":
        await db.guarantor_deals.update_one(
            {"id": order_id},
            {"$set": {"status": "approved", "approved_at": now, "approved_by": user["id"]}}
        )
    elif decision == "reject":
        await db.guarantor_deals.update_one(
            {"id": order_id},
            {"$set": {"status": "rejected", "rejected_at": now, "rejected_by": user["id"], "rejection_reason": reason}}
        )
    elif decision in ["complete", "refund"]:
        # Delegate to resolve logic
        buyer_id = deal["creator_id"] if deal.get("creator_role") == "buyer" else deal.get("counterparty_id")
        seller_id = deal.get("counterparty_id") if deal.get("creator_role") == "buyer" else deal["creator_id"]
        
        if decision == "complete":
            seller_receives = deal.get("amount", 0) - deal.get("commission", 0)
            if seller_id:
                await db.traders.update_one({"id": seller_id}, {"$inc": {"balance_usdt": seller_receives}})
            await db.guarantor_deals.update_one(
                {"id": order_id},
                {"$set": {"status": "completed", "completed_at": now, "resolved_by": user["id"], "resolution_reason": reason}}
            )
        elif decision == "refund":
            if buyer_id:
                await db.traders.update_one({"id": buyer_id}, {"$inc": {"balance_usdt": deal.get("amount", 0)}})
            await db.guarantor_deals.update_one(
                {"id": order_id},
                {"$set": {"status": "refunded", "completed_at": now, "resolved_by": user["id"], "resolution_reason": reason}}
            )
    else:
        raise HTTPException(status_code=400, detail="Неверное решение")
    
    return {"status": "ok", "decision": decision}


@router.post("/msg/guarantor/order/{order_id}/set-deadline")
async def guarantor_set_deadline(
    order_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market"]))
):
    """Set a deadline for guarantor order"""
    deal = await db.guarantor_deals.find_one({"id": order_id}, {"_id": 0})
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    deadline = data.get("deadline")
    if not deadline:
        raise HTTPException(status_code=400, detail="Укажите дедлайн")
    
    await db.guarantor_deals.update_one(
        {"id": order_id},
        {"$set": {"deadline": deadline, "deadline_set_by": user["id"], "deadline_set_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"status": "ok", "deadline": deadline}


# ==================== STAFF CHAT ROUTES ====================

@router.get("/admin/staff-chat")
async def get_staff_chat(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get staff chat messages"""
    messages = await db.staff_chat.find({}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return list(reversed(messages))


@router.post("/admin/staff-chat")
async def send_staff_message(data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Send message to staff chat"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    msg = {
        "id": str(uuid.uuid4()),
        "sender_id": user["id"],
        "sender_login": user.get("login", "Unknown"),
        "sender_role": user.get("admin_role", "admin"),
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.staff_chat.insert_one(msg)
    
    await db.admin_online.update_one(
        {"admin_id": user["id"]},
        {"$set": {
            "login": user.get("login"),
            "role": user.get("admin_role", "admin"),
            "last_seen": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    msg.pop("_id", None)
    await _ws_broadcast("staff_chat", {"type": "message", **{k: v for k, v in msg.items() if k != "_id"}})
    return {"status": "sent", "id": msg["id"]}


@router.get("/admin/staff-chat/online")
async def get_online_staff(user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get currently online staff"""
    await db.admin_online.update_one(
        {"admin_id": user["id"]},
        {"$set": {
            "login": user.get("login"),
            "role": user.get("admin_role", "admin"),
            "last_seen": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    online = await db.admin_online.find(
        {"last_seen": {"$gte": cutoff}},
        {"_id": 0, "admin_id": 0}
    ).to_list(100)
    
    return online


# ==================== ADMIN MESSAGES TO STAFF ====================

@router.get("/admin/staff-messages/{staff_id}")
async def get_staff_messages(staff_id: str, user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Get private messages between staff members"""
    my_id = user["id"]
    messages = await db.staff_private_messages.find(
        {"$or": [
            {"sender_id": my_id, "recipient_id": staff_id},
            {"sender_id": staff_id, "recipient_id": my_id}
        ]}, 
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return messages


@router.post("/admin/staff-messages/{staff_id}")
async def send_staff_private_message(staff_id: str, data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_p2p", "mod_market", "support"]))):
    """Send private message to another staff member"""
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    msg = {
        "id": str(uuid.uuid4()),
        "sender_id": user["id"],
        "sender_login": user.get("login", "Unknown"),
        "sender_role": user.get("admin_role", "admin"),
        "recipient_id": staff_id,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.staff_private_messages.insert_one(msg)
    msg.pop("_id", None)
    await _ws_broadcast(f"user_{staff_id}", {"type": "staff_message", **{k: v for k, v in msg.items() if k != "_id"}})
    return {"status": "sent"}


# ==================== USER CONVERSATIONS (msg/user/*) ====================

@router.get("/msg/user/conversations")
async def get_user_msg_conversations(user: dict = Depends(get_current_user)):
    """Get all conversations for current user (unified + private)"""
    user_id = user["id"]
    
    # Get unified conversations
    unified = await db.unified_conversations.find(
        {"$or": [
            {"participants.user_id": user_id},
            {"participants": user_id},
            {"target_user_id": user_id}
        ]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    
    # Get private conversations
    private = await db.conversations.find(
        {"$or": [
            {"participants": user_id},
            {"participant_ids": user_id}
        ]},
        {"_id": 0}
    ).sort("last_message_at", -1).to_list(50)
    
    # Enrich private conversations
    for conv in private:
        participants = conv.get("participants", conv.get("participant_ids", []))
        other_id = [p for p in participants if p != user_id][0] if len(participants) > 1 else None
        if other_id:
            other_user = await db.traders.find_one({"id": other_id}, {"_id": 0, "nickname": 1, "login": 1})
            if not other_user:
                other_user = await db.merchants.find_one({"id": other_id}, {"_id": 0, "nickname": 1, "login": 1})
            conv["other_nickname"] = other_user.get("nickname", other_user.get("login", "")) if other_user else ""
        
        unread = await db.private_messages.count_documents({
            "conversation_id": conv["id"],
            "sender_id": {"$ne": user_id},
            "read": False
        })
        conv["unread_count"] = unread
        if not conv.get("type"):
            conv["type"] = "private"
    
    # Enrich unified conversations
    for conv in unified:
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"], "is_deleted": {"$ne": True}},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        conv["last_message"] = last_msg
        conv["unread_count"] = conv.get("unread_counts", {}).get(user_id, 0)
    
    return unified + private


@router.get("/msg/user/conversations/{conv_id}/messages")
async def get_user_msg_messages(conv_id: str, user: dict = Depends(get_current_user)):
    """Get messages for a conversation (checks both unified and private)"""
    user_id = user["id"]
    
    # Try unified conversations first
    conv = await db.unified_conversations.find_one({"id": conv_id}, {"_id": 0})
    if conv:
        participants = conv.get("participants", [])
        participant_ids = []
        for p in participants:
            if isinstance(p, str):
                participant_ids.append(p)
            elif isinstance(p, dict):
                participant_ids.append(p.get("user_id", ""))
        
        if user_id not in participant_ids and not conv.get("target_user_id") == user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к чату")
        
        messages = await db.unified_messages.find(
            {"conversation_id": conv_id},
            {"_id": 0}
        ).sort("created_at", 1).to_list(500)
        
        await db.unified_conversations.update_one(
            {"id": conv_id},
            {"$set": {f"unread_counts.{user_id}": 0}}
        )
        
        return messages
    
    # Try private conversations
    conv = await db.conversations.find_one({
        "id": conv_id,
        "$or": [{"participants": user_id}, {"participant_ids": user_id}]
    }, {"_id": 0})
    
    if not conv:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    
    messages = await db.private_messages.find(
        {"conversation_id": conv_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    
    # Mark as read
    await db.private_messages.update_many(
        {"conversation_id": conv_id, "sender_id": {"$ne": user_id}, "read": False},
        {"$set": {"read": True}}
    )
    
    return messages


@router.post("/msg/user/conversations/{conv_id}/messages")
async def send_user_msg_message(conv_id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Send a message to a conversation (checks both unified and private)"""
    user_id = user["id"]
    content = data.get("content", "").strip()
    
    if not content:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    # Try unified conversations first
    conv = await db.unified_conversations.find_one({"id": conv_id}, {"_id": 0})
    if conv:
        sender_name = user.get("nickname", user.get("login", "User"))
        msg = {
            "id": str(uuid.uuid4()),
            "conversation_id": conv_id,
            "sender_id": user_id,
            "sender_role": "user",
            "sender_name": sender_name,
            "content": content,
            "attachments": data.get("attachments", []),
            "is_system": False,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.unified_messages.insert_one(msg)
        
        # Update unread counts
        all_participants = conv.get("participants", [])
        update_unread = {}
        for p in all_participants:
            p_id = p if isinstance(p, str) else p.get("user_id", "")
            if p_id and p_id != user_id:
                update_unread[f"unread_counts.{p_id}"] = 1
        
        await db.unified_conversations.update_one(
            {"id": conv_id},
            {
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat(), "last_message_at": msg["created_at"]},
                "$inc": update_unread
            }
        )
        
        msg.pop("_id", None)
        await _ws_broadcast(f"conv_{conv_id}", {"type": "message", **msg})
        
        # Also broadcast to trade channel if trade-related
        if conv.get("type") in ["p2p_trade", "p2p_dispute"] and conv.get("related_id"):
            await _ws_broadcast(f"trade_{conv['related_id']}", {"type": "message", **msg})
        
        return msg
    
    # Try private conversations
    conv = await db.conversations.find_one({
        "id": conv_id,
        "$or": [{"participants": user_id}, {"participant_ids": user_id}]
    }, {"_id": 0})
    
    if not conv:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    
    my_nickname = user.get("nickname", user.get("login", "Unknown"))
    msg_doc = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "sender_id": user_id,
        "sender_nickname": my_nickname,
        "content": content,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.private_messages.insert_one(msg_doc)
    
    await db.conversations.update_one(
        {"id": conv_id},
        {"$set": {
            "last_message": content[:100],
            "last_message_at": msg_doc["created_at"]
        }}
    )
    
    msg_doc.pop("_id", None)
    await _ws_broadcast(f"conv_{conv_id}", {"type": "message", **msg_doc})
    return msg_doc


# ==================== MERCHANT CONVERSATIONS ====================

@router.get("/msg/merchant/conversations")
async def get_merchant_conversations(user: dict = Depends(get_current_user)):
    """Get conversations for merchant"""
    user_id = user["id"]
    
    # Check if user is a merchant
    merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0, "id": 1})
    if not merchant:
        raise HTTPException(status_code=403, detail="Только для мерчантов")
    
    conversations = await db.unified_conversations.find(
        {"$or": [
            {"participants.user_id": user_id},
            {"participants": user_id},
            {"merchant_id": user_id}
        ]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    
    for conv in conversations:
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": conv["id"], "is_deleted": {"$ne": True}},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        conv["last_message"] = last_msg
        conv["unread_count"] = conv.get("unread_counts", {}).get(user_id, 0)
    
    return conversations


@router.get("/msg/merchant/conversations/{conv_id}/messages")
async def get_merchant_conv_messages(conv_id: str, user: dict = Depends(get_current_user)):
    """Get messages for a merchant conversation"""
    user_id = user["id"]
    
    conv = await db.unified_conversations.find_one({"id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    messages = await db.unified_messages.find(
        {"conversation_id": conv_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    await db.unified_conversations.update_one(
        {"id": conv_id},
        {"$set": {f"unread_counts.{user_id}": 0}}
    )
    
    return messages

@router.post("/msg/trade/{trade_id}/resolve")
async def resolve_trade_from_chat(trade_id: str, data: dict = Body(...), user: dict = Depends(require_role(["admin", "mod_p2p"]))):
    """Resolve a trade dispute from the messaging interface.
    Accepts: { decision: 'favor_buyer'|'favor_seller', reason: string }
    Delegates to the admin trade resolution logic.
    """
    decision = data.get("decision", "")
    reason = data.get("reason", "")
    
    if not decision:
        raise HTTPException(status_code=400, detail="Укажите решение (favor_buyer или favor_seller)")
    if not reason.strip():
        raise HTTPException(status_code=400, detail="Укажите причину решения")
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    if trade["status"] not in ["disputed", "dispute", "paid", "pending", "pending_payment"]:
        raise HTTPException(status_code=400, detail=f"Сделка в статусе '{trade['status']}' не может быть разрешена")
    
    # Normalize decision
    buyer_wins = decision in ["favor_buyer", "favor_client", "complete_trade", "refund_buyer"]
    seller_wins = decision in ["favor_seller", "favor_trader", "cancel", "release_seller", "cancel_dispute"]
    
    if not buyer_wins and not seller_wins:
        raise HTTPException(status_code=400, detail="Неверное решение. Используйте 'favor_buyer' или 'favor_seller'")
    
    try:
        from routes.ws_routes import ws_manager
    except ImportError:
        ws_manager = None
    
    # Handle both trade schemas: amount_usdt (new) and amount (old)
    trade_amount = trade.get("amount_usdt") or trade.get("amount", 0)
    
    if buyer_wins:
        new_status = "completed"
        
        # Buyer wins = trade completes, USDT goes to buyer
        if trade.get("buyer_id") and trade.get("buyer_type") == "trader":
            await db.traders.update_one(
                {"id": trade["buyer_id"]},
                {"$inc": {"balance_usdt": trade_amount}}
            )
        elif trade.get("merchant_id"):
            merchant_receives = trade_amount - trade.get("merchant_commission", 0)
            await db.merchants.update_one(
                {"id": trade["merchant_id"]},
                {"$inc": {"balance_usdt": merchant_receives, "total_commission_paid": trade.get("merchant_commission", 0)}}
            )
        
        if trade.get("offer_id"):
            await db.offers.update_one(
                {"id": trade["offer_id"]},
                {"$inc": {"sold_usdt": trade_amount, "actual_commission": trade.get("trader_commission", 0)}}
            )
        
        message = f"✅ Спор решён в пользу покупателя. Сделка завершена, {trade_amount} USDT зачислены покупателю.\nПричина: {reason}"
    else:
        new_status = "cancelled"
        
        # Cancel/seller wins = trade cancelled, USDT returned to offer
        if trade.get("offer_id"):
            await db.offers.update_one(
                {"id": trade["offer_id"]},
                {"$inc": {"available_usdt": trade_amount}}
            )
        else:
            await db.traders.update_one(
                {"id": trade["trader_id"]},
                {"$inc": {"balance_usdt": trade_amount}}
            )
        
        message = f"❌ Спор отменён. Сделка отменена, {trade_amount} USDT возвращены в объявление продавца.\nПричина: {reason}"
    
    # Update trade
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": new_status,
            "dispute_resolved_at": datetime.now(timezone.utc).isoformat(),
            "dispute_resolved_by": user["id"],
            "dispute_resolution": decision,
            "resolution_reason": reason
        }}
    )
    
    # System message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Archive conversation
    await db.unified_conversations.update_one(
        {"$or": [
            {"related_id": trade_id, "type": "p2p_dispute"},
            {"related_id": trade_id, "type": "p2p_trade"}
        ]},
        {"$set": {
            "resolved": True,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolved_by": user["id"],
            "status": "resolved",
            "archived": True
        }}
    )
    
    # WebSocket broadcast
    if ws_manager:
        msg_data = {k: v for k, v in system_msg.items() if k != "_id"}
        await ws_manager.broadcast(f"trade_{trade_id}", {"type": "message", **msg_data})
        await ws_manager.broadcast(f"trade_{trade_id}", {"type": "status_update", "status": new_status, "trade_id": trade_id})
        # Also broadcast to conversation channel
        conv = await db.unified_conversations.find_one(
            {"$or": [{"related_id": trade_id, "type": "p2p_dispute"}, {"related_id": trade_id, "type": "p2p_trade"}]},
            {"_id": 0, "id": 1}
        )
        if conv:
            await ws_manager.broadcast(f"conv_{conv['id']}", {"type": "message", **msg_data})
            await ws_manager.broadcast(f"conv_{conv['id']}", {"type": "status_update", "status": "resolved"})
        # Notify users
        if trade.get("trader_id"):
            await ws_manager.broadcast(f"user_{trade['trader_id']}", {"type": "trade_resolved", "trade_id": trade_id, "status": new_status})
        if trade.get("buyer_id"):
            await ws_manager.broadcast(f"user_{trade['buyer_id']}", {"type": "trade_resolved", "trade_id": trade_id, "status": new_status})
    
    return {"status": new_status, "message": message}
