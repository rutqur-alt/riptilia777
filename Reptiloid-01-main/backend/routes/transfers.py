"""
Transfers routes - User-to-user USDT transfers
Routes for sending and tracking internal transfers
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid

from core.database import db
from core.auth import get_current_user

router = APIRouter(tags=["transfers"])


# ==================== PYDANTIC MODELS ====================

class TransferRequest(BaseModel):
    recipient_nickname: str
    amount: float


# ==================== TRANSFER ROUTES ====================

@router.post("/transfers/send")
async def send_transfer(data: TransferRequest, user: dict = Depends(get_current_user)):
    """Send USDT to another user"""
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")
    
    sender = await db.traders.find_one({"id": user["id"]}, {"_id": 0})
    if not sender:
        raise HTTPException(status_code=404, detail="Отправитель не найден")
    
    if sender.get("balance_usdt", 0) < data.amount:
        raise HTTPException(status_code=400, detail="Недостаточно средств")
    
    recipient = await db.traders.find_one({"nickname": data.recipient_nickname}, {"_id": 0})
    if not recipient:
        raise HTTPException(status_code=404, detail="Получатель не найден")
    
    if recipient["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Нельзя перевести самому себе")
    
    # Execute transfer
    await db.traders.update_one(
        {"id": user["id"]},
        {"$inc": {"balance_usdt": -data.amount}}
    )
    await db.traders.update_one(
        {"id": recipient["id"]},
        {"$inc": {"balance_usdt": data.amount}}
    )
    
    # Log transfer
    transfer_doc = {
        "id": str(uuid.uuid4()),
        "from_id": user["id"],
        "from_nickname": sender.get("nickname", sender.get("login")),
        "to_id": recipient["id"],
        "to_nickname": recipient.get("nickname", recipient.get("login")),
        "amount": data.amount,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.transfers.insert_one(transfer_doc)
    
    return {"status": "success", "transfer_id": transfer_doc["id"]}


@router.get("/transfers/history")
async def get_transfer_history(user: dict = Depends(get_current_user)):
    """Get user's transfer history"""
    sent = await db.transfers.find(
        {"from_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    received = await db.transfers.find(
        {"to_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    for t in sent:
        t["type"] = "sent"
    for t in received:
        t["type"] = "received"
    
    all_transfers = sent + received
    all_transfers.sort(key=lambda x: x["created_at"], reverse=True)
    
    return all_transfers[:50]
