
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from core.database import db
from datetime import datetime, timezone
import logging

from .models import TraderResponse
from .utils import get_trader_stats

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/{trader_id}", response_model=TraderResponse)
async def get_trader_public_profile(trader_id: str):
    """Get public trader profile"""
    trader = await db.traders.find_one({"id": trader_id}, {"_id": 0, "password_hash": 0})
    if not trader:
        # Try finding by login or nickname
        trader = await db.traders.find_one(
            {"$or": [{"login": trader_id}, {"nickname": trader_id}]}, 
            {"_id": 0, "password_hash": 0}
        )
        
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
        
    # Update stats
    stats = await get_trader_stats(trader["id"])
    trader.update(stats)
    
    # Check online status
    if trader.get("last_seen"):
        try:
            last_seen = datetime.fromisoformat(str(trader["last_seen"]).replace("Z", "+00:00"))
            diff_minutes = (datetime.now(timezone.utc) - last_seen).total_seconds() / 60
            trader["is_online"] = diff_minutes < 5
        except:
            trader["is_online"] = False
    else:
        trader["is_online"] = False
        
    return trader

@router.get("/", response_model=List[TraderResponse])
async def get_traders(
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "rating"
):
    """Get list of traders (public)"""
    sort_field = "rating"
    sort_dir = -1
    
    if sort_by == "rating":
        sort_field = "rating"
    elif sort_by == "deals":
        sort_field = "trades_count"
    elif sort_by == "new":
        sort_field = "created_at"
        
    cursor = db.traders.find({}, {"_id": 0, "password_hash": 0}).sort(sort_field, sort_dir).skip(skip).limit(limit)
    traders = await cursor.to_list(length=limit)
    
    for trader in traders:
        # Basic stats might be pre-calculated in background or we calculate on fly
        # For list view, better to use stored stats
        pass
        
    return traders
