
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from core.database import db
from datetime import datetime, timezone
import logging

from .models import MerchantResponse
from .utils import get_merchant_stats

router = APIRouter()
logger = logging.getLogger(__name__)

# Public routes for merchants are usually limited or non-existent as merchants are businesses
# But we might want to expose public profile if needed
# For now, keeping it minimal or empty if not needed by frontend

@router.get("/{merchant_id}", response_model=MerchantResponse)
async def get_merchant_public_profile(merchant_id: str):
    """Get public merchant profile (limited info)"""
    merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0, "password_hash": 0, "api_key": 0, "api_secret": 0, "balance_usdt": 0, "frozen_balance_usdt": 0})
    
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
        
    # We might want to show some stats but hide financial details
    # For now returning basic info
    
    return merchant
