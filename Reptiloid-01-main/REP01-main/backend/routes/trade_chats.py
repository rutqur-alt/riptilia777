"""
Trade Chats Routes - Migrated from server.py
Handles P2P trade chats, marketplace order chats, support tickets, and dispute management
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone, timedelta
import uuid

from core.auth import require_role, get_current_user, log_admin_action
from server import db

router = APIRouter(tags=["trade_chats"])


# ==================== P2P TRADE CHAT ====================

@router.post("/msg/trade/{trade_id}/init")
async def init_trade_conversation(trade_id: str, user: dict = Depends(get_current_user)):
    """Initialize conversation for P2P trade (called when trade starts)"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    existing = await db.unified_conversations.find_one({"type": {"$in": ["p2p_trade", "p2p_merchant"]}, "related_id": trade_id})
    if existing:
        return {"conversation_id": existing["id"], "exists": True}
    
    is_merchant_trade = trade.get("merchant_id") is not None
    conv_type = "p2p_merchant" if is_merchant_trade else "p2p_trade"
    
    participants = []
    unread = {}
    
    # Seller (trader)
    seller = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0, "nickname": 1, "login": 1})
    seller_name = seller.get("nickname", seller.get("login", "Продавец")) if seller else "Продавец"
    participants.append({"user_id": trade["trader_id"], "role": "p2p_seller", "name": seller_name})
    unread[trade["trader_id"]] = 0
    
    if is_merchant_trade:
        merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0, "company_name": 1, "login": 1})
        merchant_name = merchant.get("company_name", merchant.get("login", "Мерчант")) if merchant else "Мерчант"
        participants.append({"user_id": trade["merchant_id"], "role": "merchant", "name": merchant_name})
        unread[trade["merchant_id"]] = 0
    else:
        buyer_id = trade.get("buyer_id") or trade.get("client_id")
        if buyer_id:
            buyer = await db.traders.find_one({"id": buyer_id}, {"_id": 0, "nickname": 1, "login": 1})
            buyer_name = buyer.get("nickname", buyer.get("login", "Покупатель")) if buyer else "Покупатель"
            participants.append({"user_id": buyer_id, "role": "buyer", "name": buyer_name})
            unread[buyer_id] = 0
    
    conv = {
        "id": str(uuid.uuid4()),
        "type": conv_type,
        "status": "active",
        "related_id": trade_id,
        "title": f"Сделка #{trade_id[:8]}",
        "delete_locked": False,
        "participants": participants,
        "unread_counts": unread,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.unified_conversations.insert_one(conv)
    
    # Build system message with requisites
    req_text = ""
    requisites = trade.get("requisites", [])
    if not requisites and trade.get("requisite"):
        requisites = [trade["requisite"]]
    
    for req in requisites:
        if req.get("type") == "card":
            req_text += f"\n💳 {req.get('data', {}).get('bank_name', 'Карта')}: {req.get('data', {}).get('card_number', '')}"
            if req.get('data', {}).get('card_holder') or req.get('data', {}).get('holder_name'):
                holder = req.get('data', {}).get('card_holder') or req.get('data', {}).get('holder_name')
                req_text += f"\n   Получатель: {holder}"
        elif req.get("type") == "sbp":
            req_text += f"\n⚡ СБП {req.get('data', {}).get('bank_name', '')}: {req.get('data', {}).get('phone', '')}"
        elif req.get("type") == "sim":
            req_text += f"\n📞 {req.get('data', {}).get('operator', 'SIM')}: {req.get('data', {}).get('phone', '')}"
    
    msg_content = f"📋 Сделка #{trade_id[:8]} создана\n\n"
    msg_content += f"💰 Сумма: {trade.get('amount_usdt', 0)} USDT\n"
    msg_content += f"💵 К оплате: {trade.get('amount_rub', 0):,.0f} ₽\n"
    msg_content += f"📈 Курс: {trade.get('price_rub', 0)} ₽/USDT\n"
    msg_content += "⏱ Время на оплату: 30 минут\n"
    
    if req_text:
        msg_content += f"\n🏦 Реквизиты для оплаты:{req_text}"
    
    sys_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": "system",
        "sender_role": "system",
        "sender_name": "Система",
        "content": msg_content,
        "is_system": True,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(sys_msg)
    
    return {"conversation_id": conv["id"], "exists": False}


@router.post("/msg/trade/{trade_id}/dispute")
async def open_trade_dispute(trade_id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Open dispute on P2P trade - adds moderator to existing chat"""
    reason = data.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Укажите причину спора")
    
    user_id = user["id"]
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    valid_participants = [trade.get("trader_id"), trade.get("buyer_id"), trade.get("merchant_id")]
    valid_participants = [p for p in valid_participants if p]
    
    if user_id not in valid_participants and user.get("admin_role") is None:
        raise HTTPException(status_code=403, detail="Вы не участник сделки")
    
    conv = await db.unified_conversations.find_one(
        {"type": {"$in": ["p2p_trade", "p2p_merchant"]}, "related_id": trade_id},
        {"_id": 0}
    )
    if not conv:
        await init_trade_conversation(trade_id, user)
        conv = await db.unified_conversations.find_one(
            {"type": {"$in": ["p2p_trade", "p2p_merchant"]}, "related_id": trade_id},
            {"_id": 0}
        )
    
    if conv.get("status") == "dispute":
        raise HTTPException(status_code=400, detail="Спор уже открыт")
    
    moderator = await db.admins.find_one({"admin_role": "mod_p2p", "is_active": True}, {"_id": 0})
    if not moderator:
        moderator = await db.admins.find_one({"admin_role": {"$in": ["admin", "owner"]}}, {"_id": 0})
    
    if not moderator:
        raise HTTPException(status_code=500, detail="Нет доступных модераторов")
    
    mod_id = moderator["id"]
    mod_name = moderator.get("login", "Модератор")
    
    participants = conv.get("participants", [])
    participants.append({"user_id": mod_id, "role": "mod_p2p", "name": mod_name, "joined_at": datetime.now(timezone.utc).isoformat()})
    
    unread_counts = conv.get("unread_counts", {})
    unread_counts[mod_id] = 0
    
    await db.unified_conversations.update_one(
        {"id": conv["id"]},
        {"$set": {
            "status": "dispute",
            "delete_locked": True,
            "participants": participants,
            "unread_counts": unread_counts,
            "dispute_reason": reason,
            "dispute_opened_by": user_id,
            "dispute_opened_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "disputed",
            "has_dispute": True,
            "dispute_reason": reason,
            "disputed_at": datetime.now(timezone.utc).isoformat(),
            "disputed_by": user_id
        }}
    )
    
    msgs = [
        {
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_role": "system",
            "sender_name": "Система",
            "content": f"⚠️ Открыт спор: {reason}",
            "is_system": True,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_role": "system",
            "sender_name": "Система",
            "content": "⚠️ Модератор P2P подключен к чату",
            "is_system": True,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    ]
    await db.unified_messages.insert_many(msgs)
    
    return {"status": "dispute_opened", "moderator": mod_name, "conversation_id": conv["id"]}


@router.post("/msg/trade/{trade_id}/resolve")
async def resolve_trade_dispute_v2(
    trade_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "mod_p2p"]))
):
    """Resolve P2P dispute"""
    decision = data.get("decision")
    reason = data.get("reason", "")
    
    if decision not in ["refund_buyer", "cancel_dispute"]:
        raise HTTPException(status_code=400, detail="Неверное решение. Допустимо: refund_buyer, cancel_dispute")
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    conv = await db.unified_conversations.find_one({"type": "p2p_dispute", "related_id": trade_id}, {"_id": 0})
    if not conv:
        conv = await db.unified_conversations.find_one({"type": "p2p_trade", "related_id": trade_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    decision_text = {
        "refund_buyer": "В пользу покупателя",
        "cancel_dispute": "Спор отменён"
    }[decision]
    
    await db.unified_conversations.update_one(
        {"id": conv["id"]},
        {"$set": {
            "status": "archived",
            "resolved_by": user["id"],
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolution": decision,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    new_status = "refunded" if decision == "refund_buyer" else "cancelled"
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": new_status,
            "dispute_resolved": True,
            "dispute_resolution": decision,
            "dispute_resolved_at": datetime.now(timezone.utc).isoformat(),
            "dispute_resolved_by": user["id"]
        }}
    )
    
    sys_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": "system",
        "sender_role": "system",
        "sender_name": "Система",
        "content": f"✅ РЕШЕНИЕ МОДЕРАТОРА: {decision_text}. {reason}".strip(),
        "is_system": True,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(sys_msg)
    
    decision_record = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "related_id": trade_id,
        "decision_type": decision,
        "decided_by": user["id"],
        "decided_by_role": user.get("admin_role", "admin"),
        "decided_by_name": user.get("nickname", user.get("login", "Модератор")),
        "amount": trade.get("amount_usdt", 0),
        "currency": "USDT",
        "reason": reason,
        "status": "executed",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.decisions.insert_one(decision_record)
    
    await log_admin_action(user["id"], f"resolve_dispute_{decision}", "trade", trade_id, {
        "decision": decision,
        "amount": trade.get("amount_usdt", 0),
        "reason": reason
    })
    
    return {"status": "resolved", "decision": decision, "decision_id": decision_record["id"]}


# ==================== ADMIN REVERT DECISION ====================

@router.post("/admin/revert-decision/{decision_id}")
async def revert_decision(
    decision_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Revert a moderator decision (admin only)"""
    reason = data.get("reason", "")
    
    decision = await db.decisions.find_one({"id": decision_id}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Решение не найдено")
    
    if decision.get("status") == "reverted":
        raise HTTPException(status_code=400, detail="Решение уже отменено")
    
    conv = await db.unified_conversations.find_one({"id": decision.get("conversation_id")}, {"_id": 0})
    
    await db.decisions.update_one(
        {"id": decision_id},
        {"$set": {
            "status": "reverted",
            "reverted_by": user["id"],
            "reverted_at": datetime.now(timezone.utc).isoformat(),
            "revert_reason": reason
        }}
    )
    
    if conv:
        await db.unified_conversations.update_one(
            {"id": conv["id"]},
            {"$set": {
                "status": "dispute",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        sys_msg = {
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_role": "system",
            "sender_name": "Система",
            "content": f"⚠️ РЕШЕНИЕ ОТМЕНЕНО АДМИНИСТРАТОРОМ: {reason}. Спор возобновлён.",
            "is_system": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.unified_messages.insert_one(sys_msg)
    
    if decision.get("related_id"):
        await db.trades.update_one(
            {"id": decision["related_id"]},
            {"$set": {
                "status": "disputed",
                "dispute_resolved": False,
                "dispute_resolution": None
            }}
        )
    
    await log_admin_action(user["id"], "revert_decision", "decision", decision_id, {
        "original_decision": decision.get("decision_type"),
        "reason": reason
    })
    
    return {"status": "reverted", "message": "Решение отменено"}


@router.get("/admin/decisions")
async def get_all_decisions(
    skip: int = 0,
    limit: int = 50,
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market"]))
):
    """Get all decisions with optional filtering"""
    decisions = await db.decisions.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return decisions


@router.get("/admin/decisions/{decision_id}")
async def get_decision_details(
    decision_id: str,
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market"]))
):
    """Get details of a specific decision"""
    decision = await db.decisions.find_one({"id": decision_id}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Решение не найдено")
    
    conv = await db.unified_conversations.find_one({"id": decision.get("conversation_id")}, {"_id": 0})
    mod = await db.admins.find_one({"id": decision.get("decided_by")}, {"_id": 0, "password": 0})
    
    return {
        **decision,
        "conversation": conv,
        "moderator": mod
    }


# ==================== CHAT BLOCK ====================

@router.post("/admin/users/{user_id}/block-chat")
async def block_user_chat(
    user_id: str,
    data: dict = Body(...),
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market"]))
):
    """Block a user from chatting"""
    duration_hours = data.get("duration_hours", 24)
    reason = data.get("reason", "")
    
    target_user = await db.traders.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    block_until = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
    
    await db.traders.update_one(
        {"id": user_id},
        {"$set": {
            "chat_blocked": True,
            "chat_blocked_until": block_until.isoformat(),
            "chat_blocked_reason": reason,
            "chat_blocked_by": user["id"]
        }}
    )
    
    await log_admin_action(user["id"], "block_chat", "user", user_id, {
        "duration_hours": duration_hours,
        "reason": reason
    })
    
    return {"status": "blocked", "blocked_until": block_until.isoformat()}


@router.post("/admin/users/{user_id}/unblock-chat")
async def unblock_user_chat(
    user_id: str,
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market"]))
):
    """Unblock a user from chatting"""
    await db.traders.update_one(
        {"id": user_id},
        {"$set": {
            "chat_blocked": False,
            "chat_blocked_until": None,
            "chat_blocked_reason": None,
            "chat_blocked_by": None
        }}
    )
    
    await log_admin_action(user["id"], "unblock_chat", "user", user_id, {})
    
    return {"status": "unblocked"}


# ==================== MARKETPLACE ORDER CHAT ====================

@router.post("/msg/order/{order_id}/init")
async def init_marketplace_conversation(order_id: str, user: dict = Depends(get_current_user)):
    """Initialize conversation for Marketplace order (with guarantor from start)"""
    order = await db.marketplace_purchases.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    existing = await db.unified_conversations.find_one({"type": "marketplace", "related_id": order_id})
    if existing:
        return {"conversation_id": existing["id"], "exists": True}
    
    buyer = await db.traders.find_one({"id": order["buyer_id"]}, {"_id": 0})
    seller = await db.traders.find_one({"id": order["seller_id"]}, {"_id": 0})
    
    guarantor = await db.admins.find_one({"admin_role": "mod_market", "is_active": True}, {"_id": 0})
    if not guarantor:
        guarantor = await db.admins.find_one({"admin_role": {"$in": ["admin", "owner"]}}, {"_id": 0})
    
    participants = [
        {"user_id": order["buyer_id"], "role": "buyer", "name": buyer.get("nickname", "Покупатель") if buyer else "Покупатель"},
        {"user_id": order["seller_id"], "role": "shop_owner", "name": seller.get("shop_settings", {}).get("shop_name", "Магазин") if seller else "Магазин"}
    ]
    unread = {order["buyer_id"]: 0, order["seller_id"]: 0}
    
    if guarantor:
        participants.append({"user_id": guarantor["id"], "role": "mod_market", "name": guarantor.get("login", "Гарант")})
        unread[guarantor["id"]] = 0
    
    conv = {
        "id": str(uuid.uuid4()),
        "type": "marketplace",
        "status": "active",
        "related_id": order_id,
        "title": f"Заказ #{order_id[:8]}",
        "delete_locked": True,
        "participants": participants,
        "unread_counts": unread,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.unified_conversations.insert_one(conv)
    
    msgs = [
        {
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_role": "system",
            "sender_name": "Система",
            "content": f"✅ Заказ создан. Сумма: {order.get('total_price', 0)} ₽",
            "is_system": True,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_role": "system",
            "sender_name": "Система",
            "content": "✅ Гарант подключен к сделке",
            "is_system": True,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "conversation_id": conv["id"],
            "sender_id": "system",
            "sender_role": "system",
            "sender_name": "Система",
            "content": "⚠️ Внимание! В сделках Marketplace удаление сообщений запрещено",
            "is_system": True,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    ]
    await db.unified_messages.insert_many(msgs)
    
    return {"conversation_id": conv["id"], "exists": False}


# ==================== SUPPORT TICKETS ====================

@router.post("/msg/support/create")
async def create_support_ticket_conv(data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Create new support ticket conversation"""
    category = data.get("category", "other")
    subject = data.get("subject", "Обращение в поддержку")
    message = data.get("message", "").strip()
    related_id = data.get("related_id")
    
    if not message:
        raise HTTPException(status_code=400, detail="Опишите проблему")
    
    user_id = user["id"]
    user_name = user.get("nickname", user.get("login", "Пользователь"))
    
    support = await db.admins.find_one({"admin_role": "support", "is_active": True}, {"_id": 0})
    if not support:
        support = await db.admins.find_one({"admin_role": {"$in": ["admin", "owner"]}}, {"_id": 0})
    
    participants = [{"user_id": user_id, "role": "user", "name": user_name}]
    unread = {user_id: 0}
    
    if support:
        participants.append({"user_id": support["id"], "role": "support", "name": support.get("login", "Поддержка")})
        unread[support["id"]] = 1
    
    conv = {
        "id": str(uuid.uuid4()),
        "type": "support_ticket",
        "status": "active",
        "related_id": related_id,
        "title": subject,
        "category": category,
        "delete_locked": False,
        "participants": participants,
        "unread_counts": unread,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.unified_conversations.insert_one(conv)
    
    first_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv["id"],
        "sender_id": user_id,
        "sender_role": "user",
        "sender_name": user_name,
        "content": message,
        "is_system": False,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.unified_messages.insert_one(first_msg)
    
    return {"conversation_id": conv["id"], "ticket_id": conv["id"]}


@router.get("/msg/support/my-tickets")
async def get_my_support_tickets(user: dict = Depends(get_current_user)):
    """Get current user's support tickets"""
    tickets = await db.unified_conversations.find(
        {"type": "support_ticket", "participants.user_id": user["id"]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    
    for t in tickets:
        last_msg = await db.unified_messages.find_one(
            {"conversation_id": t["id"]},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        t["last_message"] = last_msg
        t["unread_count"] = t.get("unread_counts", {}).get(user["id"], 0)
    
    return tickets
