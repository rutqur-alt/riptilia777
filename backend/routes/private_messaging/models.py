from pydantic import BaseModel, ConfigDict
from typing import List, Optional

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
