"""
Trades routes - P2P trade management
Full business logic including commissions, referrals, and disputes
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pydantic import BaseModel
import uuid
from bson import ObjectId

from core.database import db
from core.auth import require_role, get_current_user
from core.websocket import manager

try:
    from routes.ws_routes import ws_manager
except ImportError:
    ws_manager = None

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
        # Try Invoice API webhook first (new system)
        if trade.get("invoice_id"):
            from routes.invoice_api import send_webhook_notification
            
            # Sync invoice status with trade status
            await db.merchant_invoices.update_one(
                {"id": trade["invoice_id"]},
                {"$set": {
                    "status": status,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            await send_webhook_notification(trade["invoice_id"], status, extra_data)
            return
        
        # Fallback to old merchant_api webhook
        from routes.merchant_api import send_merchant_webhook
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


async def _create_trade_notification(user_id: str, notif_type: str, title: str, message: str, link: str = None, trade_id: str = None):
    """Create a trade event notification in both collections"""
    # Legacy notifications collection
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "link": link,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    # New event_notifications collection
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
    # Clean requisites from any MongoDB ObjectId leftovers
    requisites = [_clean_doc(r) for r in requisites]
    
    trade_doc = {
        "id": trade_id,
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
    
    # Reserve funds
    if data.offer_id:
        await db.offers.update_one(
            {"id": data.offer_id},
            {"$inc": {"available_usdt": -data.amount_usdt}}
        )
    else:
        await db.traders.update_one(
            {"id": data.trader_id},
            {"$inc": {"balance_usdt": -data.amount_usdt}}
        )
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
    
    auto_msg_content = f"📋 Сделка #{trade_id} создана\n\n"
    auto_msg_content += f"💰 Сумма к оплате: {trade_doc['amount_rub']:,.0f} ₽\n"
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
    """Get active purchases where current trader is the buyer"""
    trades = await db.trades.find(
        {
            "buyer_id": user["id"],
            "buyer_type": "trader",
            "status": {"$in": ["pending", "paid", "disputed"]}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Enrich with seller info
    for trade in trades:
        seller = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0, "login": 1, "nickname": 1})
        if seller:
            trade["trader_login"] = seller.get("login", "")
            trade["trader_nickname"] = seller.get("nickname", seller.get("login", ""))
    
    return [_clean_doc(t) for t in trades]


@router.get("/trades/sales/active")
async def get_trader_active_sales(user: dict = Depends(require_role(["trader"]))):
    """Get active sales where current trader is the seller"""
    trades = await db.trades.find(
        {"trader_id": user["id"], "status": {"$in": ["pending", "paid", "disputed"]}},
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
    """Get completed/cancelled sales where current trader was the seller"""
    trades = await db.trades.find(
        {
            "trader_id": user["id"],
            "status": {"$in": ["completed", "cancelled"]}
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
    """Get completed/cancelled purchases where current trader was the buyer"""
    trades = await db.trades.find(
        {
            "buyer_id": user["id"],
            "buyer_type": "trader",
            "status": {"$in": ["completed", "cancelled", "refunded"]}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Enrich with seller info
    for trade in trades:
        seller = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0, "login": 1, "nickname": 1})
        if seller:
            trade["trader_login"] = seller.get("login", "")
            trade["trader_nickname"] = seller.get("nickname", seller.get("login", ""))
    
    return [_clean_doc(t) for t in trades]


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
    
    # Update trade status
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": "completed",
            "completed_at": now
        }}
    )
    
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
    
    # Process referral earnings
    referral_rate = 0.005  # 0.5%
    referral_amount = trade["amount_usdt"] * referral_rate
    
    # Case 1: Trader (seller) is referred → their referrer earns from sales
    seller = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0})
    if seller and seller.get("referred_by"):
        referrer = await db.traders.find_one({"id": seller["referred_by"]}, {"_id": 0})
        if referrer:
            await db.traders.update_one(
                {"id": seller["referred_by"]},
                {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
            )
            await db.transactions.insert_one({
                "id": str(uuid.uuid4()),
                "trader_id": seller["referred_by"],
                "type": "referral_bonus",
                "amount": referral_amount,
                "description": f"Реферальный бонус от сделки #{trade_id[:8]}",
                "from_platform": True,
                "reference_trade_id": trade_id,
                "referred_user_id": seller["id"],
                "created_at": now
            })
        else:
            # Check if referrer is merchant
            referrer = await db.merchants.find_one({"id": seller["referred_by"]}, {"_id": 0})
            if referrer:
                await db.merchants.update_one(
                    {"id": seller["referred_by"]},
                    {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                )
                await db.transactions.insert_one({
                    "id": str(uuid.uuid4()),
                    "merchant_id": seller["referred_by"],
                    "type": "referral_bonus",
                    "amount": referral_amount,
                    "description": f"Реферальный бонус от сделки #{trade_id[:8]}",
                    "from_platform": True,
                    "reference_trade_id": trade_id,
                    "referred_user_id": seller["id"],
                    "created_at": now
                })
    
    # Case 2: Merchant is referred → their referrer earns from purchases
    if trade.get("merchant_id"):
        merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0})
        if merchant and merchant.get("referred_by"):
            referrer = await db.traders.find_one({"id": merchant["referred_by"]}, {"_id": 0})
            if referrer:
                await db.traders.update_one(
                    {"id": merchant["referred_by"]},
                    {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                )
                await db.transactions.insert_one({
                    "id": str(uuid.uuid4()),
                    "trader_id": merchant["referred_by"],
                    "type": "referral_bonus",
                    "amount": referral_amount,
                    "description": f"Реферальный бонус от сделки #{trade_id[:8]}",
                    "from_platform": True,
                    "reference_trade_id": trade_id,
                    "referred_user_id": merchant["id"],
                    "created_at": now
                })
            else:
                referrer = await db.merchants.find_one({"id": merchant["referred_by"]}, {"_id": 0})
                if referrer:
                    await db.merchants.update_one(
                        {"id": merchant["referred_by"]},
                        {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                    )
                    await db.transactions.insert_one({
                        "id": str(uuid.uuid4()),
                        "merchant_id": merchant["referred_by"],
                        "type": "referral_bonus",
                        "amount": referral_amount,
                        "description": f"Реферальный бонус от сделки #{trade_id[:8]}",
                        "from_platform": True,
                        "reference_trade_id": trade_id,
                        "referred_user_id": merchant["id"],
                        "created_at": now
                    })
    
    # Process multi-level referral bonuses (3 levels: 5%, 3%, 1%)
    # Based on trader's commission from the trade
    trader_commission = trade.get("trader_commission", 0)
    if trader_commission > 0:
        try:
            from routes.referral import process_referral_bonus
            await process_referral_bonus(trade["trader_id"], trader_commission)
        except Exception as e:
            # Log but don't fail the trade
            print(f"Referral bonus error: {e}")
    
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
        completion_text = f"✅ Сделка завершена! Продавец подтвердил получение оплаты. {trade['amount_usdt']} USDT переведены покупателю."
    
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
    
    # Also notify buyer directly
    if trade.get("buyer_id"):
        await _ws_broadcast(f"user_{trade['buyer_id']}", {
            "type": "trade_completed",
            "trade_id": trade_id,
            "amount_usdt": trade["amount_usdt"],
            "status": "completed"
        })
    
    # Send webhook to merchant (COMPLETED)
    # Re-read trade to get freshly calculated merchant_receives_usdt
    updated_trade = await db.trades.find_one({"id": trade_id}, {"_id": 0}) or trade
    # Get base_rate for webhook (may have been calculated above for merchant trades)
    payout_settings_for_wh = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    wh_base_rate = payout_settings_for_wh.get("base_rate", 78.5) if payout_settings_for_wh else 78.5
    await send_merchant_webhook_on_trade(updated_trade, "completed", {
        "trade_id": trade_id,
        "amount_usdt": updated_trade.get("amount_usdt", trade["amount_usdt"]),
        "client_amount_rub": updated_trade.get("client_amount_rub"),
        "merchant_receives_rub": updated_trade.get("merchant_receives_rub"),
        "merchant_receives_usdt": updated_trade.get("merchant_receives_usdt"),
        "rate": wh_base_rate,
        "merchant_amount_usdt": updated_trade.get("merchant_receives_usdt"),
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
    
    return {"status": "completed"}


@router.post("/trades/{trade_id}/mark-paid")
async def mark_trade_paid(trade_id: str):
    """Mark a trade as paid by customer (no auth required for customer)"""
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
    
    # Send system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": f"✅ Клиент подтвердил оплату {trade['amount_rub']:,.0f} ₽. Трейдер, проверьте поступление средств на ваши реквизиты.",
        "created_at": now
    }
    await db.trade_messages.insert_one(system_msg)
    
    # Broadcast via WebSocket to trade channel
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in system_msg.items() if k != "_id"}})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "status_update", "status": "paid", "trade_id": trade_id})
    
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
            message=f"Клиент оплатил сделку на {trade['amount_rub']:,.0f} \u20bd",
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
    
    # Send webhook to merchant (CANCELLED)
    await send_merchant_webhook_on_trade(trade, "cancelled", {
        "trade_id": trade_id,
        "reason": "Клиент не оплатил в течение 30 минут",
        "cancelled_at": now.isoformat()
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
async def get_trade_public(trade_id: str):
    """Get trade details - public endpoint for client"""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    return {
        "id": trade["id"],
        "amount_usdt": trade["amount_usdt"],
        "amount_rub": trade["amount_rub"],
        "price_rub": trade["price_rub"],
        "status": trade["status"],
        "requisites": trade.get("requisites", []),
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
async def get_trade_messages_public(trade_id: str):
    """Get trade messages - public endpoint for client"""
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
    
    # Determine sender type
    if user["role"] == "admin":
        sender_type = "admin"
    elif user["role"] == "merchant":
        sender_type = "merchant"
    elif user["role"] == "trader":
        if trade["trader_id"] == user["id"]:
            sender_type = "trader"
        elif trade.get("buyer_id") == user["id"]:
            sender_type = "buyer"
        else:
            sender_type = "trader"
    else:
        sender_type = "client"
    
    msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": user["id"],
        "sender_type": sender_type,
        "sender_role": user.get("role", "trader"),
        "sender_nickname": user.get("nickname", user.get("login", "")),
        "content": data.content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.trade_messages.insert_one(msg)
    await manager.broadcast(f"trade_{trade_id}", {k: v for k, v in msg.items() if k != "_id"})
    await _ws_broadcast(f"trade_{trade_id}", {"type": "message", **{k: v for k, v in msg.items() if k != "_id"}})
    
    # Create notification for the other participant about new message
    try:
        notify_id = None
        if trade["trader_id"] != user["id"]:
            notify_id = trade["trader_id"]
        elif trade.get("buyer_id") and trade["buyer_id"] != user["id"]:
            notify_id = trade["buyer_id"]
        if notify_id:
            await _create_trade_notification(
                user_id=notify_id,
                notif_type="trade_message",
                title="Сообщение в сделке",
                message=f"Новое сообщение в сделке #{trade_id[:8]}",
                link=f"/trader/sales/{trade_id}"
            )
    except Exception:
        pass
    
    return {k: v for k, v in msg.items() if k != "_id"}


@router.post("/trades/{trade_id}/messages-public")
async def send_trade_message_public(trade_id: str, data: MessageCreate):
    """Send message as client (no auth) to trade chat"""
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
    print(f"DEBUG TRADES.PY: GET /trades called, role={user.get('role')}")
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
    
    await db.trades.insert_one(trade_doc)
    
    # Reserve USDT from offer
    await db.offers.update_one(
        {"id": offer["id"]},
        {"$inc": {"available_usdt": -data.amount_usdt}}
    )
    
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
    
    # Client can cancel at any active status
    if trade["status"] in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Сделка уже завершена или отменена.")
    
    # Return funds
    if trade.get("offer_id"):
        # Trade from offer - return to offer's available_usdt
        await db.offers.update_one(
            {"id": trade["offer_id"]},
            {"$inc": {"available_usdt": trade["amount_usdt"]}}
        )
    else:
        # Direct trade - return to trader's balance
        await db.traders.update_one(
            {"id": trade["trader_id"]},
            {"$inc": {"balance_usdt": trade["amount_usdt"]}}
        )
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat(), "cancelled_by": "client"}}
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
async def open_dispute_public(trade_id: str, reason: str = ""):
    """Open a dispute by client (no auth) - only after 10 minutes since payment."""
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
    
    if resolution in ["favor_client", "refund_buyer", "favor_buyer"]:
        # Complete the trade - buyer wins, trade is completed
        new_status = "completed"
        
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
            message = f"✅ Спор разрешён в пользу клиента. Мерчант получил {merchant_receives_rub:.0f} RUB ({merchant_receives_usdt:.2f} USDT)."
        else:
            message = "✅ Спор разрешён в пользу покупателя. Сделка завершена."
        
        # Process referral earnings for completed dispute
        referral_rate = 0.005  # 0.5%
        referral_amount = trade["amount_usdt"] * referral_rate
        
        # Case 1: Trader (seller) is referred → their referrer earns from sales
        seller = await db.traders.find_one({"id": trade["trader_id"]}, {"_id": 0})
        if seller and seller.get("referred_by"):
            referrer = await db.traders.find_one({"id": seller["referred_by"]}, {"_id": 0})
            if referrer:
                await db.traders.update_one(
                    {"id": seller["referred_by"]},
                    {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                )
            else:
                referrer = await db.merchants.find_one({"id": seller["referred_by"]}, {"_id": 0})
                if referrer:
                    await db.merchants.update_one(
                        {"id": seller["referred_by"]},
                        {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                    )
        
        # Case 2: Merchant (whose client is buying) is referred → their referrer earns from purchases
        if trade.get("merchant_id"):
            merchant = await db.merchants.find_one({"id": trade["merchant_id"]}, {"_id": 0})
            if merchant and merchant.get("referred_by"):
                referrer = await db.traders.find_one({"id": merchant["referred_by"]}, {"_id": 0})
                if referrer:
                    await db.traders.update_one(
                        {"id": merchant["referred_by"]},
                        {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                    )
                else:
                    referrer = await db.merchants.find_one({"id": merchant["referred_by"]}, {"_id": 0})
                    if referrer:
                        await db.merchants.update_one(
                            {"id": merchant["referred_by"]},
                            {"$inc": {"referral_earnings": referral_amount, "balance_usdt": referral_amount}}
                        )
            
    elif resolution in ["favor_trader", "refund_seller", "cancel"]:
        # Cancel the trade - seller wins, gets USDT back to offer or balance
        new_status = "cancelled"
        
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
    
    return {"status": new_status}



@router.get("/trades/{trade_id}/dispute-public")
async def get_dispute_public(trade_id: str):
    """
    Публичный доступ к данным спора (для покупателей без авторизации)
    """
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    # Можно смотреть только disputed или resolved trades
    if trade["status"] not in ["disputed", "completed", "cancelled"]:
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
            "amount_usdt": trade.get("amount_usdt"),
            "dispute_reason": trade.get("dispute_reason"),
            "disputed_at": trade.get("disputed_at"),
            "created_at": trade.get("created_at"),
            "dispute_resolved_at": trade.get("dispute_resolved_at"),
            "dispute_resolution": trade.get("dispute_resolution")
        },
        "messages": messages
    }
