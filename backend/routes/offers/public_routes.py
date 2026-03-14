
from fastapi import APIRouter, Query
from typing import List, Optional
from core.database import db
from bson import ObjectId
import logging
import math

from .models import OfferResponse
from .utils import get_payment_details_for_offer, get_trader_nickname
from routes.qr_aggregator.utils import get_base_rate

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/offers")
async def get_public_offers(
    type: str = Query(..., description="buy or sell"),
    cryptocurrency: str = Query("USDT"),
    fiat_currency: str = Query("RUB"),
    amount: Optional[float] = None,
    payment_method: Optional[str] = None,
    sort_by: Optional[str] = None
):
    query = {
        "type": type,
        "is_active": True,
        "available_usdt": {"$gt": 0}
    }
    
    if payment_method and payment_method != "all":
        query["payment_methods"] = payment_method
    
    sort_field = "price_rub"
    sort_dir = 1 if type == "sell" else -1
    if sort_by:
        if ":" in sort_by:
            parts = sort_by.split(":")
            sort_field = parts[0]
            sort_dir = int(parts[1]) if len(parts) > 1 else 1
        elif sort_by.startswith("-"):
            sort_field = sort_by[1:]
            sort_dir = -1
        else:
            sort_field = sort_by
        if sort_field == "price":
            sort_field = "price_rub"
        
    cursor = db.offers.find(query).sort(sort_field, sort_dir)
    offers = await cursor.to_list(length=100)
    
    result = []
    for offer in offers:
        if amount:
            min_limit = offer.get("min_amount", 0)
            max_limit = offer.get("max_amount", float("inf"))
            if not (min_limit <= amount <= max_limit):
                continue
                
        offer["id"] = str(offer["_id"])
        del offer["_id"]
        offer["trader_nickname"] = await get_trader_nickname(offer["trader_id"])
        
        if offer.get("payment_detail_ids"):
            offer["payment_details"] = await get_payment_details_for_offer(offer["payment_detail_ids"])
            
        result.append(offer)
        
    if type == "sell" and cryptocurrency == "USDT" and fiat_currency == "RUB":
        try:
            from routes.qr_aggregator.trading_routes import get_qr_aggregator_offers
            qr_offers = await get_qr_aggregator_offers(amount)
            result.extend(qr_offers)
        except Exception as e:
            logger.error(f"Error fetching QR offers: {e}")
            
    return result

@router.get("/operators")
async def get_operators_for_payment(
    amount_rub: float = Query(..., gt=0),
    method: Optional[str] = None
):
    query = {
        "type": "sell",
        "is_active": True,
        "available_usdt": {"$gt": 0}
    }
    
    if method and method != "all":
        if method == "sbp":
            query["payment_methods"] = {"$in": ["SBP", "sbp"]}
        elif method == "card":
            query["payment_methods"] = {"$in": ["Card", "card", "bank_card"]}
    
    cursor = db.offers.find(query).sort("price_rub", 1)
    p2p_offers = await cursor.to_list(length=100)
    
    result = []
    base_rate = await get_base_rate()
    
    for offer in p2p_offers:
        price_rub = offer.get("price_rub", base_rate)
        available_usdt = offer.get("available_usdt", 0)
        min_amount = offer.get("min_amount", 0)
        max_amount = offer.get("max_amount", float("inf"))
        
        available_rub = available_usdt * price_rub
        effective_max_rub = min(max_amount, available_rub)
        min_amount_rub = min_amount
        
        if effective_max_rub < min_amount_rub:
            continue
            
        if not (min_amount_rub <= amount_rub <= effective_max_rub):
            continue
        
        offer["id"] = str(offer["_id"])
        del offer["_id"]
        offer["trader_nickname"] = await get_trader_nickname(offer["trader_id"])
        if offer.get("payment_detail_ids"):
            offer["payment_details"] = await get_payment_details_for_offer(offer["payment_detail_ids"])
        
        amount_usdt = amount_rub / price_rub
        offer["to_pay_rub"] = round(amount_rub, 2)
        offer["amount_usdt"] = round(amount_usdt, 4)
        offer["exchange_rate"] = round(price_rub, 2)
        
        result.append(offer)
            
    try:
        from routes.qr_aggregator.trading_routes import get_qr_aggregator_offers
        qr_offers = await get_qr_aggregator_offers(amount_rub)
        if method:
            qr_offers = [o for o in qr_offers if method.lower() in str(o.get("payment_methods", [])).lower()]
        result.extend(qr_offers)
    except Exception as e:
        logger.error(f"Error fetching QR offers for operators: {e}")
        
    return result
