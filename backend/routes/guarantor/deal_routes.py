from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user
from .models import GuarantorDealCreate, GuarantorDealResponse
import uuid
from datetime import datetime, timezone

router = APIRouter()

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
