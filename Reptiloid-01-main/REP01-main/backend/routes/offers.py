"""
Offers routes - P2P trading offers management
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from core.database import db
from core.auth import require_role
from models.schemas import OfferCreate, OfferResponse

router = APIRouter(tags=["offers"])


@router.post("/offers", response_model=OfferResponse)
async def create_offer(data: OfferCreate, user: dict = Depends(require_role(["trader"]))):
    """Create a new P2P offer"""
    trader = await db.traders.find_one({"id": user["id"]}, {"_id": 0})
    
    # Check if balance is locked
    if trader.get("is_balance_locked"):
        raise HTTPException(status_code=403, detail="Ваш баланс заблокирован. Создание объявлений недоступно.")
    
    # Get commission settings
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    commission_rate = settings.get("trader_commission", 1.0) if settings else 1.0
    
    # Calculate reserved commission (1% of offer amount)
    reserved_commission = data.amount_usdt * (commission_rate / 100)
    total_to_reserve = data.amount_usdt + reserved_commission
    
    # Check balance (amount + commission)
    if trader["balance_usdt"] < total_to_reserve:
        raise HTTPException(status_code=400, detail=f"Недостаточно средств. Нужно: {total_to_reserve:.2f} USDT (включая {commission_rate}% комиссии). Баланс: {trader['balance_usdt']:.2f} USDT")
    
    # Validate requisites - only one per type allowed
    requisites = []
    requisite_types = set()
    if data.requisite_ids:
        for req_id in data.requisite_ids:
            req = await db.requisites.find_one({"id": req_id, "trader_id": user["id"]}, {"_id": 0})
            if req:
                if req["type"] in requisite_types:
                    raise HTTPException(status_code=400, detail=f"Можно выбрать только один реквизит типа '{req['type']}'")
                requisite_types.add(req["type"])
                requisites.append(req)
    
    # Get trader's trade stats
    trades_count = await db.trades.count_documents({"trader_id": user["id"], "status": "completed"})
    total_trades = await db.trades.count_documents({"trader_id": user["id"]})
    success_rate = (trades_count / total_trades * 100) if total_trades > 0 else 100.0
    
    # Validate min/max amounts
    min_amount = data.min_amount if data.min_amount else 1.0
    max_amount = data.max_amount if data.max_amount else data.amount_usdt
    
    if min_amount < 1.0:
        raise HTTPException(status_code=400, detail="Минимальная сумма не может быть меньше 1 USDT")
    if max_amount > data.amount_usdt:
        raise HTTPException(status_code=400, detail="Максимальная сумма не может превышать сумму к продаже")
    if min_amount > max_amount:
        raise HTTPException(status_code=400, detail="Минимальная сумма не может превышать максимальную")
    
    offer_doc = {
        "id": str(uuid.uuid4()),
        "trader_id": user["id"],
        "trader_login": trader["login"],
        "amount_usdt": data.amount_usdt,
        "available_usdt": data.amount_usdt,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "price_rub": data.price_rub,
        "payment_methods": data.payment_methods,
        "accepted_merchant_types": data.accepted_merchant_types,
        "requisite_ids": data.requisite_ids or [],
        "requisites": requisites,
        "conditions": data.conditions,
        "is_active": True,
        "trades_count": trades_count,
        "success_rate": round(success_rate, 1),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commission_rate": commission_rate,
        "reserved_commission": round(reserved_commission, 4),
        "sold_usdt": 0.0,
        "actual_commission": 0.0
    }
    
    # Reserve funds from trader balance
    await db.traders.update_one(
        {"id": user["id"]},
        {"$inc": {"balance_usdt": -total_to_reserve}}
    )
    
    await db.offers.insert_one(offer_doc)
    return offer_doc


def _normalize_offer(offer: dict) -> dict:
    """Ensure offer has all required fields"""
    if "amount_usdt" not in offer:
        offer["amount_usdt"] = offer.get("max_amount", 0)
    if "available_usdt" not in offer:
        offer["available_usdt"] = offer.get("max_amount", 0)
    if "min_amount" not in offer:
        offer["min_amount"] = 1.0
    if "max_amount" not in offer:
        offer["max_amount"] = offer.get("amount_usdt", 0)
    # Clean _id from embedded requisites
    if offer.get("requisites"):
        offer["requisites"] = [{k: v for k, v in req.items() if k != "_id"} for req in offer["requisites"]]
    return offer


@router.get("/offers", response_model=List[OfferResponse])
async def get_offers(
    merchant_type: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    payment_method: Optional[str] = None,
    sort_by: Optional[str] = "price"
):
    """Get active offers with filters"""
    query = {"is_active": True, "available_usdt": {"$gt": 0}}
    
    if merchant_type:
        query["accepted_merchant_types"] = merchant_type
    
    if payment_method:
        query["payment_methods"] = payment_method
    
    if min_amount:
        query["available_usdt"] = {"$gte": min_amount}
    if max_amount:
        if "available_usdt" in query:
            query["available_usdt"]["$lte"] = max_amount
        else:
            query["available_usdt"] = {"$lte": max_amount}
    
    sort_field = "price_rub"
    sort_order = 1
    if sort_by == "amount":
        sort_field = "available_usdt"
        sort_order = -1
    elif sort_by == "rating":
        sort_field = "success_rate"
        sort_order = -1
    
    offers = await db.offers.find(query, {"_id": 0}).sort(sort_field, sort_order).to_list(100)
    
    for offer in offers:
        if offer.get("requisite_ids"):
            requisites = []
            for req_id in offer["requisite_ids"]:
                req = await db.requisites.find_one({"id": req_id}, {"_id": 0})
                if req:
                    requisites.append(req)
            offer["requisites"] = requisites
        
        offer = _normalize_offer(offer)
        
        # Add online status
        trader = await db.traders.find_one({"id": offer.get("trader_id")}, {"_id": 0, "last_seen": 1})
        if trader and trader.get("last_seen"):
            try:
                last_seen = datetime.fromisoformat(trader["last_seen"].replace("Z", "+00:00"))
                diff_minutes = (datetime.now(timezone.utc) - last_seen).total_seconds() / 60
                offer["is_online"] = diff_minutes < 5
            except:
                offer["is_online"] = False
        else:
            offer["is_online"] = False
    
    return offers


@router.get("/offers/my", response_model=List[OfferResponse])
async def get_my_offers(user: dict = Depends(require_role(["trader"]))):
    """Get current trader's offers"""
    offers = await db.offers.find({"trader_id": user["id"]}, {"_id": 0}).to_list(100)
    return [_normalize_offer(offer) for offer in offers]


