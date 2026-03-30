"""
Trades routes - P2P trade management
Full business logic including commissions, referrals, and disputes
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pydantic import BaseModel
import uuid
import logging
from bson import ObjectId

from core.database import db
from core.pagination import paginate_list
from core.auth import require_role, get_current_user
from core.websocket import manager

try:
    from modules.messaging.ws_routes import ws_manager
except ImportError:
    ws_manager = None

try:
    from modules.notifications.realtime import (
        emit_balance_update, emit_escrow_update, emit_trade_status,
        emit_trade_created, emit_trade_completed, emit_trade_cancelled,
        emit_trade_disputed, emit_trade_payment_sent, emit_offer_volume_changed,
        emit_offer_update, emit_trade_message, emit_referral_bonus
    )
except ImportError:
    pass

try:
    from modules.p2p.offers import check_and_auto_deactivate_offer, try_reactivate_offer
except ImportError:
    async def check_and_auto_deactivate_offer(*a, **kw): return False
    async def try_reactivate_offer(*a, **kw): return False

logger = logging.getLogger("trades")


async def _ws_broadcast(channel: str, data: dict):
    """Broadcast via WebSocket if available"""
    if ws_manager:
        await ws_manager.broadcast(channel, data)

# Import webhook sender
async def send_merchant_webhook_on_trade(trade: dict, status: str, extra_data: dict = None):
    """Send webhook to merchant when trade status changes.
    Supports both old payment_link system and new Invoice API.
    Also syncs invoice status with trade status.
    """
    try:
        # Единый путь: invoice_id или payment_link_id
        inv_id = trade.get("invoice_id") or trade.get("payment_link_id")
        if inv_id:
            from modules.payments.invoice import send_webhook_notification
            
            # Sync invoice status with trade status
            await db.merchant_invoices.update_one(
                {"id": inv_id},
                {"$set": {
                    "status": status,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            await send_webhook_notification(inv_id, status, extra_data)
            return
        
        # Fallback to old merchant_api webhook
        from modules.merchants.api import send_merchant_webhook
        if trade.get("merchant_id") and trade.get("payment_link_id"):
            await send_merchant_webhook(
                trade["merchant_id"],
                trade["payment_link_id"],
                status,
                extra_data
            )
    except Exception as e:
        print(f"Webhook error: {e}")

from models.schemas import TradeCreate, TradeResponse, MessageCreate, MessageResponse

router = APIRouter(tags=["trades"])
# Rate limiting for public (unauthenticated) endpoints
_public_rate_limits = {}
PUBLIC_RATE_LIMIT_MAX = 10
PUBLIC_RATE_LIMIT_WINDOW = 60

def _check_public_rate_limit(ip: str) -> bool:
    import time
    now = time.time()
    if ip not in _public_rate_limits:
        _public_rate_limits[ip] = []
    _public_rate_limits[ip] = [t for t in _public_rate_limits[ip] if now - t < PUBLIC_RATE_LIMIT_WINDOW]
    if len(_public_rate_limits[ip]) >= PUBLIC_RATE_LIMIT_MAX:
        return False
    _public_rate_limits[ip].append(now)
    return True




async def _create_trade_notification(user_id: str, notif_type: str, title: str, message: str, link: str = None, trade_id: str = None):
    """Create a trade event notification (single collection only to avoid duplicates)"""
    await db.event_notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "link": link,
        "reference_id": trade_id,
        "reference_type": "trade",
        "extra_data": {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })


def _payment_detail_to_requisite(detail: dict) -> dict:
    """Convert payment_details document to legacy requisites shape {id, type, data: {...}}."""
    pt = detail.get("payment_type") or detail.get("type")
    req_type = pt
    data = {}
    if pt in ("card", "sng_card"):
        req_type = "card"
        holder = detail.get("holder_name")
        data = {"bank_name": detail.get("bank_name"), "card_number": detail.get("card_number"), "holder_name": holder, "card_holder": holder}
    elif pt in ("sbp", "sng_sbp"):
        req_type = "sbp"
        data = {"bank_name": detail.get("bank_name"), "phone": detail.get("phone_number")}
    elif pt == "sim":
        req_type = "sim"
        data = {"operator": detail.get("operator_name") or detail.get("bank_name"), "phone": detail.get("phone_number")}
    elif pt == "qr_code":
        req_type = "qr"
        data = {"bank_name": detail.get("bank_name"), "qr_data": detail.get("qr_link") or detail.get("qr_data"), "description": detail.get("comment")}
    else:
        req_type = pt or "other"
        data = {"bank_name": detail.get("bank_name")}
    clean_data = {k: v for k, v in data.items() if v not in (None, "")}
    return {"id": detail.get("id"), "trader_id": detail.get("trader_id"), "type": req_type, "data": clean_data}


def _is_legacy_requisite(item: dict) -> bool:
    """Check if item is already in legacy requisite format {id, type, data: {...}}"""
    return "data" in item and "type" in item and isinstance(item.get("data"), dict)



def _clean_doc(doc):
    """Recursively remove MongoDB _id fields and convert ObjectId to string"""
    if isinstance(doc, dict):
        return {k: _clean_doc(v) for k, v in doc.items() if k != "_id"}
    elif isinstance(doc, list):
        return [_clean_doc(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    else:
        return doc

class DirectTradeCreate(BaseModel):
    offer_id: str
    amount_usdt: float
    requisite_id: str



async def get_next_trade_number() -> int:
    """Get next sequential trade number using MongoDB atomic counter"""
    result = await db.counters.find_one_and_update(
        {"_id": "trade_number"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    return result["seq"]


@router.post("/trades")
async def create_trade(data: TradeCreate):
    """Create a new P2P trade"""
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {"trader_commission": 1.0, "minimum_commission": 0.01}
    trader = await db.traders.find_one({"id": data.trader_id}, {"_id": 0})
    
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    
    # Check balance based on trade type
    offer = None
    if data.offer_id:
        offer = await db.offers.find_one({"id": data.offer_id}, {"_id": 0})
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        if offer.get("available_usdt", 0) < data.amount_usdt:
            raise HTTPException(status_code=400, detail="Insufficient offer balance")
    else:
        if trader["balance_usdt"] < data.amount_usdt:
            raise HTTPException(status_code=400, detail="Insufficient trader balance")
    
    amount_rub = round(data.amount_usdt * data.price_rub)  # Без копеек - целое число
    # Ensure amount_rub matches client_pays_rub when provided (avoids rounding discrepancy)
    if data.client_pays_rub:
        amount_rub = round(data.client_pays_rub)
    trader_commission = data.amount_usdt * (settings["trader_commission"] / 100)
    trader_commission = max(trader_commission, settings["minimum_commission"])
    
    merchant_commission = 0.0
    merchant_id = data.merchant_id  # Use merchant_id from request if provided
    
    if data.payment_link_id:
        link = await db.payment_links.find_one({"id": data.payment_link_id}, {"_id": 0})
        if link:
            merchant = await db.merchants.find_one({"id": link["merchant_id"]}, {"_id": 0})
            if merchant:
                merchant_id = merchant["id"]
                commission_key = f"{merchant['merchant_type']}_commission"
                merchant_rate = settings.get(commission_key, 0.5)
                merchant_commission = data.amount_usdt * (merchant_rate / 100)
    
    # Fetch requisites
    requisites = []
    requisite_ids = data.requisite_ids or []
    
    # Если есть offer с реквизитами - используем их напрямую
    if data.offer_id and offer and offer.get("requisites"):
        offer_requisites = offer.get("requisites", [])
        if requisite_ids:
            # Фильтруем по переданным ID
            requisites = [r for r in offer_requisites if r.get("id") in requisite_ids]
        if not requisites:
            # Берём все реквизиты из offer
            requisites = offer_requisites
        requisite_ids = [r["id"] for r in requisites]
    
    # Если реквизиты не найдены в offer - ищем в базе (payment_details, then requisites)
    if not requisites:
        if not requisite_ids and data.offer_id and offer and offer.get("requisite_ids"):
            requisite_ids = offer["requisite_ids"]
        
        if not requisite_ids:
            # Try payment_details first
            all_trader_pds = await db.payment_details.find(
                {"trader_id": data.trader_id}, {"_id": 0}
            ).to_list(100)
            if all_trader_pds:
                requisites = [_payment_detail_to_requisite(pd) for pd in all_trader_pds]
            else:
                all_trader_requisites = await db.requisites.find(
                    {"trader_id": data.trader_id}, {"_id": 0}
                ).to_list(100)
                requisites = all_trader_requisites
            requisite_ids = [r["id"] for r in requisites]
        else:
            for req_id in requisite_ids:
                # Try payment_details first
                pd = await db.payment_details.find_one({"id": req_id}, {"_id": 0})
                if pd:
                    requisites.append(_payment_detail_to_requisite(pd))
                else:
                    req = await db.requisites.find_one({"id": req_id}, {"_id": 0})
                    if req:
                        requisites.append(req)
    
    trade_id = f"trd_{uuid.uuid4().hex[:8]}"
    trade_number = await get_next_trade_number()
    # Clean requisites from any MongoDB ObjectId leftovers
    requisites = [_clean_doc(r) for r in requisites]
    
    trade_doc = {
        "id": trade_id,
        "trade_number": trade_number,
        "amount_usdt": data.amount_usdt,
        "price_rub": data.price_rub,
        "amount_rub": round(amount_rub),  # Целое число без копеек
        "trader_id": data.trader_id,
        "trader_login": trader.get("login", ""),
        "merchant_id": merchant_id,
        "payment_link_id": data.payment_link_id,
        "offer_id": data.offer_id,
        "requisite_ids": requisite_ids,
        "requisites": requisites,
        "buyer_id": data.buyer_id,
        "buyer_type": data.buyer_type,
        "client_session_id": data.client_session_id,
        "status": "pending",
        "trader_commission": round(trader_commission, 4),
        "merchant_commission": round(merchant_commission, 4),
        "total_commission": round(trader_commission + merchant_commission, 4),
        # New amount tracking fields
        "client_amount_rub": round(data.client_amount_rub) if data.client_amount_rub else None,  # Целое число
        "client_pays_rub": round(data.client_pays_rub or amount_rub),  # Целое число
        "merchant_receives_rub": round(data.merchant_receives_rub) if data.merchant_receives_rub else None,
        "merchant_receives_usdt": data.merchant_receives_usdt,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        "completed_at": None
    }
    
    await db.trades.insert_one(trade_doc)
    
    # Reserve funds (atomic check-and-decrement to prevent race conditions)
    if data.offer_id:
        result = await db.offers.update_one(
            {"id": data.offer_id, "available_usdt": {"$gte": data.amount_usdt}},
            {"$inc": {"available_usdt": -data.amount_usdt}}
        )
        if result.modified_count == 0:
            # Race condition - someone else took the funds
            await db.trades.delete_one({"id": trade_id})
            raise HTTPException(status_code=400, detail="Insufficient offer balance (concurrent request)")
    else:
        result = await db.traders.update_one(
            {"id": data.trader_id, "balance_usdt": {"$gte": data.amount_usdt}},
            {"$inc": {"balance_usdt": -data.amount_usdt}}
        )
        if result.modified_count == 0:
            await db.trades.delete_one({"id": trade_id})
            raise HTTPException(status_code=400, detail="Insufficient balance (concurrent request)")
        # Notify seller about balance change
        await _ws_broadcast(f"user_{data.trader_id}", {
            "type": "balance_update",
            "amount": -data.amount_usdt,
            "reason": "trade_created"
        })
    
    # Build auto-message
    offer_conditions = ""
    if data.offer_id and offer and offer.get("conditions"):
        offer_conditions = offer["conditions"]
    
    # Формируем текст реквизитов для чата (ОБЯЗАТЕЛЬНО сохраняется в истории)
    req_text = ""
    for req in requisites:
        req_data = req.get('data', {})
        req_type = req.get("type", "")
        if req_type == "card":
            bank_name = req_data.get('bank_name', 'Банковская карта')
            card_number = req_data.get('card_number', 'Не указан')
            card_holder = req_data.get('card_holder', '')
            req_text += f"\n\n💳 **{bank_name}**"
            req_text += f"\nНомер карты: `{card_number}`"
            if card_holder:
                req_text += f"\nПолучатель: {card_holder}"
        elif req_type == "sbp":
            bank_name = req_data.get('bank_name', 'СБП')
            phone = req_data.get('phone', 'Не указан')
            req_text += f"\n\n⚡ **{bank_name}**"
            req_text += f"\nТелефон: `{phone}`"
        elif req_type == "sim":
            operator_name = req_data.get('operator', req_data.get('bank_name', 'Мобильный'))
            phone = req_data.get('phone', 'Не указан')
            req_text += f"\n\n📱 **{operator_name}**"
            req_text += f"\nТелефон: `{phone}`"
        elif req_type == "qr_code":
            req_text += f"\n\n📲 **QR-код**"
            if req_data.get('qr_data'):
                req_text += f"\nДанные: {req_data['qr_data']}"
    
    auto_msg_content = f"📋 Сделка №{trade_number} создана\n\n"
    auto_msg_content += f"💰 Сумма к оплате: {trade_doc.get('client_pays_rub', trade_doc['amount_rub']):,.0f} ₽\n"
    auto_msg_content += "⏱ Время на оплату: 30 минут"
    
    if offer_conditions:
        auto_msg_content += f"\n\n📝 **Правила продавца:**\n{offer_conditions}"
    
    if req_text:
        auto_msg_content += f"\n\n🏦 **РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:**{req_text}"
    
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "sender_role": "system",
        "content": auto_msg_content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Broadcast via WebSocket
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in system_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "pending", "trade_id": trade_id})
    
    # Notify the trader about the new trade so it appears instantly
    await _ws_broadcast(f"user_{data.trader_id}", {
        "type": "new_trade",
        "trade_id": trade_id,
        "amount_usdt": data.amount_usdt,
        "amount_rub": round(amount_rub, 2),
        "buyer_id": data.buyer_id,
        "status": "pending"
    })
    
    # Send webhook to merchant (PENDING - invoice created)
    if data.payment_link_id and merchant_id:
        await send_merchant_webhook_on_trade(trade_doc, "pending", {
            "trade_id": trade_id,
            "amount_usdt": data.amount_usdt,
            "client_amount_rub": data.client_amount_rub,
            "client_pays_rub": data.client_pays_rub or round(amount_rub, 2),
            "expires_at": trade_doc["expires_at"]
        })
    
    # Create notification for trader about new trade
    await _create_trade_notification(
        data.trader_id,
        "trade_created",
        "Новая сделка",
        f"Создана сделка на {data.amount_usdt:.2f} USDT ({round(amount_rub):,} ₽)",
        f"/trader/sales/{trade_id}",
        trade_id
    )
    
    return trade_doc


@router.get("/trades/purchases/active")
async def get_trader_active_purchases(user: dict = Depends(require_role(["trader"]))):
    """Get active purchases where current trader is the buyer (P2P + QR-агрегатор)"""
    # P2P trades where trader is buyer
    p2p_trades = await db.trades.find(
        {
            "buyer_id": user["id"],
            "buyer_type": "trader",
            "status": {"$in": ["pending", "paid", "disputed"]}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # QR-агрегатор trades where trader is buying USDT
    qr_trades = await db.trades.find(
        {
            "trader_id": user["id"],
            "qr_aggregator_trade": True,
            "status": {"$in": ["pending", "paid", "waiting_payment", "disputed"]}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Combine all trades
    all_trades = p2p_trades + qr_trades
    
    # Enrich with seller/provider info
    for trade in all_trades:
        if trade.get("qr_aggregator_trade"):
            # QR trade - get provider info
            trade["is_qr_purchase"] = True
            provider = await db.qr_providers.find_one(
                {"id": trade.get("provider_id")}, 
                {"_id": 0, "display_name": 1, "login": 1}
            )
            if provider:
                trade["seller_login"] = f"QR: {provider.get('display_name', provider.get('login', ''))}"
                trade["seller_nickname"] = trade["seller_login"]
        else:
            # P2P trade - get seller (trader) info
            seller = await db.traders.find_one(
                {"id": trade["trader_id"]}, 
                {"_id": 0, "login": 1, "nickname": 1}
            )
            if seller:
                trade["trader_login"] = seller.get("login", "")
                trade["trader_nickname"] = seller.get("nickname", seller.get("login", ""))
                trade["seller_login"] = trade["trader_login"]
                trade["seller_nickname"] = trade["trader_nickname"]
    
    # Sort by created_at
    all_trades.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return [_clean_doc(t) for t in all_trades]


@router.get("/trades/sales/active")
async def get_trader_active_sales(user: dict = Depends(require_role(["trader"]))):
    """Get active sales where current trader is the seller (excludes QR trades where trader is buyer)"""
    trades = await db.trades.find(
        {
            "trader_id": user["id"], 
            "status": {"$in": ["pending", "paid", "disputed"]},
            "qr_aggregator_trade": {"$ne": True}  # Exclude QR trades - in those trader is buyer, not seller
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    for trade in trades:
        if trade.get("buyer_id"):
            buyer = await db.traders.find_one({"id": trade["buyer_id"]}, {"_id": 0, "login": 1, "nickname": 1})
            if buyer:
                trade["buyer_login"] = buyer.get("login", "")
                trade["buyer_nickname"] = buyer.get("nickname", buyer.get("login", ""))
        else:
            trade["buyer_nickname"] = "Гость"
    return [_clean_doc(t) for t in trades]


@router.get("/trades/sales/history")
async def get_trader_sales_history(user: dict = Depends(require_role(["trader"]))):
    """Get completed/cancelled sales where current trader was the seller (excludes QR trades)"""
    trades = await db.trades.find(
        {
            "trader_id": user["id"],
            "status": {"$in": ["completed", "cancelled"]},
            "qr_aggregator_trade": {"$ne": True}  # Exclude QR trades - in those trader is buyer, not seller
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    for trade in trades:
        if trade.get("buyer_id"):
            buyer = await db.traders.find_one({"id": trade["buyer_id"]}, {"_id": 0, "login": 1, "nickname": 1})
            if buyer:
                trade["buyer_nickname"] = buyer.get("nickname", buyer.get("login", ""))
        else:
            trade["buyer_nickname"] = "Гость"
    
    return [_clean_doc(t) for t in trades]


@router.get("/trades/purchases/history")
async def get_trader_purchases_history(user: dict = Depends(require_role(["trader"]))):
    """Get completed/cancelled purchases where current trader was the buyer (P2P + QR)"""
    # Find P2P trades where trader is buyer
    p2p_trades = await db.trades.find(
        {
            "buyer_id": user["id"],
            "buyer_type": "trader",
            "status": {"$in": ["completed", "cancelled", "refunded"]}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Find QR aggregator trades where trader is the buyer
    qr_trades = await db.trades.find(
        {
            "trader_id": user["id"],
            "qr_aggregator_trade": True,
            "status": {"$in": ["completed", "cancelled", "pending_completion"]}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Combine and sort by date
    all_trades = p2p_trades + qr_trades
    all_trades.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    # Enrich with seller info for P2P trades
    for trade in all_trades:
        if trade.get("qr_aggregator_trade"):
            # For QR trades, mark as QR purchase
            trade["is_qr_purchase"] = True
            # Get provider info
            provider = await db.qr_providers.find_one({"id": trade.get("provider_id")}, {"_id": 0, "display_name": 1, "login": 1})
            if provider:
                trade["seller_login"] = f"QR: {provider.get('display_name', provider.get('login', ''))}"
                trade["seller_nickname"] = trade["seller_login"]
        else:
            seller = await db.traders.find_one({"id": trade.get("trader_id")}, {"_id": 0, "login": 1, "nickname": 1})
            if seller:
                trade["trader_login"] = seller.get("login", "")
                trade["trader_nickname"] = seller.get("nickname", seller.get("login", ""))
                trade["seller_login"] = trade["trader_login"]
                trade["seller_nickname"] = trade["trader_nickname"]
    
    return [_clean_doc(t) for t in all_trades[:100]]


@router.post("/trades/{trade_id}/confirm")
async def confirm_trade(trade_id: str, user: dict = Depends(require_role(["trader"]))):
    """Trader confirms payment received. Only allowed if client marked as paid or dispute."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade["trader_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your trade")
    
    # Trader can confirm ONLY if:
    # 1. Client marked as paid (status = "paid")
    # 2. Trade is in dispute (status = "disputed")
    if trade["status"] not in ["paid", "disputed"]:
        raise HTTPException(status_code=400, detail="Можно подтвердить только после оплаты клиентом")
    
    now = datetime.now(timezone.utc).isoformat()
    original_status = trade["status"]
    
    # ATOMIC: Update trade status with status check to prevent double-completion
    confirm_result = await db.trades.update_one(
        {"id": trade_id, "status": {"$in": ["paid", "disputed"]}},
        {"$set": {
            "status": "completed",
            "completed_at": now
        }}
    )
    
    if confirm_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Сделка уже обработана (параллельный запрос)")
    
    # Record status change in trade_status_history
    await db.trade_status_history.insert_one({
        "trade_id": trade_id,
        "old_status": trade["status"],
        "new_status": "completed",
        "changed_by": user["id"],
        "changed_by_role": "trader",
        "reason": "trader_confirmed",
        "created_at": now
    })
    
    # === Financial operations with rollback protection ===
    try:
        # If direct P2P trade (trader-to-trader), credit USDT to buyer
        if trade.get("buyer_type") == "trader" and trade.get("buyer_id"):
            buyer_receives = trade["amount_usdt"]
            await db.traders.update_one(
                {"id": trade["buyer_id"]},
                {"$inc": {"balance_usdt": buyer_receives}}
            )
            # Notify buyer about balance update
            await _ws_broadcast(f"user_{trade['buyer_id']}", {
                "type": "balance_update",
                "amount": buyer_receives,
                "reason": "trade_completed"
            })
        # If merchant trade, transfer to merchant
        elif trade.get("merchant_id"):
            # Get merchant's commission rate (set by admin on approval)
            merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0})
            commission_rate = merchant.get("commission_rate", 10.0) if merchant else 10.0
        
            # Get original amount from invoice (what merchant requested, NOT what client paid)
            # This is the base for commission calculation
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
        
            # Update trade with calculated amounts
            commission_usdt = platform_fee_rub / base_rate
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
        
            # Credit merchant balance and update commission paid
            await db.merchants.update_one(
                {"id": trade["merchant_id"]},
                {"$inc": {
                    "balance_usdt": merchant_receives_usdt,
                    "total_commission_paid": commission_usdt
                }}
            )
        
            # Record merchant deposit transaction in transactions collection
            await db.transactions.insert_one({
                "id": str(uuid.uuid4()),
                "tx_id": f"mtx_{trade_id[:8]}_{uuid.uuid4().hex[:6]}",
                "user_id": trade["merchant_id"],
                "type": "deposit",
                "amount": merchant_receives_usdt,
                "amount_rub": original_amount_rub,
                "currency": "USDT",
                "status": "completed",
                "description": f"Пополнение от сделки #{trade_id[:8]} — {original_amount_rub:.0f} RUB ({merchant_receives_usdt:.2f} USDT)",
                "reference_id": trade_id,
                "trade_id": trade_id,
                "invoice_id": trade.get("invoice_id"),
                "merchant_id": trade["merchant_id"],
                "is_financial_operation": True,
                "created_at": now
            })
        
            # Update payment link status
            if trade.get("payment_link_id"):
                await db.payment_links.update_one(
                    {"id": trade["payment_link_id"]},
                    {"$set": {"status": "completed"}}
                )
        
            # Update invoice status to completed
            if trade.get("invoice_id"):
                await db.merchant_invoices.update_one(
                    {"id": trade["invoice_id"]},
                    {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
                )
    
        # Update offer's sold_usdt and actual_commission
        # Commission is already reserved in offer, no need to deduct from trader balance
        trader_commission = trade.get("trader_commission", 0)
        if trade.get("offer_id"):
            await db.offers.update_one(
                {"id": trade["offer_id"]},
                {"$inc": {
                    "sold_usdt": trade["amount_usdt"],
                    "actual_commission": trader_commission
                }}
            )
            # Log commission deduction from reserved funds
            if trader_commission > 0:
                await db.transactions.insert_one({
                    "id": str(uuid.uuid4()),
                    "trader_id": trade["trader_id"],
                    "type": "commission",
                    "amount": -trader_commission,
                    "description": f"Комиссия 1% со сделки #{trade_id[:8]} ({trade['amount_usdt']:.2f} USDT) - из заморозки",
                    "reference_trade_id": trade_id,
                    "from_reserved": True,
                    "created_at": now
                })
    
    except Exception as _fin_err:
        # ROLLBACK: Revert trade status on financial operation failure
        logger.error(f"[ROLLBACK] confirm_trade {trade_id}: financial operation failed: {_fin_err}", exc_info=True)
        try:
            await db.trades.update_one(
                {"id": trade_id},
                {"$set": {"status": original_status}, "$unset": {"completed_at": ""}}
            )
            logger.info(f"[ROLLBACK] confirm_trade {trade_id}: trade status reverted to '{original_status}'")
        except Exception as _rb_err:
            logger.error(f"[ROLLBACK FAILED] confirm_trade {trade_id}: could not revert status: {_rb_err}")
        raise HTTPException(status_code=500, detail="Ошибка обработки сделки. Статус возвращён, попробуйте снова.")

    # Process referral bonus (1-level, 0.5% of sold USDT)
    # Only for seller (trader) trades
    try:
        from modules.social.referral import process_referral_bonus
        await process_referral_bonus(trade_id, trade["trader_id"], trade["amount_usdt"])
    except Exception as e:
        logger.warning(f"Referral bonus error for trade {trade_id}: {e}")
    
    # Agent commission accrual
    if trade.get("merchant_id"):
        try:
            from modules.agents.routes import accrue_agent_commission
            await accrue_agent_commission(trade_id, trade["merchant_id"], trade["amount_usdt"])
        except Exception as e:
            print(f"Agent commission error: {e}")
    # Update unified conversation
    await db.unified_conversations.update_one(
        {"$or": [
            {"related_id": trade_id, "type": "p2p_trade"},
            {"related_id": trade_id, "type": "p2p_dispute"}
        ]},
        {"$set": {
            "status": "completed",
            "resolved": True,
            "resolved_at": now,
            "archived": True
        }}
    )
    
    # Send system message about completion - разное сообщение для мерчант клиента и P2P
    is_merchant_trade = trade.get("payment_link_id") or trade.get("merchant_id")
    if is_merchant_trade:
        # Для клиента мерчанта - не показываем USDT
        completion_text = f"✅ Сделка завершена! Оплата подтверждена. Средства зачислены."
    else:
        # Для P2P сделки - показываем USDT
        completion_text = f"✅ Сделка №{trade.get('trade_number', '')} завершена! Продавец подтвердил получение оплаты. {trade['amount_usdt']} USDT переведены покупателю."
    
    confirm_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "sender_role": "system",
        "content": completion_text,
        "created_at": now
    }
    await db.trade_messages.insert_one(confirm_msg)
    
    # Broadcast via WebSocket to both parties
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in confirm_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "completed", "trade_id": trade_id})

    # Real-time: notify both parties of completion + balance changes
    try:
        await emit_trade_completed(trade_id, trade["trader_id"], trade.get("buyer_id", ""), trade["amount_usdt"])
        seller_updated = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0, "balance_usdt": 1})
        if seller_updated:
            await emit_balance_update(trade["trader_id"], seller_updated.get("balance_usdt", 0), "trade_completed")
        buyer_id = trade.get("buyer_id", "")
        if buyer_id:
            buyer_updated = await db.traders.find_one({"id": buyer_id}, {"_id": 0, "balance_usdt": 1})
            if buyer_updated:
                await emit_balance_update(buyer_id, buyer_updated.get("balance_usdt", 0), "trade_completed")
        # Emit offer update (volume changed after trade)
        if trade.get("offer_id"):
            offer_after = await db.offers.find_one({"id": trade["offer_id"]}, {"_id": 0})
            if offer_after:
                await emit_offer_update(trade["offer_id"], "volume_changed", offer_after)
                # Auto-deactivate offer if remaining balance < min_amount
                try:
                    await check_and_auto_deactivate_offer(trade["offer_id"])
                except Exception as e:
                    logger.warning(f"[AUTO-DEACT] Error after trade completion: {e}")
    except Exception as e:
        logger.warning(f"[RT] trade_completed event error: {e}")

    # Also notify buyer directly
    if trade.get("buyer_id"):
        await _ws_broadcast(f"user_{trade['buyer_id']}", {
            "type": "trade_completed",
            "trade_id": trade_id,
            "amount_usdt": trade["amount_usdt"],
            "status": "completed"
        })
    
    # Send webhook to merchant (COMPLETED) — с данными для бухгалтерии
    fresh_trade = await db.trades.find_one({"id": trade_id}, {"_id": 0}) or trade
    payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    current_rate = payout_settings.get("base_rate", 78.5) if payout_settings else 78.5
    
    await send_merchant_webhook_on_trade(fresh_trade, "completed", {
        "amount_usdt": fresh_trade.get("amount_usdt") or trade["amount_usdt"],
        "merchant_receives_usdt": fresh_trade.get("merchant_receives_usdt") or 0,
        "commission_usdt": fresh_trade.get("merchant_commission") or 0,
        "exchange_rate": current_rate,
        "completed_at": now
    })
    
    # Create event notifications for both parties
    if trade.get("trader_id"):
        await _create_trade_notification(
            trade["trader_id"], 
            "trade_completed",
            "Сделка завершена",
            f"Сделка на {trade['amount_usdt']:.2f} USDT успешно завершена",
            f"/trader/sales/{trade_id}",
            trade_id
        )
    if trade.get("buyer_id") and trade.get("buyer_type") == "trader":
        await _create_trade_notification(
            trade["buyer_id"],
            "trade_completed", 
            "Сделка завершена",
            f"Сделка на {trade['amount_usdt']:.2f} USDT успешно завершена",
            f"/trader/purchases/{trade_id}",
            trade_id
        )
    

    # === Record trade in transactions for financial history ===
    tn = trade.get("trade_number", "")
    # Seller transaction - NOT recorded as financial operation
    # because funds were already frozen when offer was created
    # This is for audit trail only, will be shown in Trade History, not Finance History
    await db.transactions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": trade["trader_id"],
        "trader_id": trade["trader_id"],
        "type": "trade_sale",  # Changed from "trade" - sale from offer, funds already frozen
        "subtype": "p2p_sell",
        "amount": -trade["amount_usdt"],
        "currency": "USDT",
        "status": "completed",
        "description": f"Продажа {trade['amount_usdt']:.2f} USDT — Сделка №{tn}",
        "reference_id": trade_id,
        "trade_number": tn,
        "is_financial_operation": False,  # Not a financial operation - funds were frozen at offer creation
        "created_at": now
    })
    # Buyer transaction (if trader) - recorded as purchase (financial operation)
    if trade.get("buyer_type") == "trader" and trade.get("buyer_id"):
        await db.transactions.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": trade["buyer_id"],
            "trader_id": trade["buyer_id"],
            "type": "purchase_completed",  # Changed from "trade" - this is a credit to buyer
            "subtype": "p2p_buy",
            "amount": trade["amount_usdt"],
            "currency": "USDT",
            "status": "completed",
            "description": f"Покупка {trade['amount_usdt']:.2f} USDT — Сделка №{tn}",
            "reference_id": trade_id,
            "trade_number": tn,
            "is_financial_operation": True,  # This IS a financial operation - credit to buyer
            "created_at": now
        })

    return {"status": "completed"}


