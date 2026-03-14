from pydantic import BaseModel
from typing import Optional, List

class SendMessageRequest(BaseModel):
    content: str
    attachments: Optional[List[str]] = None

class OpenDisputeRequest(BaseModel):
    reason: str

class ResolveDisputeRequest(BaseModel):
    decision: str  # "refund_buyer", "release_seller", "split"
    amount: Optional[float] = None
    reason: str

class CreateSupportTicketRequest(BaseModel):
    category: str
    subject: str
    message: str
    related_id: Optional[str] = None  # Optional trade/order ID

class CreateInternalChatRequest(BaseModel):
    title: str
    participant_ids: List[str]
    related_dispute_id: Optional[str] = None
