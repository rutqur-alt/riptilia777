
from fastapi import APIRouter, HTTPException
from typing import Optional

from core.database import db
from .models import PaymentLinkResponse

router = APIRouter()

@router.get("/{link_id}", response_model=PaymentLinkResponse)
async def get_payment_link(link_id: str):
    """Get payment link details (public)"""
    link = await db.payment_links.find_one({"id": link_id}, {"_id": 0})
    if not link:
        raise HTTPException(status_code=404, detail="Payment link not found")
    return link


@router.get("/{link_id}/active-trade")
async def get_active_trade_for_link(link_id: str, client_id: Optional[str] = None):
    """Get active trade for payment link (for returning clients)"""
    query = {
        "payment_link_id": link_id,
        "status": {"$in": ["pending", "paid", "disputed"]}
    }
    
    if client_id:
        query["client_session_id"] = client_id
    
    trade = await db.trades.find_one(query, {"_id": 0}, sort=[("created_at", -1)])
    
    if trade:
        if trade.get("requisite_ids"):
            requisites = []
            for req_id in trade["requisite_ids"]:
                req = await db.requisites.find_one({"id": req_id}, {"_id": 0})
                if req:
                    requisites.append(req)
            trade["requisites"] = requisites
        return trade
    
    return None
