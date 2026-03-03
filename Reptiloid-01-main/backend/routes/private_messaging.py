"""
Private Messaging routes - User-to-user private messaging
Routes for conversations and private messages between users
"""
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict
import uuid

from core.database import db
from core.auth import get_current_user

router = APIRouter(tags=["private_messaging"])


# ==================== PYDANTIC MODELS ====================

class PrivateMessageCreate(BaseModel):
    content: str


class ConversationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    participants: List[str]
    participant_nicknames: List[str]
    last_message: Optional[str] = None
    last_message_at: Optional[str] = None
    unread_count: int = 0
    created_at: str


class PrivateMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    conversation_id: str
    sender_id: str
    sender_nickname: str
    content: str
    read: bool = False
    created_at: str


# ==================== WEBSOCKET MANAGER ====================

class PrivateMessageManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, conversation_id: str):
        if conversation_id in self.active_connections:
            if websocket in self.active_connections[conversation_id]:
                self.active_connections[conversation_id].remove(websocket)
    
    async def broadcast(self, conversation_id: str, message: dict):
        if conversation_id in self.active_connections:
            for conn in self.active_connections[conversation_id]:
                try:
                    await conn.send_json(message)
                except:
                    pass


private_msg_manager = PrivateMessageManager()


# ==================== USER SEARCH ====================

@router.get("/users/search")
async def search_users(query: str, user: dict = Depends(get_current_user)):
    """Search users by nickname or login for messaging"""
    if len(query) < 2:
        return []
    
    traders = await db.traders.find({
        "$or": [
            {"nickname": {"$regex": query, "$options": "i"}},
            {"login": {"$regex": query, "$options": "i"}},
            {"display_name": {"$regex": query, "$options": "i"}}
        ],
        "id": {"$ne": user["id"]}
    }, {"_id": 0, "id": 1, "nickname": 1, "login": 1, "display_name": 1}).to_list(10)
    
    merchants = await db.merchants.find({
        "$or": [
            {"nickname": {"$regex": query, "$options": "i"}},
            {"login": {"$regex": query, "$options": "i"}},
            {"merchant_name": {"$regex": query, "$options": "i"}}
        ],
        "id": {"$ne": user["id"]}
    }, {"_id": 0, "id": 1, "nickname": 1, "login": 1, "merchant_name": 1}).to_list(10)
    
    results = []
    for t in traders:
        nick = t.get("nickname") or t.get("display_name") or t.get("login", "Unknown")
        results.append({"id": t["id"], "nickname": nick, "login": t.get("login"), "type": "user"})
    for m in merchants:
        nick = m.get("nickname") or m.get("merchant_name") or m.get("login", "Unknown")
        results.append({"id": m["id"], "nickname": nick, "login": m.get("login"), "type": "merchant", "name": m.get("merchant_name")})
    
    return results


@router.get("/users/online")
async def get_online_users(user: dict = Depends(get_current_user)):
    """Get list of all users for messaging"""
    traders = await db.traders.find(
        {"id": {"$ne": user["id"]}},
        {"_id": 0, "id": 1, "nickname": 1}
    ).to_list(100)
    
    return [{"id": t["id"], "nickname": t["nickname"], "type": "user"} for t in traders]


# ==================== CONVERSATIONS ====================

@router.get("/conversations")
async def get_conversations(user: dict = Depends(get_current_user)):
    """Get all conversations for current user"""
    conversations = await db.conversations.find(
        {"$or": [
            {"participants": user["id"]},
            {"participant_ids": user["id"]}
        ]},
        {"_id": 0}
    ).sort("last_message_at", -1).to_list(50)
    
    for conv in conversations:
        if conv.get("is_admin_chat"):
            conv["other_nickname"] = "Администрация"
            conv["other_user"] = {"nickname": "Администрация"}
        else:
            participants = conv.get("participants", conv.get("participant_ids", []))
            other_id = [p for p in participants if p != user["id"]][0] if participants else None
            
            if other_id and other_id != "admin":
                other_user = await db.traders.find_one({"id": other_id}, {"_id": 0, "nickname": 1})
                if not other_user:
                    other_user = await db.merchants.find_one({"id": other_id}, {"_id": 0, "nickname": 1})
                
                conv["other_user"] = other_user
                conv["other_nickname"] = other_user["nickname"] if other_user else "Unknown"
            else:
                conv["other_nickname"] = "Администрация"
                conv["other_user"] = {"nickname": "Администрация"}
        
        unread = await db.private_messages.count_documents({
            "conversation_id": conv["id"],
            "sender_id": {"$ne": user["id"]},
            "read": False
        })
        conv["unread_count"] = unread
    
    return conversations


@router.post("/conversations/{user_id}")
async def create_or_get_conversation(user_id: str, user: dict = Depends(get_current_user)):
    """Create a new conversation or get existing one with a user"""
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Нельзя написать самому себе")
    
    other_user = await db.traders.find_one({"id": user_id}, {"_id": 0})
    if not other_user:
        other_user = await db.merchants.find_one({"id": user_id}, {"_id": 0})
    if not other_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    existing = await db.conversations.find_one({
        "participants": {"$all": [user["id"], user_id]}
    }, {"_id": 0})
    
    if existing:
        existing["other_nickname"] = other_user.get("nickname", "Unknown")
        return existing
    
    conv_id = f"conv_{uuid.uuid4().hex[:12]}"
    my_nickname = user.get("nickname", user.get("login", "Unknown"))
    
    conv_doc = {
        "id": conv_id,
        "participants": [user["id"], user_id],
        "participant_nicknames": [my_nickname, other_user.get("nickname", "Unknown")],
        "last_message": None,
        "last_message_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.conversations.insert_one(conv_doc)
    
    response = {k: v for k, v in conv_doc.items() if k != "_id"}
    response["other_nickname"] = other_user.get("nickname", "Unknown")
    return response


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    """Delete a conversation"""
    conv = await db.conversations.find_one({
        "id": conversation_id,
        "participants": user["id"]
    }, {"_id": 0})
    
    if not conv:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    
    await db.private_messages.delete_many({"conversation_id": conversation_id})
    await db.conversations.delete_one({"id": conversation_id})
    
    return {"status": "deleted"}


# ==================== MESSAGES ====================

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str, user: dict = Depends(get_current_user)):
    """Get messages in a conversation"""
    conv = await db.conversations.find_one({
        "id": conversation_id,
        "participants": user["id"]
    }, {"_id": 0})
    
    if not conv:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    
    messages = await db.private_messages.find(
        {"conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    
    await db.private_messages.update_many(
        {
            "conversation_id": conversation_id,
            "sender_id": {"$ne": user["id"]},
            "read": False
        },
        {"$set": {"read": True}}
    )
    
    return messages


@router.post("/conversations/{conversation_id}/messages")
async def send_private_message(conversation_id: str, data: PrivateMessageCreate, user: dict = Depends(get_current_user)):
    """Send a private message"""
    conv = await db.conversations.find_one({
        "id": conversation_id,
        "participants": user["id"]
    }, {"_id": 0})
    
    if not conv:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    
    if not data.content.strip():
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    
    my_nickname = user.get("nickname", user.get("login", "Unknown"))
    
    msg_doc = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": user["id"],
        "sender_nickname": my_nickname,
        "content": data.content.strip(),
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.private_messages.insert_one(msg_doc)
    
    await db.conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "last_message": data.content[:100],
            "last_message_at": msg_doc["created_at"]
        }}
    )
    
    response = {k: v for k, v in msg_doc.items() if k != "_id"}
    
    await private_msg_manager.broadcast(conversation_id, response)
    
    return response
