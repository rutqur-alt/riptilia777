from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
import uuid
from typing import List

from core.database import db
from core.auth import require_role, get_current_user
from models.schemas import TradeCreate, TradeResponse
from .utils import (
    _ws_broadcast, 
    send_merchant_webhook_on_trade, 
    _create_trade_notification,
    _payment_detail_to_requisite,
    _is_legacy_requisite,
    _clean_doc
)

router = APIRouter()

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
            "status": {"$in": ["completed", "cancelled", "refunded", "disputed"]}
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
    # Special handling for QR aggregator trades
    if trade_id.startswith("trd_") and user.get("role") == "qr_provider":
        # Redirect to QR aggregator logic if needed, but for now check if it's in trades collection
        pass

    trade = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    
    # If not found in trades, check if it's a QR aggregator trade that might be stored differently
    # But currently all trades should be in trades collection
    
    if not trade:
        # Check if it's a QR trade that might be only in qr_provider_operations (should not happen for normal flow)
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Check access - allow seller (trader_id), buyer (buyer_id), merchant (merchant_id), or admin/moderator
    user_id = user["id"]
    user_role = user.get("role", "")
    
    is_seller = trade.get("trader_id") == user_id
    is_buyer = trade.get("buyer_id") == user_id
    is_merchant = trade.get("merchant_id") == user_id
    is_admin = user_role in ["admin", "mod_p2p", "owner", "super_admin"]
    
    # Special case for QR provider viewing their trades
    is_qr_provider = False
    if user_role == "qr_provider":
        # Check if this trade is linked to this provider
        # This might require checking qr_provider_operations collection
        op = await db.qr_provider_operations.find_one({"trade_id": trade_id, "provider_id": user_id})
        if op:
            is_qr_provider = True
            
    if not (is_seller or is_buyer or is_merchant or is_admin or is_qr_provider):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Add seller_login for buyer view
    if is_buyer:
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

from .utils import DirectTradeCreate

@router.post("/trades/direct")
async def create_direct_trade(data: DirectTradeCreate, user: dict = Depends(require_role(["trader"]))):
    """Create a direct P2P trade between traders (buyer and seller)"""
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {"trader_commission": 1.0, "minimum_commission": 0.01}
    
    # Get the offer
    offer = await db.offers.find_one({"id": data.offer_id, "is_active": True}, {"_id": 0})
    if not offer:
        # Check if it's a QR aggregator offer
        if data.offer_id.startswith("qr_aggregator"):
             # Redirect to QR aggregator logic - client should use /qr-aggregator/buy
             # But if they called this endpoint, we should handle it or return error
             raise HTTPException(status_code=400, detail="Please use /api/qr-aggregator/buy for QR aggregator offers")
        
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
