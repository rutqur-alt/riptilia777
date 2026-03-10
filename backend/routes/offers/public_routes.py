
from fastapi import APIRouter, Query
from typing import List, Optional
from core.database import db
from bson import ObjectId
import logging
import math

from .models import OfferResponse
from .utils import get_payment_details_for_offer, get_trader_nickname
from routes.qr_aggregator.utils import get_base_rate_rub

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[OfferResponse])
async def get_public_offers(
    type: str = Query(..., description="buy or sell"),
    cryptocurrency: str = Query("USDT"),
    fiat_currency: str = Query("RUB"),
    amount: Optional[float] = None,
    payment_method: Optional[str] = None
):
    query = {
        "type": type,
        "cryptocurrency": cryptocurrency,
        "fiat_currency": fiat_currency,
        "is_active": True,
        "available_amount": {"$gt": 0}
    }
    
    if payment_method and payment_method != "all":
        query["payment_methods"] = payment_method
        
    # Filter by amount limits
    # Note: This is tricky in MongoDB if price is dynamic, but assuming fixed/calculated price
    # We filter in python for complex logic if needed, or basic mongo query
    
    cursor = db.offers.find(query).sort("price_rub", 1 if type == "sell" else -1)
    offers = await cursor.to_list(length=100)
    
    result = []
    for offer in offers:
        # Filter by amount if provided
        if amount:
            min_limit = offer.get("min_limit", 0)
            max_limit = offer.get("max_limit", float("inf"))
            
            # Check limits in RUB (assuming limits are in RUB)
            # Or convert amount to RUB if limits are in RUB
            # Usually limits in P2P are in Fiat
            if not (min_limit <= amount <= max_limit):
                continue
                
        offer["id"] = str(offer["_id"])
        offer["trader_nickname"] = await get_trader_nickname(offer["trader_id"])
        
        if offer.get("payment_detail_ids"):
            offer["payment_details"] = await get_payment_details_for_offer(offer["payment_detail_ids"])
            
        result.append(offer)
        
    # Add QR Aggregator offers if type is sell (buying USDT)
    if type == "sell" and cryptocurrency == "USDT" and fiat_currency == "RUB":
        try:
            from routes.qr_aggregator.trading_routes import get_qr_aggregator_offers
            qr_offers = await get_qr_aggregator_offers(amount)
            result.extend(qr_offers)
        except Exception as e:
            logger.error(f"Error fetching QR offers: {e}")
            
    return result

@router.get("/operators", response_model=List[OfferResponse])
async def get_operators_for_payment(
    amount_rub: float = Query(..., gt=0),
    method: Optional[str] = None
):
    """
    Get offers suitable for merchant payment (operators).
    Includes P2P traders and QR Aggregator.
    """
    # 1. Get P2P offers
    query = {
        "type": "sell",
        "cryptocurrency": "USDT",
        "fiat_currency": "RUB",
        "is_active": True,
        "available_amount": {"$gt": 0}
    }
    
    if method and method != "all":
        # Map method names if needed
        # For now assume direct match or simple mapping
        if method == "sbp":
            query["payment_methods"] = {"$in": ["SBP", "Sberbank", "Tinkoff"]} # Example mapping
        elif method == "card":
            query["payment_methods"] = {"$in": ["Card", "Sberbank", "Tinkoff", "Alfa"]}
    
    cursor = db.offers.find(query).sort("price_rub", 1)
    p2p_offers = await cursor.to_list(length=100)
    
    result = []
    
    # Filter P2P offers by limits
    for offer in p2p_offers:
        min_limit = offer.get("min_limit", 0)
        max_limit = offer.get("max_limit", float("inf"))
        
        # Check available amount in RUB
        available_rub = offer["available_amount"] * offer["price_rub"]
        effective_max = min(max_limit, available_rub)
        
        if min_limit <= amount_rub <= effective_max:
            offer["id"] = str(offer["_id"])
            offer["trader_nickname"] = await get_trader_nickname(offer["trader_id"])
            if offer.get("payment_detail_ids"):
                offer["payment_details"] = await get_payment_details_for_offer(offer["payment_detail_ids"])
            result.append(offer)
            
    # 2. Get QR Aggregator offers
    try:
        from routes.qr_aggregator.trading_routes import get_qr_aggregator_offers
        qr_offers = await get_qr_aggregator_offers(amount_rub)
        
        # Filter QR offers by method if requested
        if method:
            qr_offers = [o for o in qr_offers if method.lower() in str(o.get("payment_methods", [])).lower()]
            
        result.extend(qr_offers)
    except Exception as e:
        logger.error(f"Error fetching QR offers for operators: {e}")
        
    return result
