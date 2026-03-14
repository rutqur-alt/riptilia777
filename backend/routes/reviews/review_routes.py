
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import get_current_user
from .models import ReviewCreate, ReviewResponse
from .utils import update_shop_rating

router = APIRouter()

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
