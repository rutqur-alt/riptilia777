"""
Admin Management Routes - Migrated from server.py
Handles admin users/traders/merchants, staff management, trades, forum moderation, settings
"""
from fastapi import Body, APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from starlette.responses import Response
import json as _json
from datetime import datetime, timezone, timedelta
import uuid
from bson import ObjectId

from core.auth import require_admin_level, log_admin_action, hash_password
from core.database import db, ADMIN_ROLES, ROLE_PERMISSIONS

router = APIRouter(tags=["admin_management"])


# ==================== ADMIN: USERS/TRADERS ====================


def _clean_doc(doc):
    """Recursively clean MongoDB documents for JSON serialization"""
    if doc is None:
        return None
    if isinstance(doc, dict):
        result = {}
        for k, v in doc.items():
            if k == "_id":
                continue
            result[k] = _clean_doc(v)
        return result
    elif isinstance(doc, list):
        return [_clean_doc(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif hasattr(doc, 'isoformat'):
        return doc.isoformat()
    else:
        return doc

@router.get("/admin/users/traders")
async def get_all_traders_admin(
    skip: int = 0, 
    limit: int = 50,
    search: str = None,
    status: str = None,
    user: dict = Depends(require_admin_level(30))
):
    """Get all traders with admin info"""
    query = {}
    if search:
        query["$or"] = [
            {"login": {"$regex": search, "$options": "i"}},
            {"nickname": {"$regex": search, "$options": "i"}}
        ]
    if status == "blocked":
        query["is_blocked"] = True
    elif status == "active":
        query["is_blocked"] = {"$ne": True}
    
    traders = await db.traders.find(query, {"_id": 0, "password_hash": 0, "password": 0}).skip(skip).limit(limit).to_list(limit)
    total = await db.traders.count_documents(query)
    
    return {"traders": traders, "total": total}


@router.get("/admin/users/traders/{trader_id}")
async def get_trader_details_admin(trader_id: str, user: dict = Depends(require_admin_level(30))):
    """Get detailed trader info including history"""
    trader = await db.traders.find_one({"id": trader_id}, {"_id": 0, "password_hash": 0, "password": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    
    # Get recent trades
    trades = await db.trades.find(
        {"$or": [{"trader_id": trader_id}, {"buyer_id": trader_id}]},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Get offers
    offers = await db.offers.find({"trader_id": trader_id}, {"_id": 0}).to_list(100)
    
    # Get requisites
    requisites = await db.requisites.find({"trader_id": trader_id}, {"_id": 0}).to_list(50)
    
    return {
        "trader": trader,
        "trades": trades,
        "offers": offers,
        "requisites": requisites
    }


@router.post("/admin/users/traders/{trader_id}/block")
async def block_trader(trader_id: str, data: dict, user: dict = Depends(require_admin_level(50))):
    """Block/unblock a trader"""
    block = data.get("block", True)
    reason = data.get("reason", "")
    
    await db.traders.update_one(
        {"id": trader_id},
        {"$set": {"is_blocked": block, "block_reason": reason, "blocked_at": datetime.now(timezone.utc).isoformat() if block else None, "blocked_by": user["id"] if block else None}}
    )
    
    await log_admin_action(user["id"], "block_trader" if block else "unblock_trader", "trader", trader_id, {"reason": reason})
    
    return {"status": "success", "blocked": block}


@router.post("/admin/users/traders/{trader_id}/edit")
async def edit_trader_admin(trader_id: str, data: dict, user: dict = Depends(require_admin_level(80))):
    """Edit trader data"""
    allowed_fields = ["balance_usdt", "commission_rate", "nickname", "display_name"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    await db.traders.update_one({"id": trader_id}, {"$set": update_data})
    
    await log_admin_action(user["id"], "edit_trader", "trader", trader_id, update_data)
    
    return {"status": "success"}


# ==================== ADMIN: USERS/MERCHANTS ====================

@router.get("/admin/users/merchants")
async def get_all_merchants_admin(
    skip: int = 0,
    limit: int = 50,
    search: str = None,
    status: str = None,
    user: dict = Depends(require_admin_level(30))
):
    """Get all merchants with admin info"""
    query = {}
    if search:
        query["$or"] = [
            {"login": {"$regex": search, "$options": "i"}},
            {"merchant_name": {"$regex": search, "$options": "i"}}
        ]
    if status:
        query["status"] = status
    
    merchants = await db.merchants.find(query, {"_id": 0, "password_hash": 0, "password": 0}).skip(skip).limit(limit).to_list(limit)
    total = await db.merchants.count_documents(query)
    
    return {"merchants": merchants, "total": total}


@router.post("/admin/users/merchants/{merchant_id}/edit")
async def edit_merchant_admin(merchant_id: str, data: dict, user: dict = Depends(require_admin_level(80))):
    """Edit merchant data"""
    allowed_fields = ["balance_usdt", "commission_rate", "merchant_name", "status"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    await db.merchants.update_one({"id": merchant_id}, {"$set": update_data})
    
    await log_admin_action(user["id"], "edit_merchant", "merchant", merchant_id, update_data)
    
    return {"status": "success"}


# ==================== ADMIN: STAFF MANAGEMENT ====================

@router.get("/admin/staff")
async def get_staff_list(user: dict = Depends(require_admin_level(80))):
    """Get all staff members"""
    staff = await db.admins.find({}, {"_id": 0, "password_hash": 0, "password": 0}).to_list(100)
    return staff


@router.post("/admin/staff/create")
async def create_staff_member(data: dict, user: dict = Depends(require_admin_level(100))):
    """Create new staff member (owner only)"""
    login = data.get("login")
    password = data.get("password")
    admin_role = data.get("role", "support")  # owner, admin, mod_p2p, mod_market, support
    nickname = data.get("nickname", login)
    
    if not login or not password:
        raise HTTPException(status_code=400, detail="Login and password required")
    
    if admin_role not in ADMIN_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {list(ADMIN_ROLES.keys())}")
    
    # Check if creating owner/admin requires owner role
    if admin_role in ["owner", "admin"] and ADMIN_ROLES.get(user.get("admin_role", "admin"), 0) < 100:
        raise HTTPException(status_code=403, detail="Only owner can create admins")
    
    existing = await db.admins.find_one({"login": login})
    if existing:
        raise HTTPException(status_code=400, detail="Login already exists")
    
    staff_doc = {
        "id": str(uuid.uuid4()),
        "login": login,
        "nickname": nickname,
        "password_hash": hash_password(password),
        "role": "admin",  # For auth system
        "admin_role": admin_role,  # Specific admin role
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True
    }
    
    await db.admins.insert_one(staff_doc)
    
    await log_admin_action(user["id"], "create_staff", "admin", staff_doc["id"], {"login": login, "role": admin_role})
    
    return {"status": "success", "id": staff_doc["id"]}


@router.delete("/admin/staff/{staff_id}")
async def delete_staff_member(staff_id: str, user: dict = Depends(require_admin_level(100))):
    """Delete staff member (owner only)"""
    staff = await db.admins.find_one({"id": staff_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    if staff.get("admin_role") == "owner":
        raise HTTPException(status_code=403, detail="Cannot delete owner")
    
    await db.admins.delete_one({"id": staff_id})
    
    await log_admin_action(user["id"], "delete_staff", "admin", staff_id, {"login": staff.get("login")})
    
    return {"status": "deleted"}


@router.put("/admin/staff/{staff_id}/permissions")
async def update_staff_permissions(staff_id: str, data: dict, user: dict = Depends(require_admin_level(80))):
    """Update staff member's custom permissions"""
    staff = await db.admins.find_one({"id": staff_id})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    if staff.get("admin_role") == "owner":
        raise HTTPException(status_code=403, detail="Cannot modify owner permissions")
    
    custom_permissions = data.get("permissions", [])
    
    await db.admins.update_one(
        {"id": staff_id},
        {"$set": {"custom_permissions": custom_permissions}}
    )
    
    await log_admin_action(user["id"], "update_staff_permissions", "admin", staff_id, {"permissions": custom_permissions})
    
    return {"status": "updated", "permissions": custom_permissions}


@router.get("/admin/staff/{staff_id}")
async def get_staff_member(staff_id: str, user: dict = Depends(require_admin_level(50))):
    """Get single staff member details"""
    staff = await db.admins.find_one({"id": staff_id}, {"_id": 0, "password_hash": 0, "password": 0})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Add default permissions based on role
    role = staff.get("admin_role", "support")
    staff["role_permissions"] = ROLE_PERMISSIONS.get(role, [])
    staff["custom_permissions"] = staff.get("custom_permissions", [])
    
    return staff


@router.get("/admin/permissions/list")
async def get_all_permissions(user: dict = Depends(require_admin_level(50))):
    """Get list of all available permissions"""
    return {
        "permissions": [
            {"key": "view_users", "label": "Просмотр пользователей", "category": "users"},
            {"key": "view_user_stats", "label": "Статистика пользователей", "category": "users"},
            {"key": "block_users", "label": "Блокировка пользователей", "category": "users"},
            {"key": "view_p2p_trades", "label": "Просмотр P2P сделок", "category": "p2p"},
            {"key": "view_p2p_offers", "label": "Просмотр объявлений", "category": "p2p"},
            {"key": "resolve_p2p_disputes", "label": "Решение споров P2P", "category": "p2p"},
            {"key": "view_shops", "label": "Просмотр магазинов", "category": "market"},
            {"key": "block_shops", "label": "Блокировка магазинов", "category": "market"},
            {"key": "approve_shops", "label": "Одобрение магазинов", "category": "market"},
            {"key": "view_products", "label": "Просмотр товаров", "category": "market"},
            {"key": "act_as_guarantor", "label": "Гарант сделок", "category": "market"},
            {"key": "view_messages", "label": "Просмотр сообщений", "category": "support"},
            {"key": "send_messages", "label": "Отправка сообщений", "category": "support"},
            {"key": "view_tickets", "label": "Просмотр тикетов", "category": "support"},
            {"key": "answer_tickets", "label": "Ответы на тикеты", "category": "support"},
            {"key": "escalate_to_moderator", "label": "Эскалация модератору", "category": "support"},
            {"key": "escalate_to_admin", "label": "Эскалация админу", "category": "support"},
        ],
        "role_defaults": ROLE_PERMISSIONS
    }


# ==================== ADMIN: TRADES ====================

@router.get("/admin/trades")
async def get_all_trades_admin(
    skip: int = 0,
    limit: int = 50,
    status: str = None,
    user: dict = Depends(require_admin_level(30))
):
    """Get all trades"""
    import logging
    logger = logging.getLogger("admin_trades")
    logger.warning("=== ADMIN TRADES ENDPOINT CALLED ===")
    try:
        query = {}
        if status:
            query["status"] = status
        
        trades = await db.trades.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        total = await db.trades.count_documents(query)
        logger.warning(f"Found {len(trades)} trades, total={total}")
        
        cleaned = []
        for t in trades:
            ct = {}
            for k, v in t.items():
                if k == "_id":
                    continue
                ct[k] = _clean_doc(v)
            cleaned.append(ct)
        
        body_str = _json.dumps({"trades": cleaned, "total": total}, default=str, ensure_ascii=False)
        result = _json.loads(body_str)
        logger.warning(f"Returning JSONResponse with {len(result['trades'])} trades")
        resp = JSONResponse(content=result)
        logger.warning(f"Response type: {type(resp)}, isinstance Response: {isinstance(resp, Response)}")
        return resp
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e), "trades": [], "total": 0}, status_code=500)


@router.get("/admin/trades/{trade_id}")
async def get_trade_details_admin(trade_id: str, user: dict = Depends(require_admin_level(30))):
    """Get detailed trade info including chat"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Get chat messages
    messages = await db.trade_messages.find({"trade_id": trade_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    
    # Get trader and buyer info
    trader = await db.traders.find_one({"id": trade.get("trader_id")}, {"_id": 0, "password_hash": 0, "password": 0, "login": 1, "nickname": 1})
    buyer = await db.traders.find_one({"id": trade.get("buyer_id")}, {"_id": 0, "password_hash": 0, "password": 0, "login": 1, "nickname": 1}) if trade.get("buyer_id") else None
    
    return Response(content=_json.dumps({
        "trade": _clean_doc(trade),
        "messages": [_clean_doc(m) for m in messages],
        "trader": _clean_doc(trader) if trader else None,
        "buyer": _clean_doc(buyer) if buyer else None
    }, default=str), media_type="application/json")


@router.post("/admin/trades/{trade_id}/resolve")
async def resolve_trade_dispute(trade_id: str, data: dict = Body(...), user: dict = Depends(require_admin_level(50))):
    """Resolve a disputed trade
    decision: 'favor_buyer' or 'favor_seller'
    reason: text explanation
    """
    decision = data.get("decision", data.get("resolution", ""))
    reason = data.get("reason", "")
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade["status"] not in ["disputed", "dispute", "paid", "pending", "pending_payment"]:
        raise HTTPException(status_code=400, detail=f"Cannot resolve trade in status: {trade['status']}")
    
    # Normalize decision values
    # favor_buyer / favor_client / refund_buyer / complete_trade -> two outcomes
    buyer_wins = decision in ["favor_buyer", "favor_client", "complete_trade", "refund_buyer"]
    seller_wins = decision in ["favor_seller", "favor_trader", "cancel", "release_seller"]
    
    if not buyer_wins and not seller_wins:
        raise HTTPException(status_code=400, detail="Invalid decision. Use 'favor_buyer' or 'favor_seller'")
    
    try:
        from routes.ws_routes import ws_manager
    except ImportError:
        ws_manager = None
    
    # Handle both trade schemas: amount_usdt (new) and amount (old)
    trade_amount = trade.get("amount_usdt") or trade.get("amount", 0)
    
    if buyer_wins:
        # BUYER WINS: Complete the trade, credit USDT to buyer
        new_status = "completed"
        
        # Credit USDT to buyer
        if trade.get("buyer_id") and trade.get("buyer_type") == "trader":
            await db.traders.update_one(
                {"id": trade["buyer_id"]},
                {"$inc": {"balance_usdt": trade_amount}}
            )
            message = f"✅ Спор решён в пользу покупателя. Сделка завершена, {trade_amount} USDT зачислены покупателю."
        elif trade.get("merchant_id"):
            # Get merchant's commission rate (set by admin on approval)
            merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0})
            commission_rate = merchant.get("commission_rate", 10.0) if merchant else 10.0
            
            # Get original amount from invoice (what merchant requested, NOT what client paid)
            original_amount_rub = None
            if trade.get("invoice_id"):
                invoice = await db.merchant_invoices.find_one({"id": trade["invoice_id"]}, {"_id": 0})
                if invoice:
                    original_amount_rub = invoice.get("original_amount_rub")
            
            # Fallback to trade amounts if no invoice found
            if not original_amount_rub:
                original_amount_rub = trade.get("client_amount_rub") or trade.get("amount_rub", 0)
            
            # Get base exchange rate
            payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
            base_rate = payout_settings.get("base_rate", 78.5) if payout_settings else 78.5
            
            # Merchant receives: original_amount - commission%
            # Commission is calculated from ORIGINAL order amount, not what client paid
            merchant_receives_rub = original_amount_rub * (100 - commission_rate) / 100
            platform_fee_rub = original_amount_rub * commission_rate / 100
            merchant_receives_usdt = merchant_receives_rub / base_rate
            commission_usdt = platform_fee_rub / base_rate
            
            # Update trade with calculated amounts
            await db.trades.update_one(
                {"id": trade_id},
                {"$set": {
                    "original_amount_rub": original_amount_rub,
                    "merchant_commission_percent": commission_rate,
                    "platform_fee_rub": platform_fee_rub,
                    "merchant_receives_rub": merchant_receives_rub,
                    "merchant_receives_usdt": merchant_receives_usdt,
                    "merchant_commission": commission_usdt
                }}
            )
            
            # Credit merchant balance
            await db.merchants.update_one(
                {"id": trade["merchant_id"]},
                {"$inc": {
                    "balance_usdt": merchant_receives_usdt,
                    "total_commission_paid": commission_usdt
                }}
            )
            
            # Update invoice status to completed
            if trade.get("invoice_id"):
                await db.merchant_invoices.update_one(
                    {"id": trade["invoice_id"]},
                    {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
                )
            
            message = f"✅ Спор решён в пользу клиента. Мерчант получил {merchant_receives_rub:.0f} RUB ({merchant_receives_usdt:.2f} USDT)."
        else:
            message = f"✅ Спор решён в пользу покупателя. Сделка завершена."
        
        if reason:
            message += f"\nПричина: {reason}"
        
        # Update offer sold_usdt
        if trade.get("offer_id"):
            await db.offers.update_one(
                {"id": trade["offer_id"]},
                {"$inc": {
                    "sold_usdt": trade_amount,
                    "actual_commission": trade.get("trader_commission", 0)
                }}
            )
    
    else:
        # SELLER WINS: Cancel the trade, return USDT to seller's offer or balance
        new_status = "cancelled"
        
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
        
        message = f"❌ Спор решён в пользу продавца. Сделка отменена, {trade_amount} USDT возвращены продавцу."
        if reason:
            message += f"\nПричина: {reason}"
    
    # Update trade status
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
    
    # Send system message to trade chat
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Auto-archive the unified conversation
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
        msg_broadcast = {k: v for k, v in system_msg.items() if k != "_id"}
        await ws_manager.broadcast(f"trade_{trade_id}", {"type": "message", **msg_broadcast})
        await ws_manager.broadcast(f"trade_{trade_id}", {"type": "status_update", "status": new_status, "trade_id": trade_id})
        # Notify trader
        if trade.get("trader_id"):
            await ws_manager.broadcast(f"user_{trade['trader_id']}", {"type": "trade_resolved", "trade_id": trade_id, "status": new_status})
        if trade.get("buyer_id"):
            await ws_manager.broadcast(f"user_{trade['buyer_id']}", {"type": "trade_resolved", "trade_id": trade_id, "status": new_status})
    
    await log_admin_action(user["id"], "resolve_dispute", "trade", trade_id, {"resolution": decision, "reason": reason, "new_status": new_status})
    
    return {"status": new_status, "message": message}


@router.delete("/admin/trades/{trade_id}")
async def delete_trade(trade_id: str, user: dict = Depends(require_admin_level(80))):
    """Delete a trade (admin only)"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    # Delete the trade
    await db.trades.delete_one({"id": trade_id})
    
    # Also delete related messages
    await db.trade_messages.delete_many({"trade_id": trade_id})
    
    await log_admin_action(user["id"], "delete_trade", "trade", trade_id, {
        "amount": trade.get("amount_usdt"),
        "status": trade.get("status"),
        "seller_id": trade.get("seller_id"),
        "buyer_id": trade.get("buyer_id")
    })
    
    return {"status": "deleted"}


# ==================== ADMIN: COMMISSION SETTINGS ====================

@router.get("/admin/settings/commissions")
async def get_commission_settings_v2(user: dict = Depends(require_admin_level(80))):
    """Get all commission settings"""
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    return settings or {}


@router.post("/admin/settings/commissions")
async def update_commission_settings_v2(data: dict, user: dict = Depends(require_admin_level(100))):
    """Update commission settings (owner only)"""
    allowed_fields = [
        "trader_commission", "casino_commission", "shop_commission", 
        "stream_commission", "other_commission", "minimum_commission",
        "guarantor_commission_percent", "guarantor_auto_complete_days",
        "referral_commission"
    ]
    
    update_data = {k: float(v) for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields")
    
    await db.commission_settings.update_one({}, {"$set": update_data}, upsert=True)
    
    await log_admin_action(user["id"], "update_commissions", "settings", "commissions", update_data)
    
    return {"status": "success"}


# ==================== ADMIN: FORUM MODERATION ====================

@router.get("/admin/forum/messages")
async def get_forum_messages_admin(
    skip: int = 0,
    limit: int = 100,
    user: dict = Depends(require_admin_level(30))
):
    """Get forum messages for moderation"""
    messages = await db.forum_messages.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return messages


@router.delete("/admin/forum/messages/{message_id}")
async def delete_forum_message(message_id: str, user: dict = Depends(require_admin_level(50))):
    """Delete a forum message"""
    await db.forum_messages.delete_one({"id": message_id})
    
    await log_admin_action(user["id"], "delete_forum_message", "forum", message_id, {})
    
    return {"status": "deleted"}


@router.post("/admin/forum/ban")
async def ban_from_forum(data: dict, user: dict = Depends(require_admin_level(50))):
    """Ban user from forum"""
    user_id = data.get("user_id")
    hours = data.get("hours", 24)
    reason = data.get("reason", "")
    
    ban_until = datetime.now(timezone.utc) + timedelta(hours=hours)
    
    await db.traders.update_one(
        {"id": user_id},
        {"$set": {"forum_ban_until": ban_until.isoformat(), "forum_ban_reason": reason}}
    )
    
    await log_admin_action(user["id"], "forum_ban", "trader", user_id, {"hours": hours, "reason": reason})
    
    return {"status": "banned", "until": ban_until.isoformat()}


# ==================== ADMIN: LOGS ====================

@router.get("/admin/logs")
async def get_admin_logs(
    skip: int = 0,
    limit: int = 100,
    action: str = None,
    user: dict = Depends(require_admin_level(80))
):
    """Get admin action logs"""
    query = {}
    if action:
        query["action"] = action
    
    logs = await db.admin_logs.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return logs


# ==================== ADMIN: WITHDRAWALS ====================

@router.get("/admin/withdrawals")
async def get_pending_withdrawals(status_filter: str = "pending", user: dict = Depends(require_admin_level(50))):
    """Get withdrawal requests with filtering. Returns trader and merchant withdrawals separately."""
    query = {}
    if status_filter and status_filter != "all":
        query["status"] = status_filter
    
    trader_withdrawals = await db.withdrawals.find(
        {**query, "source": {"$ne": "merchant"}}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    merchant_withdrawals = await db.withdrawals.find(
        {**query, "source": "merchant"}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # If no source field exists, try to separate by user_type or return all as trader
    if not trader_withdrawals and not merchant_withdrawals:
        all_withdrawals = await db.withdrawals.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        trader_withdrawals = [w for w in all_withdrawals if w.get("user_type") != "merchant"]
        merchant_withdrawals = [w for w in all_withdrawals if w.get("user_type") == "merchant"]
    
    return {
        "trader_withdrawals": trader_withdrawals,
        "merchant_withdrawals": merchant_withdrawals
    }


@router.post("/admin/withdrawals/{withdrawal_id}/process")
async def process_withdrawal(withdrawal_id: str, decision: str = None, data: dict = None, user: dict = Depends(require_admin_level(50))):
    """Process (approve/reject) withdrawal request. Accepts decision as query param or in body."""
    # Support both query param and body
    action = decision
    reason = ""
    if data and isinstance(data, dict):
        action = action or data.get("action") or data.get("decision")
        reason = data.get("reason", "")
    
    withdrawal = await db.withdrawals.find_one({"id": withdrawal_id}, {"_id": 0})
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    
    if withdrawal.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Withdrawal already processed")
    
    now = datetime.now(timezone.utc).isoformat()
    
    if action == "approve":
        await db.withdrawals.update_one(
            {"id": withdrawal_id},
            {"$set": {"status": "completed", "processed_by": user["id"], "processed_at": now}}
        )
    elif action == "reject":
        # Return funds to user
        await db.traders.update_one(
            {"id": withdrawal["user_id"]},
            {"$inc": {"balance_usdt": withdrawal["amount"]}}
        )
        await db.withdrawals.update_one(
            {"id": withdrawal_id},
            {"$set": {"status": "rejected", "processed_by": user["id"], "processed_at": now, "reject_reason": reason}}
        )
    
    await log_admin_action(user["id"], f"withdrawal_{action}", "withdrawal", withdrawal_id, {"amount": withdrawal["amount"], "reason": reason})
    
    return {"status": "success", "action": action}