@router.post("/trades/{trade_id}/mark-paid")
async def mark_trade_paid(trade_id: str, request: Request):
    """Mark a trade as paid by customer (no auth required for customer)"""
    # Rate limit public endpoint
    client_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    if not _check_public_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade["status"] != "pending":
        raise HTTPException(status_code=400, detail="Trade not pending")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {"status": "paid", "paid_at": now}}
    )
    
    # Record status change in trade_status_history
    await db.trade_status_history.insert_one({
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "old_status": "pending",
        "new_status": "paid",
        "changed_by": "client",
        "changed_by_role": "client",
        "reason": "client_marked_paid",
        "created_at": now
    })
    
    # Send system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": f"✅ Клиент подтвердил оплату {trade.get('client_pays_rub', trade['amount_rub']):,.0f} ₽. Трейдер, проверьте поступление средств на ваши реквизиты.",
        "created_at": now
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Broadcast via WebSocket to trade channel
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in system_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "paid", "trade_id": trade_id})

    # Real-time: payment sent event
    try:
        await emit_trade_payment_sent(trade_id, trade["trader_id"], trade.get("buyer_id", ""), trade.get("client_pays_rub", trade.get("amount_rub", 0)))
    except Exception as e:
        print(f"[RT] payment_sent event error: {e}")
    
    # Also broadcast to trader's user channel for immediate notification
    await _ws_broadcast(f"user_{trade['trader_id']}", {
        "type": "trade_status_update",
        "trade_id": trade_id,
        "status": "paid",
        "message": f"Клиент оплатил сделку {trade_id[:12]}"
    })
    
    # Create notification for trader about payment
    try:
        await _create_trade_notification(
            user_id=trade["trader_id"],
            notif_type="trade_payment",
            title="Оплата получена",
            message=f"Клиент оплатил сделку на {trade.get('client_pays_rub', trade['amount_rub']):,.0f} \u20bd",
            link=f"/trader/sales/{trade_id}"
        )
    except Exception:
        pass
    
    # Send webhook to merchant (PAID)
    await send_merchant_webhook_on_trade(trade, "paid", {
        "trade_id": trade_id,
        "paid_at": now
    })
    
    return {"status": "paid"}


