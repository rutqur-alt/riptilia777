from pydantic import BaseModel, ConfigDict
from typing import Optional

class GuarantorDealCreate(BaseModel):
    role: str  # buyer or seller
    amount: float
    currency: str = "USDT"
    title: str
    description: str
    conditions: Optional[str] = None
    counterparty_nickname: Optional[str] = None


class GuarantorDealResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    creator_id: str
    creator_nickname: str
    creator_role: str
    counterparty_id: Optional[str] = None
    counterparty_nickname: Optional[str] = None
    amount: float
    currency: str
    title: str
    description: str
    conditions: Optional[str] = None
    status: str
    commission: float
    invite_code: Optional[str] = None
    invite_link: Optional[str] = None
    created_at: str
    funded_at: Optional[str] = None
    completed_at: Optional[str] = None
