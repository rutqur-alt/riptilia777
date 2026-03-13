
from pydantic import BaseModel, ConfigDict
from typing import Optional, List

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