@router.post("/trades/{trade_id}/cancel")
async def cancel_trade(trade_id: str, user: dict = Depends(require_role(["trader"]))):
    """Trader can cancel ONLY if pending and 30 minutes passed without payment."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade["trader_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your trade")
    
    if trade["status"] != "pending":
        raise HTTPException(status_code=400, detail="Отменить можно только если клиент не оплатил")
    
    created_at = datetime.fromisoformat(trade["created_at"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    minutes_passed = (now - created_at).total_seconds() / 60
    
    if minutes_passed < 30:
        remaining = int(30 - minutes_passed)
        raise HTTPException(status_code=400, detail=f"Отменить можно через {remaining} мин. если клиент не оплатит")
    
    # Return funds
    if trade.get("offer_id"):
        await db.offers.update_one(
            {"id": trade["offer_id"]},
            {"$inc": {"available_usdt": trade["amount_usdt"]}}
        )
    else:
        await db.traders.update_one(
            {"id": trade["trader_id"]},
            {"$inc": {"balance_usdt": trade["amount_usdt"]}}
        )
        # Notify seller about refund
        await _ws_broadcast(f"user_{trade['trader_id']}", {
            "type": "balance_update",
            "amount": trade["amount_usdt"],
            "reason": "trade_cancelled"
        })
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {"status": "cancelled", "cancelled_at": now.isoformat()}}
    )
    
    # Record status change in trade_status_history
    await db.trade_status_history.insert_one({
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "old_status": trade["status"],
        "new_status": "cancelled",
        "changed_by": user["id"],
        "changed_by_role": "trader",
        "reason": "trader_cancelled_timeout",
        "created_at": now.isoformat()
    })
    
    # Update invoice status to cancelled
    if trade.get("invoice_id"):
        await db.merchant_invoices.update_one(
            {"id": trade["invoice_id"]},
            {"$set": {"status": "cancelled", "cancelled_at": now.isoformat()}}
        )
    
    # System message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": "❌ Сделка отменена трейдером (клиент не оплатил в течение 30 минут).",
        "created_at": now.isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Broadcast via WebSocket
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in system_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "cancelled", "trade_id": trade_id})

    # Real-time: trade cancelled event + offer volume restore
    try:
        await emit_trade_cancelled(trade_id, trade.get("trader_id", ""), trade.get("buyer_id", ""))
        # Emit offer volume restored
        if trade.get("offer_id"):
            offer_after = await db.offers.find_one({"id": trade["offer_id"]}, {"_id": 0})
            if offer_after:
                await emit_offer_volume_changed(trade["offer_id"], offer_after.get("available_usdt", 0), trade["amount_usdt"])
                await emit_offer_update(trade["offer_id"], "volume_changed", offer_after)
                # Try to reactivate auto-deactivated offer if balance is now sufficient
                try:
                    await try_reactivate_offer(trade["offer_id"])
                except Exception as e:
                    print(f"[AUTO-REACT] Error after trade cancellation: {e}")
    except Exception as e:
        print(f"[RT] trade_cancelled event error: {e}")

    
    # Send webhook to merchant (CANCELLED)
    await send_merchant_webhook_on_trade(trade, "cancelled", {
        "trade_id": trade_id,
        "reason": "Клиент не оплатил в течение 30 минут",
        "cancelled_at": now.isoformat(),
        "amount_usdt": trade.get("amount_usdt", 0)
    })
    
    # Create event notifications for both parties
    if trade.get("trader_id"):
        await _create_trade_notification(
            trade["trader_id"],
            "trade_cancelled",
            "Сделка отменена",
            f"Сделка на {trade['amount_usdt']:.2f} USDT была отменена",
            f"/trader/sales/{trade_id}",
            trade_id
        )
    if trade.get("buyer_id") and trade.get("buyer_type") == "trader":
        await _create_trade_notification(
            trade["buyer_id"],
            "trade_cancelled",
            "Сделка отменена",
            f"Сделка на {trade['amount_usdt']:.2f} USDT была отменена",
            f"/trader/purchases/{trade_id}",
            trade_id
        )
    
    return {"status": "cancelled"}


@router.get("/trades/{trade_id}/public")
async def get_trade_public(trade_id: str, request: Request):
    """Get trade details - public endpoint for client"""
    # Rate limit public endpoint
    client_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    if not _check_public_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    return {
        "id": trade["id"],
        "amount_usdt": trade["amount_usdt"],
        "amount_rub": trade["amount_rub"],
        "client_pays_rub": trade.get("client_pays_rub"),
        "price_rub": trade["price_rub"],
        "status": trade["status"],
        "requisites": trade.get("requisites", []) if trade["status"] in ["pending", "paid"] else [],
        "trader_login": trade.get("trader_login", ""),
        "created_at": trade["created_at"],
        "expires_at": trade.get("expires_at"),
        "paid_at": trade.get("paid_at")
    }


@router.get("/trades/{trade_id}/messages")
async def get_trade_messages(trade_id: str, user: dict = Depends(get_current_user)):
    """Get trade messages"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    messages = await db.trade_messages.find({"trade_id": trade_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    return messages


