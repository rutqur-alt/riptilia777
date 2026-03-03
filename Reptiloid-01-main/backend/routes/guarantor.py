"""
Guarantor routes - P2P guarantor deals
Routes for creating and managing guarantor deals between users
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict
import uuid

from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/guarantor", tags=["guarantor"])


# ==================== PYDANTIC MODELS ====================

class GuarantorDealCreate(BaseModel):
    role: str  # buyer or seller
    amount: float
    currency: str = "USDT"
    title: str
    description: str
    conditions: Optional[str] = None
    counterparty_nickname: Optional[str] = None


class GuarantorDealResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    creator_id: str
    creator_nickname: str
    creator_role: str
    counterparty_id: Optional[str] = None
    counterparty_nickname: Optional[str] = None
    amount: float
    currency: str
    title: str
    description: str
    conditions: Optional[str] = None
    status: str
    commission: float
    invite_code: Optional[str] = None
    invite_link: Optional[str] = None
    created_at: str
    funded_at: Optional[str] = None
    completed_at: Optional[str] = None


# ==================== GUARANTOR DEALS ====================

@router.post("/deals", response_model=GuarantorDealResponse)
async def create_guarantor_deal(data: GuarantorDealCreate, user: dict = Depends(get_current_user)):
    """Create a new guarantor deal"""
    if data.role not in ["buyer", "seller"]:
        raise HTTPException(status_code=400, detail="Роль должна быть 'buyer' или 'seller'")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")

    if len(data.title) < 3 or len(data.title) > 100:
        raise HTTPException(status_code=400, detail="Название должно быть от 3 до 100 символов")

    if len(data.description) < 10 or len(data.description) > 1000:
        raise HTTPException(status_code=400, detail="Описание должно быть от 10 до 1000 символов")

    counterparty_id = None
    counterparty_nickname = None
    if data.counterparty_nickname:
        counterparty = await db.traders.find_one({"nickname": data.counterparty_nickname}, {"_id": 0})
        if not counterparty:
            counterparty = await db.merchants.find_one({"nickname": data.counterparty_nickname}, {"_id": 0})

        if not counterparty:
            raise HTTPException(status_code=404, detail=f"Пользователь с никнеймом '{data.counterparty_nickname}' не найден")

        if counterparty["id"] == user["id"]:
            raise HTTPException(status_code=400, detail="Нельзя создать сделку с самим собой")

        counterparty_id = counterparty["id"]
        counterparty_nickname = counterparty.get("nickname", "")

    commission = round(data.amount * 0.05, 4)

    deal_id = f"gd_{uuid.uuid4().hex[:12]}"
    invite_code = uuid.uuid4().hex[:8] if not counterparty_id else None

    deal_doc = {
        "id": deal_id,
        "creator_id": user["id"],
        "creator_nickname": user.get("nickname", user.get("login", "")),
        "creator_role": data.role,
        "counterparty_id": counterparty_id,
        "counterparty_nickname": counterparty_nickname,
        "amount": data.amount,
        "currency": data.currency,
        "title": data.title,
        "description": data.description,
        "conditions": data.conditions,
        "status": "pending_counterparty" if not counterparty_id else "pending_payment",
        "commission": commission,
        "invite_code": invite_code,
        "invite_link": f"/guarantor/join/{invite_code}" if invite_code else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "funded_at": None,
        "completed_at": None
    }

    await db.guarantor_deals.insert_one(deal_doc)

    response = {k: v for k, v in deal_doc.items() if k != "_id"}
    return response


@router.get("/deals")
async def get_my_guarantor_deals(user: dict = Depends(get_current_user)):
    """Get all guarantor deals for current user"""
    deals = await db.guarantor_deals.find({
        "$or": [
            {"creator_id": user["id"]},
            {"counterparty_id": user["id"]}
        ]
    }, {"_id": 0}).sort("created_at", -1).to_list(100)
    return deals


@router.get("/deals/{deal_id}")
async def get_guarantor_deal(deal_id: str, user: dict = Depends(get_current_user)):
    """Get a specific guarantor deal"""
    deal = await db.guarantor_deals.find_one({"id": deal_id}, {"_id": 0})
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    if deal["creator_id"] != user["id"] and deal.get("counterparty_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к этой сделке")

    return deal


@router.post("/deals/{deal_id}/join")
async def join_guarantor_deal(deal_id: str, invite_code: str, user: dict = Depends(get_current_user)):
    """Join a guarantor deal via invite link"""
    deal = await db.guarantor_deals.find_one({"id": deal_id}, {"_id": 0})
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    if deal["status"] != "pending_counterparty":
        raise HTTPException(status_code=400, detail="Сделка уже имеет второго участника")

    if deal.get("invite_code") != invite_code:
        raise HTTPException(status_code=403, detail="Неверный код приглашения")

    if deal["creator_id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Нельзя присоединиться к своей сделке")

    await db.guarantor_deals.update_one(
        {"id": deal_id},
        {"$set": {
            "counterparty_id": user["id"],
            "counterparty_nickname": user.get("nickname", user.get("login", "")),
            "status": "pending_payment",
            "invite_code": None,
            "invite_link": None
        }}
    )

    return {"status": "joined"}


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


@router.post("/deals/{deal_id}/dispute")
async def dispute_guarantor_deal(deal_id: str, reason: str = "", user: dict = Depends(get_current_user)):
    """Open a dispute on a guarantor deal"""
    deal = await db.guarantor_deals.find_one({"id": deal_id}, {"_id": 0})
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")

    if deal["status"] != "funded":
        raise HTTPException(status_code=400, detail="Спор можно открыть только после оплаты")

    if user["id"] != deal["creator_id"] and user["id"] != deal.get("counterparty_id"):
        raise HTTPException(status_code=403, detail="Только участники могут открыть спор")

    await db.guarantor_deals.update_one(
        {"id": deal_id},
        {"$set": {
            "status": "disputed",
            "disputed_at": datetime.now(timezone.utc).isoformat(),
            "disputed_by": user["id"],
            "dispute_reason": reason or "Не указана"
        }}
    )

    return {"status": "disputed"}
