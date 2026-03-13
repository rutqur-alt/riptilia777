
from core.database import db

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
