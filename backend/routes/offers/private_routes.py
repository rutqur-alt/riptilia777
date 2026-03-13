
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from core.auth import get_current_user
from core.database import db
from bson import ObjectId
from datetime import datetime
import logging
import math

from .models import OfferCreate, OfferUpdate, OfferResponse
from .utils import get_payment_details_for_offer, get_trader_nickname
from routes.qr_aggregator.utils import get_base_rate

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=OfferResponse)
async def create_offer(
    offer_data: OfferCreate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "trader":
        raise HTTPException(status_code=403, detail="Only traders can create offers")
    
    # Check if trader has enough balance for sell offers
    if offer_data.type == "sell":
        trader = await db.traders.find_one({"_id": ObjectId(current_user["id"])})
        if not trader:
            raise HTTPException(status_code=404, detail="Trader not found")
            
        # Calculate total amount to freeze (amount + commission if applicable)
        # For now assuming commission is taken from the amount or handled separately
        # Usually we freeze the amount being sold
        
        if trader.get("balance_usdt", 0) < offer_data.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
            
        # Freeze funds
        await db.traders.update_one(
            {"_id": ObjectId(current_user["id"])},
            {
                "$inc": {
                    "balance_usdt": -offer_data.amount,
                    "frozen_balance_usdt": offer_data.amount
                }
            }
        )

    offer_dict = offer_data.dict()
    offer_dict["trader_id"] = current_user["id"]
    offer_dict["created_at"] = datetime.utcnow()
    offer_dict["is_active"] = True
    offer_dict["available_amount"] = offer_data.amount
    offer_dict["sold_amount"] = 0.0
    offer_dict["reserved_amount"] = 0.0
    
    # Calculate price in RUB if fixed
    if offer_data.price_type == "fixed":
        offer_dict["price_rub"] = offer_data.price_value
    else:
        # Floating price logic would go here
        # For MVP using fixed price value as margin or direct price
        offer_dict["price_rub"] = offer_data.price_value

    result = await db.offers.insert_one(offer_dict)
    
    # Fetch created offer
    created_offer = await db.offers.find_one({"_id": result.inserted_id})
    created_offer["id"] = str(created_offer["_id"])
    
    # Add nickname
    created_offer["trader_nickname"] = current_user.get("nickname", "Trader")
    
    # Add payment details
    if created_offer.get("payment_detail_ids"):
        created_offer["payment_details"] = await get_payment_details_for_offer(created_offer["payment_detail_ids"])
    
    return created_offer

@router.get("/my", response_model=List[OfferResponse])
async def get_my_offers(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "trader":
        raise HTTPException(status_code=403, detail="Only traders can view their offers")
        
    cursor = db.offers.find({"trader_id": current_user["id"]}).sort("created_at", -1)
    offers = await cursor.to_list(length=100)
    
    for offer in offers:
        offer["id"] = str(offer["_id"])
        offer["trader_nickname"] = current_user.get("nickname", "Trader")
        if offer.get("payment_detail_ids"):
            offer["payment_details"] = await get_payment_details_for_offer(offer["payment_detail_ids"])
            
    return offers

@router.put("/{offer_id}", response_model=OfferResponse)
async def update_offer(
    offer_id: str,
    offer_data: OfferUpdate,
    current_user: dict = Depends(get_current_user)
):
    offer = await db.offers.find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
        
    if offer["trader_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your offer")
        
    update_data = {k: v for k, v in offer_data.dict().items() if v is not None}
    
    # Handle balance changes if amount is updated
    if "amount" in update_data and offer["type"] == "sell":
        diff = update_data["amount"] - offer["amount"]
        if diff > 0:
            # Need to freeze more
            trader = await db.traders.find_one({"_id": ObjectId(current_user["id"])})
            if trader.get("balance_usdt", 0) < diff:
                raise HTTPException(status_code=400, detail="Insufficient balance for increase")
            
            await db.traders.update_one(
                {"_id": ObjectId(current_user["id"])},
                {
                    "$inc": {
                        "balance_usdt": -diff,
                        "frozen_balance_usdt": diff
                    }
                }
            )
        elif diff < 0:
            # Return to balance
            await db.traders.update_one(
                {"_id": ObjectId(current_user["id"])},
                {
                    "$inc": {
                        "balance_usdt": abs(diff),
                        "frozen_balance_usdt": -abs(diff)
                    }
                }
            )
            
        # Update available amount
        # Logic: available = new_amount - sold - reserved
        # But here we simplify assuming update_data["amount"] is the target total amount
        # We need to adjust available_amount by the diff
        update_data["available_amount"] = offer["available_amount"] + diff

    # Handle manual activation/deactivation
    if "is_active" in update_data:
        # If manually deactivating, set cooldown if it was active
        if not update_data["is_active"] and offer["is_active"]:
            # Check if it was auto-deactivated before? No, this is manual update
            # Set cooldown logic here if needed
            pass
            
    update_data["updated_at"] = datetime.utcnow()
    
    await db.offers.update_one(
        {"_id": ObjectId(offer_id)},
        {"$set": update_data}
    )
    
    updated_offer = await db.offers.find_one({"_id": ObjectId(offer_id)})
    updated_offer["id"] = str(updated_offer["_id"])
    updated_offer["trader_nickname"] = current_user.get("nickname", "Trader")
    
    if updated_offer.get("payment_detail_ids"):
        updated_offer["payment_details"] = await get_payment_details_for_offer(updated_offer["payment_detail_ids"])
        
    return updated_offer

@router.delete("/{offer_id}")
async def delete_offer(
    offer_id: str,
    current_user: dict = Depends(get_current_user)
):
    offer = await db.offers.find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
        
    if offer["trader_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your offer")
        
    # Return frozen funds if sell offer
    if offer["type"] == "sell":
        # Return remaining available amount
        # Note: reserved amount is kept frozen until trades finalize
        return_amount = offer["available_amount"]
        if return_amount > 0:
            await db.traders.update_one(
                {"_id": ObjectId(current_user["id"])},
                {
                    "$inc": {
                        "balance_usdt": return_amount,
                        "frozen_balance_usdt": -return_amount
                    }
                }
            )
            
    await db.offers.delete_one({"_id": ObjectId(offer_id)})
    return {"status": "success", "message": "Offer deleted"}
