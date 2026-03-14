from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone

from core.database import db
from core.auth import require_role

router = APIRouter()

# ==================== OFFERS MANAGEMENT ====================

@router.get("/admin/offers")
async def get_all_offers(user: dict = Depends(require_role(["admin"]))):
    """Get all P2P offers for admin"""
    offers = await db.offers.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    for offer in offers:
        # Strip ObjectId _id from embedded requisites
        if "requisites" in offer:
            for req in offer["requisites"]:
                req.pop("_id", None)
        
        trader = await db.traders.find_one({"id": offer["trader_id"]}, {"_id": 0, "login": 1, "nickname": 1})
        if trader:
            offer["trader_login"] = trader.get("login", "")
            offer["trader_nickname"] = trader.get("nickname", "")
    
    return offers


@router.put("/admin/offers/{offer_id}/deactivate")
async def deactivate_offer(offer_id: str, user: dict = Depends(require_role(["admin"]))):
    """Deactivate an offer"""
    offer = await db.offers.find_one({"id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    await db.offers.update_one(
        {"id": offer_id},
        {"$set": {
            "is_active": False,
            "deactivated_by": user["id"],
            "deactivated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if offer.get("available_usdt", 0) > 0:
        await db.traders.update_one(
            {"id": offer["trader_id"]},
            {"$inc": {"balance_usdt": offer["available_usdt"]}}
        )
    
    return {"status": "deactivated"}


@router.put("/admin/offers/{offer_id}/toggle")
async def toggle_offer(offer_id: str, user: dict = Depends(require_role(["admin"]))):
    """Toggle offer active status"""
    offer = await db.offers.find_one({"id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    new_status = not offer.get("is_active", True)
    await db.offers.update_one({"id": offer_id}, {"$set": {"is_active": new_status}})
    
    return {"status": "toggled", "is_active": new_status}
