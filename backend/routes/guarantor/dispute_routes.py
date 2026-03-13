from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user
from datetime import datetime, timezone

router = APIRouter()

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
