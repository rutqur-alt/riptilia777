from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user
from .models import PrivateMessageCreate
from .manager import private_msg_manager
import uuid
from datetime import datetime, timezone

router = APIRouter()

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
