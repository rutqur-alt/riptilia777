from pathlib import Path
import os
from datetime import datetime, timezone
import uuid
import secrets
from core.database import db

# Upload directory
UPLOAD_DIR = str(Path(__file__).parent.parent.parent / "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Shop categories
SHOP_CATEGORIES = [
    "accounts",      # Аккаунты
    "software",      # Софт
    "databases",     # Базы данных
    "tools",         # Инструменты
    "guides",        # Гайды и схемы
    "keys",          # Ключи
    "financial",     # Финансовое
    "templates",     # Шаблоны
    "other"          # Другое
]

SHOP_CATEGORY_LABELS = {
    "accounts": "Аккаунты",
    "software": "Софт",
    "databases": "Базы данных",
    "tools": "Инструменты",
    "guides": "Гайды и схемы",
    "keys": "Ключи",
    "financial": "Финансовое",
    "templates": "Шаблоны",
    "other": "Другое"
}

async def find_shop_user(user_id):
    """Find a user by ID in traders or merchants collection. Returns (user_doc, collection) or (None, None)."""
    trader = await db.traders.find_one({"id": user_id}, {"_id": 0})
    if trader:
        return trader, db.traders
    merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0})
    if merchant:
        return merchant, db.merchants
    return None, None

async def create_marketplace_notification(user_id: str, event_type: str, title: str, message: str, link: str = None, purchase_id: str = None):
    """Create event notification for marketplace events"""
    try:
        from routes.websockets import ws_manager
    except ImportError:
        ws_manager = None
    
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": event_type,
        "title": title,
        "message": message,
        "link": link,
        "reference_id": purchase_id,
        "reference_type": "marketplace",
        "extra_data": {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.event_notifications.insert_one(notification)
    
    # Real-time WebSocket notification
    if ws_manager:
        await ws_manager.broadcast(f"user_{user_id}", {
            "type": "new_notification",
            "notification": {k: v for k, v in notification.items() if k != "_id"}
        })

def generate_id(prefix: str = "") -> str:
    date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{prefix}{date_part}_{secrets.token_hex(3).upper()}"