@router.get("/trades/{trade_id}/messages-public")
async def get_trade_messages_public(trade_id: str, request: Request):
    """Get trade messages - public endpoint for client"""
    # Rate limit public endpoint
    client_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    if not _check_public_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    messages = await db.trade_messages.find({"trade_id": trade_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    return messages


@router.post("/trades/{trade_id}/messages")
async def send_trade_message(trade_id: str, data: MessageCreate, user: dict = Depends(get_current_user)):
    """Send message in trade chat"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Determine sender type and check access
    user_role = user.get("role", "")
    user_id = user.get("id", "")
    
    if user_role in ["admin", "mod_p2p", "owner"]:
        sender_type = "admin"
    elif user_role == "merchant":
        # Check if this merchant is part of the trade
        if trade.get("merchant_id") != user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой сделке")
        sender_type = "merchant"
    elif user_role == "qr_provider":
        # QR Provider can only message in disputed QR trades they're part of
        if not trade.get("qr_aggregator_trade"):
            raise HTTPException(status_code=403, detail="Провайдер может писать только в QR-сделках")
        if trade.get("provider_id") != user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой сделке")
        if trade.get("status") != "disputed":
            raise HTTPException(status_code=403, detail="Провайдер может писать только в спорных сделках")
        sender_type = "provider"
    elif user_role == "trader":
        if trade["trader_id"] == user_id:
            sender_type = "trader"
        elif trade.get("buyer_id") == user_id:
            sender_type = "buyer"
        else:
            raise HTTPException(status_code=403, detail="Нет доступа к этой сделке")
    else:
        sender_type = "client"
    
    sender_name = user.get("nickname", user.get("login", user.get("display_name", "")))
    
    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": user_id,
        "sender_type": sender_type,
        "sender_role": user_role,
        "sender_name": sender_name,
        "sender_nickname": sender_name,
        "content": data.content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.trade_messages.insert_one(msg)
    await manager.broadcast(f"trade_{trade_id}", {k: v for k, v in msg.items() if k != "_id"})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in msg.items() if k != "_id"}})
    
    # Create notifications for all participants about new message
    try:
        participants = set()
        if trade.get("trader_id") and trade["trader_id"] != user_id:
            participants.add(("trader", trade["trader_id"]))
        if trade.get("buyer_id") and trade["buyer_id"] != user_id:
            participants.add(("trader", trade["buyer_id"]))
        if trade.get("merchant_id") and trade["merchant_id"] != user_id:
            participants.add(("merchant", trade["merchant_id"]))
        # Notify provider for QR disputes
        if trade.get("qr_aggregator_trade") and trade.get("provider_id") and trade["provider_id"] != user_id:
            participants.add(("qr_provider", trade["provider_id"]))
        
        for role, pid in participants:
            await _create_trade_notification(
                user_id=pid,
                notif_type="trade_message",
                title="Сообщение в сделке",
                message=f"Новое сообщение в сделке #{trade_id[:8]}",
                link=f"/trader/sales/{trade_id}" if role == "trader" else f"/merchant/payments"
            )
    except Exception:
        pass
    
    return {k: v for k, v in msg.items() if k != "_id"}


@router.post("/trades/{trade_id}/messages-public")
async def send_trade_message_public(trade_id: str, data: MessageCreate, request: Request):
    """Send message as client (no auth) to trade chat"""
    # Rate limit public endpoint
    client_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    if not _check_public_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    # Validate message content length to prevent abuse
    if not data.content or len(data.content.strip()) == 0:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    if len(data.content) > 2000:
        raise HTTPException(status_code=400, detail="Сообщение слишком длинное (макс. 2000 символов)")
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade["status"] in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Сделка завершена, чат закрыт")
    
    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "client",
        "sender_type": "client",
        "sender_role": "client",
        "sender_nickname": "Покупатель",
        "content": data.content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.trade_messages.insert_one(msg)
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in msg.items() if k != "_id"}})
    
    # Create notification for trader about client message
    try:
        await _create_trade_notification(
            user_id=trade["trader_id"],
            notif_type="trade_message",
            title="Сообщение в сделке",
            message=f"Покупатель написал в сделке #{trade_id[:8]}",
            link=f"/trader/sales/{trade_id}"
        )
    except Exception:
        pass
    
    return {k: v for k, v in msg.items() if k != "_id"}


@router.get("/trades")
async def get_trades(user: dict = Depends(get_current_user)):
    """Get trades for current user"""
    if user["role"] == "trader":
        trades = await db.trades.find({"trader_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    elif user["role"] == "merchant":
        trades = await db.trades.find({"merchant_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    else:
        trades = await db.trades.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [_clean_doc(t) for t in trades]


@router.get("/trades/{trade_id}")
async def get_trade(trade_id: str, user: dict = Depends(get_current_user)):
    """Get single trade details"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Check access - allow both seller (trader_id) and buyer (buyer_id)
    if user["role"] == "trader":
        is_seller = trade["trader_id"] == user["id"]
        is_buyer = trade.get("buyer_id") == user["id"]
        if not (is_seller or is_buyer):
            raise HTTPException(status_code=403, detail="Access denied")
    if user["role"] == "merchant" and trade.get("merchant_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Add seller_login for buyer view
    if trade.get("buyer_id") == user["id"]:
        seller = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0})
        if seller:
            trade["seller_login"] = seller.get("login", seller.get("nickname", ""))
    
    # Populate requisites (search payment_details first, then requisites as fallback)
    if trade.get("requisite_ids"):
        requisites = []
        for req_id in trade["requisite_ids"]:
            pd = await db.payment_details.find_one({"id": req_id}, {"_id": 0})
            if pd:
                requisites.append(_payment_detail_to_requisite(pd))
            else:
                req = await db.requisites.find_one({"id": req_id}, {"_id": 0})
                if req:
                    requisites.append(req)
        if requisites:
            trade["requisites"] = requisites
    elif trade.get("requisite"):
        trade["requisites"] = [trade["requisite"]]
    elif not trade.get("requisites"):
        # Try payment_details first
        seller_pds = await db.payment_details.find(
            {"trader_id": trade["trader_id"]}, {"_id": 0}
        ).to_list(20)
        if seller_pds:
            trade["requisites"] = [_payment_detail_to_requisite(pd) for pd in seller_pds]
        else:
            seller_requisites = await db.requisites.find(
                {"trader_id": trade["trader_id"]}, 
                {"_id": 0}
            ).to_list(20)
            if seller_requisites:
                trade["requisites"] = seller_requisites
    # Ensure existing requisites are in legacy format
    if trade.get("requisites"):
        reqs = trade["requisites"]
        if reqs and not _is_legacy_requisite(reqs[0]):
            trade["requisites"] = [_payment_detail_to_requisite(r) for r in reqs]
    
    return _clean_doc(trade)


# ==================== DIRECT TRADES & DISPUTES ====================

@router.post("/trades/direct")
async def create_direct_trade(data: DirectTradeCreate, user: dict = Depends(require_role(["trader"]))):
    """Create a direct P2P trade between traders (buyer and seller)"""
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    
    # Get the offer
    offer = await db.offers.find_one({"id": data.offer_id, "is_active": True}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Объявление не найдено или неактивно")
    
    # Can't buy from yourself
    if offer["trader_id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Нельзя покупать у самого себя")
    
    # Check limits
    if data.amount_usdt < (offer.get("min_amount", 1)):
        raise HTTPException(status_code=400, detail=f"Минимальная сумма: {offer.get('min_amount', 1)} USDT")
    if data.amount_usdt > (offer.get("max_amount", offer["available_usdt"])):
        raise HTTPException(status_code=400, detail=f"Максимальная сумма: {offer.get('max_amount', offer['available_usdt'])} USDT")
    if data.amount_usdt > offer["available_usdt"]:
        raise HTTPException(status_code=400, detail=f"Доступно только {offer['available_usdt']} USDT")
    
    # Get seller (trader who created the offer)
    seller = await db.traders.find_one({"id": offer["trader_id"]}, {"_id": 0})
    if not seller:
        raise HTTPException(status_code=404, detail="Продавец не найден")
    
    # Get requisite - search in offer's embedded requisites, then payment_details, then requisites
    requisite = None
    # 1. Search in offer's embedded requisites
    for r in (offer.get("requisites") or []):
        if r.get("id") == data.requisite_id:
            # Convert to legacy format if needed (might be raw payment_details format)
            if _is_legacy_requisite(r):
                requisite = r
            else:
                requisite = _payment_detail_to_requisite(r)
            break
    # 2. Search in db.payment_details and convert to legacy format
    if not requisite:
        pd = await db.payment_details.find_one({"id": data.requisite_id, "trader_id": offer["trader_id"]}, {"_id": 0})
        if pd:
            requisite = _payment_detail_to_requisite(pd)
    # 3. Fallback to db.requisites (legacy collection)
    if not requisite:
        requisite = await db.requisites.find_one({"id": data.requisite_id, "trader_id": offer["trader_id"]}, {"_id": 0})
    if not requisite:
        raise HTTPException(status_code=404, detail="Реквизит не найден")
    
    amount_rub = data.amount_usdt * offer["price_rub"]
    trader_commission = data.amount_usdt * (settings["trader_commission"] / 100)
    trader_commission = max(trader_commission, settings["minimum_commission"])
    
    trade_id = f"trd_{uuid.uuid4().hex[:8]}"
    trade_doc = {
        "id": trade_id,
        "offer_id": offer["id"],
        "trader_id": offer["trader_id"],  # Seller
        "buyer_id": user["id"],  # Buyer (another trader)
        "buyer_type": "trader",  # Mark as trader-to-trader trade
        "amount_usdt": data.amount_usdt,
        "amount_rub": amount_rub,
        "price_rub": offer["price_rub"],
        "requisite": requisite,  # Selected requisite (legacy)
        "requisites": [requisite],  # Array for frontend compatibility
        "merchant_id": None,
        "payment_link_id": None,
        "trader_commission": trader_commission,
        "merchant_commission": 0.0,
        "total_commission": trader_commission,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    }
    
    # ATOMIC: Reserve USDT from offer with balance check (prevents race condition)
    reserve_result = await db.offers.update_one(
        {"id": offer["id"], "available_usdt": {"$gte": data.amount_usdt}},
        {"$inc": {"available_usdt": -data.amount_usdt}}
    )
    
    if reserve_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Недостаточно средств в объявлении (параллельный запрос)")
    
    await db.trades.insert_one(trade_doc)
    
    # Get buyer info
    buyer = await db.traders.find_one({"id": user["id"]}, {"_id": 0})
    
    # Auto-message with rules
    auto_msg_content = f"🔔 Новая P2P сделка #{trade_id}\n\n"
    auto_msg_content += f"👤 Покупатель: @{buyer['login']}\n"
    auto_msg_content += f"💵 Сумма: {data.amount_usdt} USDT\n"
    auto_msg_content += f"💰 К оплате: {amount_rub:,.0f} ₽\n"
    auto_msg_content += f"📈 Курс: {offer['price_rub']} ₽/USDT\n"
    auto_msg_content += "⏱ Время на оплату: 30 минут\n"
    
    if offer.get("conditions"):
        auto_msg_content += f"\n📝 Правила продавца:\n{offer['conditions']}\n"
    
    # Requisite info
    req_text = ""
    if requisite["type"] == "card":
        req_text = f"\n💳 {requisite['data'].get('bank_name', '')}"
        req_text += f"\n   Карта: {requisite['data'].get('card_number', '')}"
        if requisite['data'].get('holder_name'):
            req_text += f"\n   Получатель: {requisite['data']['holder_name']}"
    elif requisite["type"] == "sbp":
        req_text = f"\n⚡ СБП {requisite['data'].get('bank_name', '')}"
        req_text += f"\n   Телефон: {requisite['data'].get('phone', '')}"
    
    if req_text:
        auto_msg_content += f"\n🏦 Реквизиты для оплаты:{req_text}"
    
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": auto_msg_content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Broadcast initial message via WebSocket
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in system_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "pending", "trade_id": trade_id})
    
    # Notify the seller about the new trade
    await _ws_broadcast(f"user_{offer['trader_id']}", {
        "type": "new_trade",
        "trade_id": trade_id,
        "amount_usdt": data.amount_usdt,
        "amount_rub": amount_rub,
        "buyer_id": user["id"],
        "status": "pending"
    })
    
    # Create event notification for the seller
    await _create_trade_notification(
        offer["trader_id"],
        "trade_created",
        "Новая сделка",
        f"Создана сделка на {data.amount_usdt:.2f} USDT ({round(amount_rub):,} ₽)",
        f"/trader/sales/{trade_id}",
        trade_id
    )
    
    # Clean MongoDB _id before returning
    trade_doc.pop("_id", None)
    if trade_doc.get("requisite"):
        trade_doc["requisite"].pop("_id", None) if isinstance(trade_doc["requisite"], dict) else None
    if trade_doc.get("requisites"):
        for r in trade_doc["requisites"]:
            if isinstance(r, dict):
                r.pop("_id", None)
    return trade_doc


