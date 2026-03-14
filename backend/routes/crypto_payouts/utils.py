from datetime import datetime, timezone
import uuid
from core.database import db

async def _create_payout_notification(user_id: str, event_type: str, title: str, message: str, link: str = None, order_id: str = None):
    """Create event notification for payout/crypto orders"""
    await db.event_notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": event_type,
        "title": title,
        "message": message,
        "link": link,
        "reference_id": order_id,
        "reference_type": "crypto_order",
        "extra_data": {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
