"""
Trades routes - P2P trade management
Full business logic including commissions, referrals, and disputes
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pydantic import BaseModel
import uuid

from core.database import db
from core.auth import require_role, get_current_user
from core.websocket import manager
from models.schemas import TradeCreate, TradeResponse, MessageCreate, MessageResponse

router = APIRouter(tags=["trades"])


class DirectTradeCreate(BaseModel):
    offer_id: str
    amount_usdt: float
    requisite_id: str


@router.post("/trades", response_model=TradeResponse)
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
    
    amount_rub = data.amount_usdt * data.price_rub
    trader_commission = data.amount_usdt * (settings["trader_commission"] / 100)
    trader_commission = max(trader_commission, settings["minimum_commission"])
    
    merchant_commission = 0.0
    merchant_id = None
    
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
    
    if not requisite_ids and data.offer_id and offer and offer.get("requisite_ids"):
        requisite_ids = offer["requisite_ids"]
    
    if not requisite_ids:
        all_trader_requisites = await db.requisites.find(
            {"trader_id": data.trader_id}, {"_id": 0}
        ).to_list(100)
        requisites = all_trader_requisites
        requisite_ids = [r["id"] for r in requisites]
    else:
        for req_id in requisite_ids:
            req = await db.requisites.find_one({"id": req_id}, {"_id": 0})
            if req:
                requisites.append(req)
    
    trade_id = f"trd_{uuid.uuid4().hex[:8]}"
    trade_doc = {
        "id": trade_id,
        "amount_usdt": data.amount_usdt,
        "price_rub": data.price_rub,
        "amount_rub": round(amount_rub, 2),
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
    
    # Build auto-message
    offer_conditions = ""
    if data.offer_id and offer and offer.get("conditions"):
        offer_conditions = offer["conditions"]
    
    req_text = ""
    for req in requisites:
        if req["type"] == "card":
            req_text += f"\n💳 {req['data'].get('bank_name', 'Карта')}: {req['data'].get('card_number', '')}"
            if req['data'].get('card_holder'):
                req_text += f"\nПолучатель: {req['data']['card_holder']}"
        elif req["type"] == "sbp":
            req_text += f"\n⚡ СБП {req['data'].get('bank_name', '')}: {req['data'].get('phone', '')}"
        elif req["type"] == "sim":
            req_text += f"\n📞 {req['data'].get('operator', 'SIM')}: {req['data'].get('phone', '')}"
    
    auto_msg_content = f"📋 Сделка #{trade_id[:12]} создана\n\n"
    auto_msg_content += f"💰 Сумма к оплате: {trade_doc['amount_rub']:,.0f} ₽\n"
    auto_msg_content += f"📈 Курс: {trade_doc['price_rub']} ₽/USDT\n"
    auto_msg_content += "⏱ Время на оплату: 30 минут\n"
    
    if offer_conditions:
        auto_msg_content += f"\n📝 Правила продавца:\n{offer_conditions}\n"
    
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
    
    return trades


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
    return trades


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
    
    return trades


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
    
    return trades


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
    # If merchant trade, transfer to merchant
    elif trade.get("merchant_id"):
        merchant_receives = trade["amount_usdt"] - trade.get("merchant_commission", 0)
        await db.merchants.update_one(
            {"id": trade["merchant_id"]},
            {"$inc": {
                "balance_usdt": merchant_receives,
                "total_commission_paid": trade.get("merchant_commission", 0)
            }}
        )
        
        # Update payment link status
        if trade.get("payment_link_id"):
            await db.payment_links.update_one(
                {"id": trade["payment_link_id"]},
                {"$set": {"status": "completed"}}
            )
    
    # Record commission
    commission_doc = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "merchant_id": trade.get("merchant_id"),
        "buyer_id": trade.get("buyer_id"),
        "trader_commission": trade.get("trader_commission", 0),
        "merchant_commission": trade.get("merchant_commission", 0),
        "total_commission": trade.get("total_commission", 0),
        "created_at": now
    }
    await db.commission_payments.insert_one(commission_doc)
    
    # Update offer's sold_usdt and actual_commission
    if trade.get("offer_id"):
        await db.offers.update_one(
            {"id": trade["offer_id"]},
            {"$inc": {
                "sold_usdt": trade["amount_usdt"],
                "actual_commission": trade.get("trader_commission", 0)
            }}
        )
    
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
    
    await db.trades.update_one(
        {"id": trade_id},
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
    return trades


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
    
    # Populate requisites
    if trade.get("requisite_ids"):
        requisites = []
        for req_id in trade["requisite_ids"]:
            req = await db.requisites.find_one({"id": req_id}, {"_id": 0})
            if req:
                requisites.append(req)
        trade["requisites"] = requisites
    elif trade.get("requisite"):
        trade["requisites"] = [trade["requisite"]]
    elif not trade.get("requisites"):
        seller_requisites = await db.requisites.find(
            {"trader_id": trade["trader_id"]}, 
            {"_id": 0}
        ).to_list(20)
        if seller_requisites:
            trade["requisites"] = seller_requisites
    
    return trade


# ==================== DIRECT TRADES & DISPUTES ====================

@router.post("/trades/direct", response_model=TradeResponse)
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
    
    # Get requisite
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
    
    return trade_doc


@router.post("/trades/{trade_id}/cancel-client")
async def cancel_trade_client(trade_id: str):
    """Client can cancel trade ONLY before marking as paid (status=pending)."""
    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Client can ONLY cancel if they haven't marked as paid yet
    if trade["status"] != "pending":
        raise HTTPException(status_code=400, detail="Отменить можно только до оплаты. После оплаты откройте диспут.")
    
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
    
    return {"status": "cancelled"}


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
    
    # Trader can open dispute immediately, client after 10 minutes
    is_seller = user and user.get("role") == "trader" and user.get("id") == trade.get("trader_id")
    is_buyer = user and user.get("role") == "trader" and user.get("id") == trade.get("buyer_id")
    
    if not is_seller:
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
            "disputed_by": user.get("id") if user else "client"
        }}
    )
    
    # Send system message
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": f"⚠️ Спор открыт {opener}! Причина: {reason or 'не указана'}. Администратор подключится к чату.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
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
            "disputed_by": "client"
        }}
    )
    
    system_msg = {
        "id": str(uuid.uuid4()),
        "trade_id": trade_id,
        "sender_id": "system",
        "sender_type": "system",
        "content": f"⚠️ Спор открыт покупателем! Причина: {reason or 'не указана'}. Администратор подключится к чату.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.trade_messages.insert_one(system_msg)
    
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
    if trade["status"] != "disputed":
        raise HTTPException(status_code=400, detail="Trade not in dispute")
    
    if resolution == "favor_client":
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
        
        # If direct P2P trade (trader-to-trader), credit USDT to buyer
        if trade.get("buyer_type") == "trader" and trade.get("buyer_id"):
            buyer_receives = trade["amount_usdt"]  # Buyer gets full amount
            await db.traders.update_one(
                {"id": trade["buyer_id"]},
                {"$inc": {"balance_usdt": buyer_receives}}
            )
            message = "✅ Спор разрешён в пользу покупателя. Сделка завершена, USDT зачислены на баланс."
        # If merchant trade, transfer to merchant
        elif trade.get("merchant_id"):
            merchant_receives = trade["amount_usdt"] - trade.get("merchant_commission", 0)
            await db.merchants.update_one(
                {"id": trade["merchant_id"]},
                {"$inc": {
                    "balance_usdt": merchant_receives,
                    "total_commission_paid": trade.get("merchant_commission", 0)
                }}
            )
            message = "✅ Спор разрешён в пользу клиента. Сделка завершена, USDT зачислены."
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
            
    elif resolution == "favor_trader":
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
        raise HTTPException(status_code=400, detail="Invalid resolution. Use 'favor_client' or 'favor_trader'")
    
    await db.trades.update_one(
        {"id": trade_id},
        {"$set": {
            "status": new_status,
            "dispute_resolved_at": datetime.now(timezone.utc).isoformat(),
            "dispute_resolved_by": user["id"],
            "dispute_resolution": resolution
        }}
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
