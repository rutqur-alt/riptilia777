
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid

from core.database import db
from core.auth import get_merchant_by_api_key

router = APIRouter()

@router.get("/merchant/balance")
async def api_get_merchant_balance(merchant: dict = Depends(get_merchant_by_api_key)):
    """Get merchant balance - API Key authentication"""
    return {
        "balance_usdt": merchant.get("balance_usdt", 0),
        "total_commission_paid": merchant.get("total_commission_paid", 0),
        "merchant_name": merchant.get("merchant_name"),
        "merchant_type": merchant.get("merchant_type")
    }


@router.post("/payment/create")
async def api_create_payment(
    amount_rub: float = Body(...),
    description: Optional[str] = Body(None),
    client_id: Optional[str] = Body(None),
    webhook_url: Optional[str] = Body(None),
    merchant: dict = Depends(get_merchant_by_api_key)
):
    """Create payment link via API Key - returns payment URL"""
    if amount_rub < 100:
        raise HTTPException(status_code=400, detail="Minimum amount is 100 RUB")
    
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    price_rub = settings.get("default_price_rub", 100) if settings else 100
    
    link_id = str(uuid.uuid4())[:8]
    link_doc = {
        "id": link_id,
        "merchant_id": merchant["id"],
        "amount_rub": amount_rub,
        "amount_usdt": round(amount_rub / price_rub, 2),
        "price_rub": price_rub,
        "description": description,
        "client_id": client_id,
        "webhook_url": webhook_url or merchant.get("webhook_url"),
        "link_url": f"/deposit/{link_id}",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    }
    
    await db.payment_links.insert_one(link_doc)
    
    return {
        "payment_id": link_id,
        "payment_url": f"/deposit/{link_id}",
        "amount_rub": amount_rub,
        "amount_usdt": link_doc["amount_usdt"],
        "status": "active",
        "expires_at": link_doc["expires_at"]
    }


@router.get("/payment/{payment_id}/status")
async def api_get_payment_status(payment_id: str, merchant: dict = Depends(get_merchant_by_api_key)):
    """Get payment status via API Key"""
    link = await db.payment_links.find_one({"id": payment_id, "merchant_id": merchant["id"]}, {"_id": 0})
    if not link:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    trade = await db.trades.find_one({"payment_link_id": payment_id}, {"_id": 0})
    trade_status = trade.get("status") if trade else None
    
    return {
        "payment_id": payment_id,
        "amount_rub": link.get("amount_rub"),
        "amount_usdt": link.get("amount_usdt"),
        "status": link.get("status"),
        "trade_status": trade_status,
        "created_at": link.get("created_at")
    }


@router.get("/payments")
async def api_list_payments(
    status: Optional[str] = None,
    limit: int = 50,
    merchant: dict = Depends(get_merchant_by_api_key)
):
    """List all payments for merchant via API Key"""
    query = {"merchant_id": merchant["id"]}
    if status:
        query["status"] = status
    
    links = await db.payment_links.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    
    for link in links:
        trade = await db.trades.find_one(
            {"payment_link_id": link["id"]},
            {"_id": 0, "id": 1, "status": 1}
        )
        if trade:
            link["trade_id"] = trade["id"]
            link["trade_status"] = trade["status"]
    
    return links


@router.get("/transactions")
async def api_list_transactions(
    limit: int = 50,
    merchant: dict = Depends(get_merchant_by_api_key)
):
    """List merchant transactions via API Key"""
    transactions = await db.transactions.find(
        {"user_id": merchant["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    
    return transactions
