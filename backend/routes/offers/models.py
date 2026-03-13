
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class OfferCreate(BaseModel):
    type: str = Field(..., description="buy or sell")
    cryptocurrency: str = Field(..., description="USDT, BTC, etc.")
    fiat_currency: str = Field(..., description="RUB, USD, etc.")
    amount: float = Field(..., gt=0)
    min_limit: float = Field(..., gt=0)
    max_limit: float = Field(..., gt=0)
    price_type: str = Field(..., description="fixed or floating")
    price_value: float = Field(..., gt=0)
    payment_methods: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    payment_detail_ids: Optional[List[str]] = None

class OfferUpdate(BaseModel):
    amount: Optional[float] = None
    min_limit: Optional[float] = None
    max_limit: Optional[float] = None
    price_value: Optional[float] = None
    payment_methods: Optional[List[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    payment_detail_ids: Optional[List[str]] = None

class OfferResponse(BaseModel):
    id: str
    trader_id: str
    trader_nickname: Optional[str] = None
    type: str
    cryptocurrency: str
    fiat_currency: str
    amount: float
    available_amount: float
    min_limit: float
    max_limit: float
    price_type: str
    price_value: float
    price_rub: float
    payment_methods: List[str]
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    payment_details: Optional[List[Dict[str, Any]]] = None
    auto_deactivated: bool = False
    deactivation_status: Optional[str] = None
    deactivation_reason: Optional[str] = None
