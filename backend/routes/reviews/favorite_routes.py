
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import get_current_user

router = APIRouter()

@router.post("/favorites/shops/{shop_id}")
async def add_favorite_shop(shop_id: str, user: dict = Depends(get_current_user)):
    """Add shop to favorites"""
    existing = await db.favorites.find_one({
        "user_id": user["id"],
        "shop_id": shop_id
    })
    if existing:
        return {"status": "already_exists"}
    
    await db.favorites.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "shop_id": shop_id,
        "type": "shop",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    return {"status": "added"}


@router.delete("/favorites/shops/{shop_id}")
async def remove_favorite_shop(shop_id: str, user: dict = Depends(get_current_user)):
    """Remove shop from favorites"""
    await db.favorites.delete_one({"user_id": user["id"], "shop_id": shop_id})
    return {"status": "removed"}


@router.get("/favorites/shops")
async def get_favorite_shops(user: dict = Depends(get_current_user)):
    """Get user's favorite shops"""
    favorites = await db.favorites.find(
        {"user_id": user["id"], "type": "shop"},
        {"_id": 0}
    ).to_list(100)
    
    shop_ids = [f["shop_id"] for f in favorites]
    shops = []
    for shop_id in shop_ids:
        shop = await db.traders.find_one(
            {"id": shop_id, "has_shop": True},
            {"_id": 0, "id": 1, "nickname": 1, "shop_settings": 1}
        )
        if shop:
            shops.append({
                "id": shop["id"],
                "nickname": shop["nickname"],
                "shop_name": shop.get("shop_settings", {}).get("shop_name"),
                "rating": shop.get("shop_settings", {}).get("rating", 0),
                "reviews_count": shop.get("shop_settings", {}).get("reviews_count", 0)
            })
    return shops
