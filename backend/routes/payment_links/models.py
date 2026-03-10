
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class PaymentLinkCreate(BaseModel):
    amount_rub: float = Field(..., gt=0)
    price_rub: float = Field(..., gt=0)
    description: Optional[str] = None

class PaymentLinkResponse(BaseModel):
    id: str
    merchant_id: str
    amount_rub: float
    amount_usdt: float
    price_rub: float
    status: str
    link_url: str
    created_at: datetime
    expires_at: datetime
    trade_id: Optional[str] = None
    trade_status: Optional[str] = None
