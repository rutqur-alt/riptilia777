
from datetime import datetime, timezone
import uuid
from typing import List

from core.database import db

# WebSocket manager for real-time notifications
try:
    from routes.ws_routes import ws_manager
except ImportError:
    ws_manager = None

async def _ws_broadcast(channel: str, data: dict):
    """Broadcast message via WebSocket"""
    if ws_manager:
        await ws_manager.broadcast(channel, data)

async def create_event_notification(
    user_id: str,
    event_type: str,
    title: str,
    message: str,
    link: str = None,
    reference_id: str = None,
    reference_type: str = None,
    extra_data: dict = None
):
    """
    Create a new event notification for a user.
    
    Args:
        user_id: The user to notify
        event_type: Type from NOTIFICATION_TYPES
        title: Short title for the notification
        message: Detailed message
        link: Link to navigate to when clicked
        reference_id: ID of related entity (trade_id, order_id, etc.)
        reference_type: Type of reference (trade, order, purchase, etc.)
        extra_data: Additional data to store with notification
    """
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": event_type,
        "title": title,
        "message": message,
        "link": link,
        "reference_id": reference_id,
        "reference_type": reference_type,
        "extra_data": extra_data or {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.event_notifications.insert_one(notification)
    
    # Real-time notification via WebSocket
    await _ws_broadcast(f"user_{user_id}", {
        "type": "new_notification",
        "notification": {k: v for k, v in notification.items() if k != "_id"}
    })
    
    return notification


async def create_bulk_notifications(notifications: List[dict]):
    """Create multiple notifications at once"""
    if not notifications:
        return
    
    docs = []
    now = datetime.now(timezone.utc).isoformat()
    
    for n in notifications:
        docs.append({
            "id": str(uuid.uuid4()),
            "user_id": n["user_id"],
            "type": n["type"],
            "title": n["title"],
            "message": n["message"],
            "link": n.get("link"),
            "reference_id": n.get("reference_id"),
            "reference_type": n.get("reference_type"),
            "extra_data": n.get("extra_data", {}),
            "read": False,
            "created_at": now
        })
    
    await db.event_notifications.insert_many(docs)
