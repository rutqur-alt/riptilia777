from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user
import uuid
from datetime import datetime, timezone

router = APIRouter()

@router.post("/deals/{deal_id}/fund")
async def fund_guarantor_deal(deal_id: str, user: dict = Depends(get_current_user)):
    """Buyer funds the deal (transfers crypto to escrow)"""
    deal = await db.guarantor_deals.find_one({"id": deal_id}, {"_id": 0})
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    if deal["status"] != "pending_payment":
        raise HTTPException(status_code=400, detail="Сделка не в статусе ожидания оплаты")

    buyer_id = deal["creator_id"] if deal["creator_role"] == "buyer" else deal["counterparty_id"]

    if user["id"] != buyer_id:
        raise HTTPException(status_code=403, detail="Только покупатель может оплатить сделку")

    buyer = await db.traders.find_one({"id": buyer_id}, {"_id": 0})
    if not buyer:
        raise HTTPException(status_code=404, detail="Покупатель не найден")

    if buyer.get("balance_usdt", 0) < deal["amount"]:
        raise HTTPException(status_code=400, detail=f"Недостаточно средств. Баланс: {buyer.get('balance_usdt', 0)} {deal['currency']}")

    await db.traders.update_one(
        {"id": buyer_id},
        {"$inc": {"balance_usdt": -deal["amount"]}}
    )

    await db.guarantor_deals.update_one(
        {"id": deal_id},
        {"$set": {
            "status": "funded",
            "funded_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    return {"status": "funded"}


@router.post("/deals/{deal_id}/confirm")
async def confirm_guarantor_deal(deal_id: str, user: dict = Depends(get_current_user)):
    """Buyer confirms the deal is complete, releasing funds to seller"""
    deal = await db.guarantor_deals.find_one({"id": deal_id}, {"_id": 0})
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    if deal["status"] != "funded":
        raise HTTPException(status_code=400, detail="Сделка не в статусе оплачена")

    buyer_id = deal["creator_id"] if deal["creator_role"] == "buyer" else deal["counterparty_id"]
    seller_id = deal["counterparty_id"] if deal["creator_role"] == "buyer" else deal["creator_id"]

    if user["id"] != buyer_id:
        raise HTTPException(status_code=403, detail="Только покупатель может подтвердить выполнение")

    seller_receives = deal["amount"] - deal["commission"]

    await db.traders.update_one(
        {"id": seller_id},
        {"$inc": {"balance_usdt": seller_receives}}
    )

    commission_doc = {
        "id": str(uuid.uuid4()),
        "deal_id": deal_id,
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "amount": deal["commission"],
        "type": "guarantor",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.commission_payments.insert_one(commission_doc)

    await db.guarantor_deals.update_one(
        {"id": deal_id},
        {"$set": {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    return {"status": "completed", "seller_received": seller_receives}