@router.post("/trades/{trade_id}/cancel-client")
async def cancel_trade_client(trade_id: str):
    """Client can cancel trade at any time (pending, paid, disputed)."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # ATOMIC: Update status first to prevent double-cancel/double-refund
    cancel_result = await db.trades.update_one(
        {"id": trade_id, "status": {"$nin": ["completed", "cancelled"]}},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat(), "cancelled_by": "client"}}
    )
    
    if cancel_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Сделка уже завершена или отменена.")
    
    # Record status change in trade_status_history
    await db.trade_status_history.insert_one({
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "old_status": trade["status"],
        "new_status": "cancelled",
        "changed_by": "client",
        "changed_by_role": "client",
        "reason": "client_cancelled",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Return funds (safe - status already set to cancelled atomically)
    if trade.get("offer_id"):
        # Trade from offer - return to offer's available_usdt
        await db.offers.update_one(
            {"id": trade["offer_id"]},
            {"$inc": {"available_usdt": trade["amount_usdt"]}}
        )
        # Try to reactivate auto-deactivated offer if balance now sufficient
        try:
            await try_reactivate_offer(trade["offer_id"])
        except Exception as e:
            print(f"[AUTO-REACT] Error after client cancellation: {e}")
    else:
        # Direct trade - return to trader's balance
        await db.traders.update_one(
            {"id": trade["trader_id"]},
            {"$inc": {"balance_usdt": trade["amount_usdt"]}}
        )
    
    # Update invoice status to cancelled
    if trade.get("invoice_id"):
        await db.merchant_invoices.update_one(
            {"id": trade["invoice_id"]},
            {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    # System message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": "❌ Сделка отменена покупателем.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Broadcast via WebSocket
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in system_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "cancelled", "trade_id": trade_id})
    
    # Notify trader that client cancelled the trade
    if trade.get("trader_id"):
        await _create_trade_notification(
            user_id=trade["trader_id"],
            notif_type="trade_cancelled",
            title="Сделка отменена",
            message=f"Покупатель отменил сделку на {trade['amount_usdt']:.2f} USDT",
            link=f"/trader/sales/{trade_id}",
            trade_id=trade_id
        )
    
    # Send webhook to merchant if applicable
    if trade.get("merchant_id"):
        await send_merchant_webhook_on_trade(trade, "cancelled", {
            "trade_id": trade_id,
            "reason": "Отменено покупателем",
            "cancelled_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {"status": "cancelled"}



@router.get("/trades/{trade_id}/chat-history")
async def get_trade_chat_history(trade_id: str, user: dict = Depends(get_current_user)):
    """Get full chat history for a trade - accessible to buyer, seller, admin, moderator."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Check access: buyer, seller, admin, or moderator
    user_id = user.get("id")
    user_role = user.get("role", "")
    is_buyer = user_id == trade.get("buyer_id")
    is_seller = user_id == trade.get("trader_id")
    is_admin = user_role in ["admin", "mod_p2p", "owner"]
    
    if not (is_buyer or is_seller or is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get all messages
    messages = await db.trade_messages.find(
        {"trade_id": trade_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    
    # Get seller/buyer info
    seller = await db.traders.find_one({"id": trade.get("trader_id")}, {"_id": 0})
    buyer = None
    if trade.get("buyer_id"):
        buyer = await db.traders.find_one({"id": trade["buyer_id"]}, {"_id": 0})
    
    return {
        "trade": {
            "id": trade["id"],
            "status": trade.get("status"),
            "amount_usdt": trade.get("amount_usdt"),
            "amount_rub": trade.get("amount_rub"),
            "client_pays_rub": trade.get("client_pays_rub"),
            "price_rub": trade.get("price_rub"),
            "created_at": trade.get("created_at"),
            "completed_at": trade.get("completed_at"),
            "disputed_at": trade.get("disputed_at"),
            "dispute_reason": trade.get("dispute_reason"),
            "disputed_by_role": trade.get("disputed_by_role"),
            "seller_nickname": seller.get("nickname", seller.get("login", "")) if seller else "",
            "buyer_nickname": buyer.get("nickname", buyer.get("login", "")) if buyer else "Клиент",
            "requisites": trade.get("requisites", [])
        },
        "messages": messages
    }

@router.post("/trades/{trade_id}/dispute")
async def open_dispute(trade_id: str, reason: str = "", user: dict = Depends(get_current_user)):
    """Open a dispute. Trader can open immediately after payment, client after 10 minutes."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Check if dispute is already open
    if trade["status"] == "disputed":
        raise HTTPException(status_code=400, detail="Спор уже открыт")
    
    # Only paid trades can be disputed
    if trade["status"] != "paid":
        raise HTTPException(status_code=400, detail="Спор можно открыть только после оплаты")
    
    # Trader can open dispute immediately, merchant immediately, client after 10 minutes
    is_seller = user and user.get("role") == "trader" and user.get("id") == trade.get("trader_id")
    is_buyer = user and user.get("role") == "trader" and user.get("id") == trade.get("buyer_id")
    is_merchant = user and user.get("role") == "merchant" and user.get("id") == trade.get("merchant_id")
    
    if not is_seller and not is_merchant:
        # Buyer/Client needs to wait 10 minutes
        paid_at = trade.get("paid_at")
        if paid_at:
            paid_time = datetime.fromisoformat(paid_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            minutes_passed = (now - paid_time).total_seconds() / 60
            
            if minutes_passed < 10:
                remaining = int(10 - minutes_passed)
                raise HTTPException(status_code=400, detail=f"Спор можно открыть через {remaining} мин.")
    
    # Determine who opened dispute
    if is_seller:
        opener = "продавцом"
    elif is_merchant:
        opener = "мерчантом"
    elif is_buyer:
        opener = "покупателем"
    else:
        opener = "клиентом"
    
    # Update trade status to disputed
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "disputed",
            "disputed_at": datetime.now(timezone.utc).isoformat(),
            "dispute_reason": reason or "Не указана",
            "disputed_by": user.get("id") if user else "client",
            "disputed_by_role": opener
        }}
    )
    
    # Record status change in trade_status_history
    await db.trade_status_history.insert_one({
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "old_status": trade["status"],
        "new_status": "disputed",
        "changed_by": user.get("id") if user else "client",
        "changed_by_role": opener,
        "reason": f"dispute_opened: {reason or 'Не указана'}",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Send system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "is_system": True,
        "sender_role": "system",
        "content": f"⚠️ Спор открыт {opener}! Причина: {reason or 'не указана'}. Администратор подключится к чату.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "disputed", "trade_id": trade_id})

    # Real-time: dispute event
    try:
        await emit_trade_disputed(trade_id, trade.get("trader_id", ""), trade.get("buyer_id", ""))
    except Exception as e:
        print(f"[RT] trade_disputed event error: {e}")
    
    # Create notification for participants about dispute (using event_notifications)
    try:
        participants = set()
        if trade.get("trader_id"):
            participants.add(trade["trader_id"])
        if trade.get("buyer_id"):
            participants.add(trade["buyer_id"])
        if user and user.get("id"):
            participants.discard(user["id"])
        
        for pid in participants:
            # Create in event_notifications (new system)
            await db.event_notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": pid,
                "type": "trade_disputed",
                "title": "Спор по сделке",
                "message": f"Открыт спор по сделке #{trade_id[:8]} на {trade.get('amount_usdt', 0):.2f} USDT",
                "link": f"/trader/sales/{trade_id}",
                "reference_id": trade_id,
                "reference_type": "trade_dispute",
                "extra_data": {"reason": reason or "Не указана"},
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            # Also create in old system for backward compatibility
            await _create_trade_notification(
                user_id=pid,
                notif_type="trade_disputed",
                title="Спор открыт",
                message=f"Открыт спор по сделке #{trade_id[:8]}",
                link=f"/trader/sales/{trade_id}",
                trade_id=trade_id
            )
            # Real-time WebSocket notification
            await _ws_broadcast(f"user_{pid}", {
                "type": "new_notification",
                "notification": {
                    "id": str(uuid.uuid4()),
                    "type": "trade_disputed",
                    "title": "Спор по сделке",
                    "message": f"Открыт спор по сделке #{trade_id[:8]}",
                    "link": f"/trader/sales/{trade_id}"
                }
            })
    except Exception:
        pass
    
    # Create notification for MERCHANT about dispute
    if trade.get("merchant_id"):
        try:
            await db.event_notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": trade["merchant_id"],
                "type": "trade_disputed",
                "title": "Спор по сделке",
                "message": f"Открыт спор по сделке #{trade_id[:8]} на {trade.get('amount_usdt', 0):.2f} USDT",
                "link": "/merchant/payments",
                "reference_id": trade_id,
                "reference_type": "trade_dispute",
                "extra_data": {"reason": reason or "Не указана"},
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            # Real-time WebSocket notification for merchant
            await _ws_broadcast(f"user_{trade['merchant_id']}", {
                "type": "new_notification",
                "notification": {
                    "id": str(uuid.uuid4()),
                    "type": "trade_disputed",
                    "title": "Спор по сделке",
                    "message": f"Открыт спор по сделке #{trade_id[:8]}",
                    "link": "/merchant/payments"
                }
            })
        except Exception:
            pass
    
    # Send webhook to merchant (DISPUTED)
    await send_merchant_webhook_on_trade(trade, "disputed", {
        "trade_id": trade_id,
        "reason": reason or "Не указана",
        "disputed_at": datetime.now(timezone.utc).isoformat(),
        "disputed_by": opener
    })
    
    return {"status": "disputed"}


@router.post("/trades/{trade_id}/dispute-public")
async def open_dispute_public(trade_id: str, request: Request, reason: str = ""):
    """Open a dispute by client (no auth) - only after 10 minutes since payment."""
    # Rate limit public endpoint
    client_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    if not _check_public_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Check if dispute is already open
    if trade["status"] == "disputed":
        raise HTTPException(status_code=400, detail="Спор уже открыт")
    
    if trade["status"] != "paid":
        raise HTTPException(status_code=400, detail="Спор можно открыть только после оплаты")
    
    paid_at = trade.get("paid_at")
    if paid_at:
        paid_time = datetime.fromisoformat(paid_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        minutes_passed = (now - paid_time).total_seconds() / 60
        
        if minutes_passed < 10:
            remaining = int(10 - minutes_passed)
            raise HTTPException(status_code=400, detail=f"Спор можно открыть через {remaining} мин.")
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "disputed",
            "disputed_at": datetime.now(timezone.utc).isoformat(),
            "dispute_reason": reason or "Не указана",
            "disputed_by": "client",
            "disputed_by_role": "клиентом"
        }}
    )
    
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "is_system": True,
        "sender_role": "system",
        "content": f"⚠️ Спор открыт клиентом! Причина: {reason or 'не указана'}. Администратор подключится к чату.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Send webhook to merchant (DISPUTED)
    await send_merchant_webhook_on_trade(trade, "disputed", {
        "trade_id": trade_id,
        "reason": reason or "Не указана",
        "disputed_at": datetime.now(timezone.utc).isoformat(),
        "disputed_by": "клиентом"
    })
    
    return {"status": "disputed"}


@router.post("/trades/{trade_id}/resolve-dispute")
async def resolve_dispute(trade_id: str, resolution: str, user: dict = Depends(require_role(["admin"]))):
    """Resolve a dispute (admin only)
    - favor_client: Complete the trade (buyer gets USDT)
    - favor_trader: Cancel the trade (seller keeps USDT)
    """
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade["status"] not in ["disputed", "dispute"]:
        raise HTTPException(status_code=400, detail="Trade not in dispute")
    
    # ATOMIC: Lock the trade by updating status immediately to prevent double-resolution
    lock_result = await db.trades.update_one(
        {"id": trade_id, "status": {"$in": ["disputed", "dispute"]}},
        {"$set": {"status": "resolving"}}
    )
    if lock_result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Спор уже решается (параллельный запрос)")
    
    if resolution in ["favor_client", "refund_buyer", "favor_buyer"]:
        # Complete the trade - buyer wins, trade is completed
        new_status = "completed"
        
        # === Financial operations with rollback protection ===
        try:
            # Update offer's sold_usdt if trade was from offer
            if trade.get("offer_id"):
                await db.offers.update_one(
                    {"id": trade["offer_id"]},
                    {"$inc": {
                        "sold_usdt": trade["amount_usdt"],
                        "actual_commission": trade["trader_commission"]
                    }}
                )
        
            # Deduct commission from seller (1%)
            trader_commission_amt = trade.get("trader_commission", 0)
            if trader_commission_amt > 0:
                await db.traders.update_one(
                    {"id": trade["trader_id"]},
                    {"$inc": {"balance_usdt": -trader_commission_amt}}
                )
                now_ts = datetime.now(timezone.utc).isoformat()
                await db.transactions.insert_one({
                    "id": str(uuid.uuid4()),
                    "trader_id": trade["trader_id"],
                    "type": "commission",
                    "amount": -trader_commission_amt,
                    "description": f"Комиссия площадки 1% со сделки #{trade_id[:8]} (спор)",
                    "reference_trade_id": trade_id,
                    "created_at": now_ts
                })
        
            # Record commission payment
            await db.commission_payments.insert_one({
                "id": str(uuid.uuid4()),
                "trade_id": trade_id,
                "trader_id": trade.get("trader_id"),
                "merchant_id": trade.get("merchant_id"),
                "trader_commission": trader_commission_amt,
                "merchant_commission": trade.get("merchant_commission", 0),
                "total_commission": trade.get("total_commission", 0),
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
            # If direct P2P trade (trader-to-trader), credit USDT to buyer
            if trade.get("buyer_type") == "trader" and trade.get("buyer_id"):
                buyer_receives = trade["amount_usdt"]  # Buyer gets full amount
                await db.traders.update_one(
                    {"id": trade["buyer_id"]},
                    {"$inc": {"balance_usdt": buyer_receives}}
                )
                message = "✅ Спор разрешён в пользу покупателя. Сделка завершена, USDT зачислены на баланс."
            # If merchant trade, transfer to merchant with proper calculation
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
            
                # Record merchant deposit transaction in transactions collection
                await db.transactions.insert_one({
                    "id": str(uuid.uuid4()),
                    "tx_id": f"mtx_{trade_id[:8]}_{uuid.uuid4().hex[:6]}",
                    "user_id": trade["merchant_id"],
                    "type": "deposit",
                    "amount": merchant_receives_usdt,
                    "amount_rub": original_amount_rub,
                    "currency": "USDT",
                    "status": "completed",
                    "description": f"Пополнение от сделки #{trade_id[:8]} (спор) — {original_amount_rub:.0f} RUB ({merchant_receives_usdt:.2f} USDT)",
                    "reference_id": trade_id,
                    "trade_id": trade_id,
                    "invoice_id": trade.get("invoice_id"),
                    "merchant_id": trade["merchant_id"],
                    "is_financial_operation": True,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
            
                message = f"✅ Спор разрешён в пользу клиента. Мерчант получил {merchant_receives_rub:.0f} RUB ({merchant_receives_usdt:.2f} USDT)."
            else:
                message = "✅ Спор разрешён в пользу покупателя. Сделка завершена."
        
        except Exception as _fin_err:
            # ROLLBACK: Revert lock status on financial operation failure
            logger.error(f"[ROLLBACK] resolve_dispute {trade_id} favor_client: financial operation failed: {_fin_err}", exc_info=True)
            try:
                await db.trades.update_one(
                    {"id": trade_id},
                    {"$set": {"status": trade["status"]}}
                )
                logger.info(f"[ROLLBACK] resolve_dispute {trade_id}: status reverted to '{trade['status']}'")
            except Exception as _rb_err:
                logger.error(f"[ROLLBACK FAILED] resolve_dispute {trade_id}: could not revert status: {_rb_err}")
            raise HTTPException(status_code=500, detail="Ошибка обработки спора. Статус возвращён, попробуйте снова.")

        # Process referral bonus for completed dispute (1-level, 0.5% of sold USDT)
        try:
            from modules.social.referral import process_referral_bonus
            await process_referral_bonus(trade_id, trade["trader_id"], trade["amount_usdt"])
        except Exception as e:
            logger.warning(f"Referral bonus error (dispute) for trade {trade_id}: {e}")
            
    elif resolution in ["favor_trader", "refund_seller", "cancel"]:
        # Cancel the trade - seller wins, gets USDT back to offer or balance
        new_status = "cancelled"
        
        # === Financial operations with rollback protection ===
        try:
            # Return USDT to offer if it was a direct trade
            if trade.get("offer_id"):
                await db.offers.update_one(
                    {"id": trade["offer_id"]},
                    {"$inc": {"available_usdt": trade["amount_usdt"]}}
                )
            else:
                # Otherwise return to trader balance
                await db.traders.update_one(
                    {"id": trade["trader_id"]},
                    {"$inc": {"balance_usdt": trade["amount_usdt"]}}
                )
        
        except Exception as _fin_err:
            # ROLLBACK: Revert lock status on financial operation failure
            logger.error(f"[ROLLBACK] resolve_dispute {trade_id} favor_trader: financial operation failed: {_fin_err}", exc_info=True)
            try:
                await db.trades.update_one(
                    {"id": trade_id},
                    {"$set": {"status": trade["status"]}}
                )
                logger.info(f"[ROLLBACK] resolve_dispute {trade_id}: status reverted to '{trade['status']}'")
            except Exception as _rb_err:
                logger.error(f"[ROLLBACK FAILED] resolve_dispute {trade_id}: could not revert status: {_rb_err}")
            raise HTTPException(status_code=500, detail="Ошибка обработки спора. Статус возвращён, попробуйте снова.")

        message = "❌ Спор разрешён в пользу продавца. Сделка отменена, USDT возвращены."
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution. Use 'favor_client'/'refund_buyer' or 'favor_trader'/'refund_seller'")
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": new_status,
            "dispute_resolved_at": datetime.now(timezone.utc).isoformat(),
            "dispute_resolved_by": user["id"],
            "dispute_resolution": resolution
        }}
    )
    
    # Record status change in trade_status_history
    await db.trade_status_history.insert_one({
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "old_status": "disputed",
        "new_status": new_status,
        "changed_by": user["id"],
        "changed_by_role": "admin",
        "reason": f"dispute_resolved: {resolution}",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Update invoice status to match trade status
    if trade.get("invoice_id"):
        await db.merchant_invoices.update_one(
            {"id": trade["invoice_id"]},
            {"$set": {"status": new_status, "dispute_resolved_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    # Send system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Auto-archive the unified conversation for this dispute
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
    
    # Send webhook to merchant about dispute resolution
    resolved_trade = await db.trades.find_one({"id": trade_id}, {"_id": 0}) or trade
    payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    current_rate = payout_settings.get("base_rate", 78.5) if payout_settings else 78.5
    
    webhook_extra = {
        "trade_id": trade_id,
        "dispute_resolution": resolution,
        "resolved_at": datetime.now(timezone.utc).isoformat()
    }
    if new_status == "completed":
        webhook_extra.update({
            "amount_usdt": resolved_trade.get("amount_usdt", 0),
            "client_amount_rub": resolved_trade.get("client_amount_rub") or resolved_trade.get("original_amount_rub") or resolved_trade.get("amount_rub"),
            "merchant_receives_rub": resolved_trade.get("merchant_receives_rub") or 0,
            "merchant_receives_usdt": resolved_trade.get("merchant_receives_usdt") or 0,
            "commission_usdt": resolved_trade.get("merchant_commission") or 0,
            "rate": current_rate,
            "completed_at": datetime.now(timezone.utc).isoformat()
        })
    elif new_status == "cancelled":
        webhook_extra["reason"] = "Спор разрешён в пользу продавца"
        webhook_extra["cancelled_at"] = datetime.now(timezone.utc).isoformat()
    
    await send_merchant_webhook_on_trade(resolved_trade, new_status, webhook_extra)
    
    return {"status": new_status}



@router.get("/trades/{trade_id}/dispute-public")
async def get_dispute_public(trade_id: str, request: Request):
    """
    Публичный доступ к данным спора (для покупателей без авторизации)
    """
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    # Можно смотреть только disputed trades
    if trade["status"] not in ["disputed"]:
        raise HTTPException(status_code=403, detail="Нет доступа к данным сделки")
    
    # Получаем сообщения чата
    messages = await db.trade_messages.find(
        {"trade_id": trade_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    
    # Добавляем сообщения модераторов из dispute_chats
    dispute_messages = await db.dispute_chats.find(
        {"trade_id": trade_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    for msg in dispute_messages:
        messages.append({
            "id": msg["id"],
            "trade_id": trade_id,
            "sender_id": msg.get("sender_id"),
            "sender_type": "admin",
            "sender_role": msg.get("sender_role", "admin"),
            "content": msg.get("message"),
            "created_at": msg.get("created_at")
        })
    
    # Сортируем все сообщения по времени
    messages.sort(key=lambda x: x.get("created_at", ""))
    
    # Безопасный ответ
    return {
        "trade": {
            "id": trade["id"],
            "status": trade["status"],
            "amount_rub": trade.get("amount_rub"),
            "client_pays_rub": trade.get("client_pays_rub"),
            "amount_usdt": trade.get("amount_usdt"),
            "dispute_reason": trade.get("dispute_reason"),
            "disputed_at": trade.get("disputed_at"),
            "created_at": trade.get("created_at"),
            "dispute_resolved_at": trade.get("dispute_resolved_at"),
            "dispute_resolution": trade.get("dispute_resolution")
        },
        "messages": messages
    }


@router.get("/trades/purchases/all-history")
async def get_all_purchases_history(user: dict = Depends(require_role(["trader"]))):
    """Get combined purchase history: P2P trades + crypto buy orders"""
    trader_id = user["id"]
    result = []
    
    # 1. P2P trade purchases (where user is buyer)
    p2p_trades = await db.trades.find(
        {"buyer_id": trader_id, "buyer_type": "trader", "status": {"$in": ["completed", "cancelled"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    for t in p2p_trades:
        result.append({
            "id": t["id"],
            "trade_number": t.get("trade_number"),
            "type": "p2p",
            "amount_usdt": t.get("amount_usdt", 0),
            "amount_rub": t.get("amount_rub", 0),
            "status": t["status"],
            "seller": t.get("trader_login", ""),
            "created_at": t.get("created_at", ""),
            "completed_at": t.get("completed_at", ""),
            "chat_type": "trade"
        })
    
    # 2. Crypto buy orders
    crypto_orders = await db.crypto_orders.find(
        {"buyer_id": trader_id, "status": {"$in": ["completed", "cancelled", "pending", "paid"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    for o in crypto_orders:
        conv = await db.unified_conversations.find_one(
            {"related_id": o["id"]}, {"_id": 0, "id": 1}
        )
        result.append({
            "id": o["id"],
            "trade_number": o.get("trade_number"),
            "type": "crypto_buy",
            "amount_usdt": o.get("amount_usdt", 0),
            "amount_rub": o.get("amount_rub", 0),
            "status": o["status"],
            "seller": o.get("merchant_nickname", ""),
            "created_at": o.get("created_at", ""),
            "completed_at": o.get("completed_at", ""),
            "conversation_id": conv["id"] if conv else None,
            "chat_type": "crypto_order"
        })
    
    # Sort by created_at descending
    result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return result
