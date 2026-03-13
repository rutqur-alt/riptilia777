from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId

def clean_doc(doc):
    """Recursively clean MongoDB documents for JSON serialization"""
    if doc is None:
        return None
    if isinstance(doc, dict):
        result = {}
        for k, v in doc.items():
            if k == "_id":
                continue
            result[k] = clean_doc(v)
        return result
    elif isinstance(doc, list):
        return [clean_doc(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif hasattr(doc, 'isoformat'):
        return doc.isoformat()
    else:
        return doc

def get_date_range(period: str, date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Calculate date range from period or explicit dates."""
    now = datetime.now(timezone.utc)
    if date_from and date_to:
        return date_from, date_to

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "yesterday":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        now = start + timedelta(days=1)
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now - timedelta(days=30)
    elif period == "year":
        start = now - timedelta(days=365)
    elif period == "all":
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    else:
        start = now - timedelta(days=7)

    return start.isoformat(), now.isoformat()

# Role info helpers
MSG_ROLE_COLORS = {
    "user": "#FFFFFF", "buyer": "#FFFFFF", "p2p_seller": "#FFFFFF",
    "shop_owner": "#8B5CF6", "merchant": "#F97316",
    "mod_p2p": "#F59E0B", "mod_market": "#F59E0B",
    "support": "#3B82F6", "admin": "#EF4444", "owner": "#EF4444",
    "system": "#6B7280"
}

MSG_ROLE_NAMES = {
    "user": "Пользователь", "buyer": "Покупатель", "p2p_seller": "Продавец",
    "shop_owner": "Магазин", "merchant": "Мерчант",
    "mod_p2p": "Модератор P2P", "mod_market": "Гарант",
    "support": "Поддержка", "admin": "Администратор", "owner": "Владелец",
    "system": "Система"
}

def get_msg_role_info(role: str, name: str) -> dict:
    return {
        "name": name,
        "role": role,
        "role_name": MSG_ROLE_NAMES.get(role, role),
        "color": MSG_ROLE_COLORS.get(role, "#FFFFFF"),
        "icon": ""
    }
