"""
Reviews routes - Shop reviews and ratings
Routes for creating and managing shop reviews
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict
import uuid

from core.database import db
from core.auth import get_current_user

router = APIRouter(tags=["reviews"])


# ==================== PYDANTIC MODELS ====================

class ReviewCreate(BaseModel):
    shop_id: str
    rating: int  # 1-5
    comment: Optional[str] = None
    purchase_id: Optional[str] = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    shop_id: str
    reviewer_id: str
    reviewer_nickname: str
    rating: int
    comment: Optional[str] = None
    purchase_id: Optional[str] = None
    created_at: str


# ==================== HELPER FUNCTIONS ====================

async def update_shop_rating(shop_id: str):
    """Recalculate shop rating based on all reviews"""
    reviews = await db.shop_reviews.find({"shop_id": shop_id}, {"_id": 0, "rating": 1}).to_list(1000)
    if reviews:
        avg_rating = sum(r["rating"] for r in reviews) / len(reviews)
        await db.traders.update_one(
            {"id": shop_id},
            {"$set": {
                "shop_settings.rating": round(avg_rating, 1),
                "shop_settings.reviews_count": len(reviews)
            }}
        )


# ==================== REVIEW ROUTES ====================

@router.post("/shops/{shop_id}/reviews")
async def create_shop_review(shop_id: str, data: ReviewCreate, user: dict = Depends(get_current_user)):
    """Create a review for a shop"""
    shop_owner = await db.traders.find_one({"id": shop_id, "has_shop": True}, {"_id": 0})
    if not shop_owner:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    
    if shop_owner["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Нельзя оставить отзыв на свой магазин")
    
    if data.rating < 1 or data.rating > 5:
        raise HTTPException(status_code=400, detail="Рейтинг должен быть от 1 до 5")
    
    existing = await db.shop_reviews.find_one({
        "shop_id": shop_id,
        "reviewer_id": user["id"]
    })
    if existing:
        raise HTTPException(status_code=400, detail="Вы уже оставили отзыв на этот магазин")
    
    review_doc = {
        "id": str(uuid.uuid4()),
        "shop_id": shop_id,
        "reviewer_id": user["id"],
        "reviewer_nickname": user.get("nickname", user.get("login", "Unknown")),
        "rating": data.rating,
        "comment": data.comment,
        "purchase_id": data.purchase_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.shop_reviews.insert_one(review_doc)
    await update_shop_rating(shop_id)
    
    response = {k: v for k, v in review_doc.items() if k != "_id"}
    return response


@router.get("/shops/{shop_id}/reviews")
async def get_shop_reviews(shop_id: str):
    """Get all reviews for a shop"""
    reviews = await db.shop_reviews.find(
        {"shop_id": shop_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return reviews


@router.delete("/shops/{shop_id}/reviews/{review_id}")
async def delete_shop_review(shop_id: str, review_id: str, user: dict = Depends(get_current_user)):
    """Delete own review"""
    review = await db.shop_reviews.find_one({"id": review_id, "reviewer_id": user["id"]})
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")
    
    await db.shop_reviews.delete_one({"id": review_id})
    await update_shop_rating(shop_id)
    return {"status": "deleted"}


# ==================== PRODUCT CATEGORIES ====================

PRODUCT_CATEGORIES = [
    {"id": "games", "name": "Игры", "icon": "🎮"},
    {"id": "accounts", "name": "Аккаунты", "icon": "👤"},
    {"id": "subscriptions", "name": "Подписки", "icon": "📺"},
    {"id": "software", "name": "Софт", "icon": "💻"},
    {"id": "keys", "name": "Ключи", "icon": "🔑"},
    {"id": "services", "name": "Услуги", "icon": "🛠"},
    {"id": "other", "name": "Другое", "icon": "📦"}
]


@router.get("/product-categories")
async def get_product_categories():
    """Get all product categories"""
    return PRODUCT_CATEGORIES


# ==================== FAVORITES ====================

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
