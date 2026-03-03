"""
BITARBITR P2P Platform - Notifications Router
Обработка уведомлений (колокольчик)
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone
import logging

router = APIRouter(tags=["Notifications"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

# Глобальные зависимости - инициализируются из server.py
_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"


def init_router(database, jwt_secret: str, jwt_algorithm: str = "HS256"):
    """Инициализация роутера"""
    global _db, _jwt_secret, _jwt_algorithm
    _db = database
    _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получение текущего пользователя из JWT"""
    from jose import jwt, JWTError
    
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    token = credentials.credentials
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await _db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


def require_role(allowed_roles: list):
    """Проверка роли пользователя"""
    async def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Access denied")
        return user
    return role_checker


# ================== USER NOTIFICATIONS ==================

@router.get("/notifications")
async def get_user_notifications(user: dict = Depends(get_current_user)):
    """Получить уведомления пользователя (трейдера/мерчанта)"""
    notifications = await _db.user_notifications.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    unread_count = await _db.user_notifications.count_documents({
        "user_id": user["id"],
        "read": False
    })
    
    return {"notifications": notifications, "unread_count": unread_count}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: dict = Depends(get_current_user)):
    """Отметить уведомление как прочитанное"""
    await _db.user_notifications.update_one(
        {"id": notification_id, "user_id": user["id"]},
        {"$set": {"read": True}}
    )
    return {"success": True}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(user: dict = Depends(get_current_user)):
    """Отметить все уведомления как прочитанные"""
    await _db.user_notifications.update_many(
        {"user_id": user["id"], "read": False},
        {"$set": {"read": True}}
    )
    return {"success": True}


# ================== ADMIN NOTIFICATIONS ==================

@router.get("/admin/notifications")
async def get_admin_notifications(user: dict = Depends(require_role(["admin", "support"]))):
    """Получить уведомления админа/саппорта"""
    # Уведомления либо для конкретного юзера, либо для всех админов (без user_id)
    notifications = await _db.admin_notifications.find(
        {"$or": [
            {"user_id": user["id"]},
            {"user_id": {"$exists": False}},
            {"user_id": None}
        ]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    # Считаем непрочитанные
    unread_count = await _db.admin_notifications.count_documents({
        "$and": [
            {"$or": [
                {"user_id": user["id"]},
                {"user_id": {"$exists": False}},
                {"user_id": None}
            ]},
            {"$or": [{"read": False}, {"is_read": False}]}
        ]
    })
    
    return {"notifications": notifications, "unread_count": unread_count}


@router.post("/admin/notifications/{notification_id}/read")
async def mark_admin_notification_read(
    notification_id: str, 
    user: dict = Depends(require_role(["admin", "support"]))
):
    """Отметить уведомление админа как прочитанное"""
    # Обновляем уведомление - либо для этого админа, либо общее
    result = await _db.admin_notifications.update_one(
        {"id": notification_id, "$or": [
            {"user_id": user["id"]},
            {"user_id": {"$exists": False}},
            {"user_id": None}
        ]},
        {"$set": {"read": True, "is_read": True}}
    )
    
    return {"success": True, "modified": result.modified_count > 0}


@router.post("/admin/notifications/read-all")
async def mark_all_admin_notifications_read(
    user: dict = Depends(require_role(["admin", "support"]))
):
    """Отметить все уведомления админа как прочитанные"""
    # Отмечаем все уведомления для этого админа + общие уведомления без user_id
    await _db.admin_notifications.update_many(
        {"$or": [
            {"user_id": user["id"]},
            {"user_id": {"$exists": False}},
            {"user_id": None}
        ]},
        {"$set": {"read": True, "is_read": True}}
    )
    return {"success": True}


@router.delete("/admin/notifications/{notification_id}")
async def delete_admin_notification(
    notification_id: str,
    user: dict = Depends(require_role(["admin", "support"]))
):
    """Удалить уведомление"""
    result = await _db.admin_notifications.delete_one({"id": notification_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    
    return {"success": True}