@router.get("/public/offers")
async def get_public_offers(
    payment_method: Optional[str] = None,
    currency: Optional[str] = "RUB",
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    sort_by: Optional[str] = "price"
):
    """Public order book endpoint - no auth required"""
    query = {"is_active": True, "available_usdt": {"$gt": 0}}
    
    if payment_method and payment_method != "all":
        query["payment_methods"] = payment_method
    
    if min_amount:
        query["available_usdt"] = {"$gte": min_amount}
    if max_amount:
        if "available_usdt" in query:
            query["available_usdt"]["$lte"] = max_amount
        else:
            query["available_usdt"] = {"$lte": max_amount}
    
    sort_field = "price_rub"
    sort_order = 1
    if sort_by == "amount":
        sort_field = "available_usdt"
        sort_order = -1
    elif sort_by == "rating":
        sort_field = "success_rate"
        sort_order = -1
    
    offers = await db.offers.find(query, {"_id": 0}).sort(sort_field, sort_order).to_list(100)
    
    for offer in offers:
        # Clean _id from embedded requisites
        if offer.get("requisites"):
            offer["requisites"] = [{k: v for k, v in req.items() if k != "_id"} for req in offer["requisites"]]
        
        if offer.get("requisite_ids"):
            requisites = []
            for req_id in offer["requisite_ids"]:
                req = await db.requisites.find_one({"id": req_id}, {"_id": 0})
                if req:
                    requisites.append(req)
            offer["requisites"] = requisites
        
        offer = _normalize_offer(offer)
        
        # Add trader info
        trader = await db.traders.find_one({"id": offer.get("trader_id")}, {"_id": 0, "last_seen": 1, "display_name": 1, "login": 1})
        if trader:
            offer["trader_display_name"] = trader.get("display_name") or offer.get("trader_login", "")
            if trader.get("last_seen"):
                try:
                    last_seen = datetime.fromisoformat(trader["last_seen"].replace("Z", "+00:00"))
                    diff_minutes = (datetime.now(timezone.utc) - last_seen).total_seconds() / 60
                    offer["is_online"] = diff_minutes < 5
                except:
                    offer["is_online"] = False
            else:
                offer["is_online"] = False
        else:
            offer["trader_display_name"] = offer.get("trader_login", "")
            offer["is_online"] = False
    
    return offers


@router.delete("/offers/{offer_id}")
async def delete_offer(offer_id: str, user: dict = Depends(require_role(["trader"]))):
    """Delete an offer and refund unused funds"""
    offer = await db.offers.find_one({"id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    if offer["trader_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your offer")
    
    # Calculate refund
    available_usdt = offer.get("available_usdt", 0)
    reserved_commission = offer.get("reserved_commission", 0)
    sold_usdt = offer.get("sold_usdt", 0)
    commission_rate = offer.get("commission_rate", 1.0)
    
    correct_commission = sold_usdt * (commission_rate / 100)
    commission_refund = reserved_commission - correct_commission
    total_refund = available_usdt + max(0, commission_refund)
    
    if total_refund > 0:
        await db.traders.update_one(
            {"id": user["id"]},
            {"$inc": {"balance_usdt": total_refund}}
        )
    
    await db.offers.update_one({"id": offer_id}, {"$set": {"is_active": False}})
    
    return {
        "status": "deleted",
        "returned_usdt": round(available_usdt, 4),
        "commission_refund": round(max(0, commission_refund), 4),
        "total_refund": round(total_refund, 4),
        "sold_usdt": round(sold_usdt, 4),
        "actual_commission_paid": round(correct_commission, 4)
    }
