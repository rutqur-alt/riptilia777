
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid

from core.database import db
from core.auth import require_role
from .models import PaymentLinkCreate, PaymentLinkResponse

router = APIRouter()

@router.post("/", response_model=PaymentLinkResponse)
async def create_payment_link(data: PaymentLinkCreate, user: dict = Depends(require_role(["merchant"]))):
    """Create a new payment link for merchant"""
    merchant = await db.merchants.find_one({"id": user["id"]}, {"_id": 0})
    
    if not merchant or merchant["status"] not in ["active", "approved"]:
        raise HTTPException(status_code=403, detail="Merchant not approved")
    
    amount_usdt = data.amount_rub / data.price_rub
    
    link_id = str(uuid.uuid4())[:8]
    link_doc = {
        "id": link_id,
        "merchant_id": user["id"],
        "amount_rub": data.amount_rub,
        "amount_usdt": round(amount_usdt, 2),
        "price_rub": data.price_rub,
        "status": "active",
        "link_url": f"/pay/{link_id}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    }
    
    await db.payment_links.insert_one(link_doc)
    return link_doc


@router.get("/")
async def get_payment_links(user: dict = Depends(require_role(["merchant"]))):
    """Get all payment links for current merchant"""
    links = await db.payment_links.find({"merchant_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    # Enrich with trade info
    for link in links:
        trade = await db.trades.find_one(
            {"payment_link_id": link["id"]},
            {"_id": 0, "id": 1, "status": 1},
            sort=[("created_at", -1)]
        )
        if trade:
            link["trade_id"] = trade["id"]
            link["trade_status"] = trade["status"]
    
    return links
