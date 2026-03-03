"""
Forum routes - Global forum/chat functionality
Routes for public forum messages with anti-spam protection
"""
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
import uuid

from core.database import db
from core.auth import get_current_user

router = APIRouter(tags=["forum"])


# ==================== PYDANTIC MODELS ====================

class ForumMessageCreate(BaseModel):
    content: str


class ForumMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    sender_id: str
    sender_login: str
    sender_role: str
    content: str
    created_at: str


# ==================== FORUM WEBSOCKET MANAGER ====================

class ForumConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


forum_manager = ForumConnectionManager()


# ==================== FORUM WEBSOCKET ====================

@router.websocket("/ws/forum")
async def forum_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time forum messages"""
    await forum_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, receive pings
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        forum_manager.disconnect(websocket)
    except Exception:
        forum_manager.disconnect(websocket)


# ==================== FORUM ROUTES ====================

@router.get("/forum/messages")
async def get_forum_messages(limit: int = 50, before: Optional[str] = None):
    """Get global forum messages (public, no auth required)"""
    query = {}
    if before:
        query["created_at"] = {"$lt": before}
    
    messages = await db.forum_messages.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return list(reversed(messages))


@router.post("/forum/messages", response_model=ForumMessageResponse)
async def send_forum_message(data: ForumMessageCreate, user: dict = Depends(get_current_user)):
    """Send a message to global forum (authenticated users only)"""
    if not data.content or len(data.content.strip()) == 0:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    if len(data.content) > 1000:
        raise HTTPException(status_code=400, detail="Сообщение слишком длинное (макс. 1000 символов)")
    
    content = data.content.strip()
    
    # Check if user is banned from forum
    user_doc = await db.traders.find_one({"id": user["id"]}, {"_id": 0, "forum_ban_until": 1, "last_forum_message": 1})
    if user_doc and user_doc.get("forum_ban_until"):
        ban_until = datetime.fromisoformat(user_doc["forum_ban_until"].replace("Z", "+00:00"))
        if ban_until > datetime.now(timezone.utc):
            remaining_hours = int((ban_until - datetime.now(timezone.utc)).total_seconds() / 3600)
            raise HTTPException(status_code=403, detail=f"Вы заблокированы в чате ещё {remaining_hours} ч.")
    
    # Rate limit: max 1 message per 10 minutes (anti-spam)
    if user_doc and user_doc.get("last_forum_message") and user.get("role") != "admin":
        last_msg_time = datetime.fromisoformat(user_doc["last_forum_message"].replace("Z", "+00:00"))
        seconds_since_last = (datetime.now(timezone.utc) - last_msg_time).total_seconds()
        if seconds_since_last < 600:
            minutes_left = int((600 - seconds_since_last) / 60)
            seconds_left = int((600 - seconds_since_last) % 60)
            raise HTTPException(status_code=429, detail=f"Подождите {minutes_left} мин. {seconds_left} сек. перед отправкой")
    
    # Auto-moderation: check for spam/ads/links
    content_lower = content.lower()
    
    spam_keywords = [
        "ищу сотрудников", "набираем", "вакансия", "работа мечты", "заработок", 
        "продаю", "куплю", "дешево", "скидка", "акция", "бесплатно",
        "пассивный доход", "бизнес предложение", "инвестиции гарантия",
        "telegram.me", "t.me/", "@", "wa.me", "whatsapp", "viber",
        "bitcoin", "btc", "eth", "крипта дешево"
    ]
    
    url_patterns = ["http://", "https://", "www.", ".com", ".ru", ".net", ".org", ".io"]
    
    is_spam = False
    reason = ""
    
    for keyword in spam_keywords:
        if keyword in content_lower:
            is_spam = True
            reason = f"Обнаружена реклама: {keyword}"
            break
    
    if not is_spam and user.get("role") != "admin":
        for pattern in url_patterns:
            if pattern in content_lower:
                is_spam = True
                reason = "Ссылки запрещены в общем чате"
                break
    
    if is_spam:
        ban_until = datetime.now(timezone.utc) + timedelta(hours=24)
        await db.traders.update_one(
            {"id": user["id"]},
            {"$set": {"forum_ban_until": ban_until.isoformat()}}
        )
        
        await db.forum_violations.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "user_login": user.get("login", "Unknown"),
            "content": content,
            "reason": reason,
            "banned_until": ban_until.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        raise HTTPException(
            status_code=403, 
            detail=f"Сообщение заблокировано: {reason}. Вы заблокированы на 24 часа."
        )
    
    message_doc = {
        "id": str(uuid.uuid4()),
        "sender_id": user["id"],
        "sender_login": user.get("login", "Anonymous"),
        "sender_role": user.get("role", "user"),
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.forum_messages.insert_one(message_doc)
    
    # Update last message time for rate limiting
    if user.get("role") == "trader":
        await db.traders.update_one(
            {"id": user["id"]},
            {"$set": {"last_forum_message": message_doc["created_at"]}}
        )
    elif user.get("role") == "merchant":
        await db.merchants.update_one(
            {"id": user["id"]},
            {"$set": {"last_forum_message": message_doc["created_at"]}}
        )
    
    # Broadcast to WebSocket clients
    await forum_manager.broadcast(message_doc)
    
    return message_doc


# ==================== FORUM VIOLATIONS ====================

@router.get("/admin/forum/violations")
async def get_forum_violations(user: dict = Depends(get_current_user)):
    """Get forum violations log (admin only)"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для администраторов")
    
    violations = await db.forum_violations.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return violations


@router.post("/admin/forum/unban/{user_id}")
async def unban_forum_user(user_id: str, user: dict = Depends(get_current_user)):
    """Unban user from forum (admin only)"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Только для администраторов")
    
    await db.traders.update_one(
        {"id": user_id},
        {"$unset": {"forum_ban_until": ""}}
    )
    
    return {"status": "unbanned"}
