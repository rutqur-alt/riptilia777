
from fastapi import APIRouter

router = APIRouter()

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
