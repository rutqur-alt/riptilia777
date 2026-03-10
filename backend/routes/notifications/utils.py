
from datetime import datetime, timezone
import uuid
from core.database import db

async def create_notification(user_id: str, type: str, title: str, message: str, link: str = None):
    """Helper to create a notification"""
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": type,
        "title": title,
        "message": message,
        "link": link,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
