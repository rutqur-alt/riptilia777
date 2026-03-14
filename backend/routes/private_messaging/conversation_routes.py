from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user
import uuid
from datetime import datetime, timezone

router = APIRouter()

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
