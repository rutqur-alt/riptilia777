
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class OfferCreate(BaseModel):
    type: str = Field(..., description="buy or sell")
    amount_usdt: float = Field(..., gt=0)
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    price_rub: float = Field(..., gt=0)
    payment_methods: List[str] = Field(default_factory=list)
    conditions: Optional[str] = None
    payment_detail_ids: Optional[List[str]] = None

class OfferUpdate(BaseModel):
    amount_usdt: Optional[float] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    price_rub: Optional[float] = None
    payment_methods: Optional[List[str]] = None
    conditions: Optional[str] = None
    is_active: Optional[bool] = None
    payment_detail_ids: Optional[List[str]] = None

class OfferResponse(BaseModel):
    id: str
    trader_id: str
    trader_login: Optional[str] = None
    trader_nickname: Optional[str] = None
    type: str
    amount_usdt: Optional[float] = None
    available_usdt: Optional[float] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    price_rub: Optional[float] = None
    payment_methods: Optional[List[str]] = None
    payment_details: Optional[List[Dict[str, Any]]] = None
    payment_detail_ids: Optional[List[str]] = None
    requisites: Optional[List[Dict[str, Any]]] = None
    requisite_ids: Optional[List[str]] = None
    conditions: Optional[str] = None
    is_active: Optional[bool] = True
    trades_count: Optional[int] = 0
    success_rate: Optional[float] = 100.0
    created_at: Optional[datetime] = None
    commission_rate: Optional[float] = None
    reserved_commission: Optional[float] = None
    sold_usdt: Optional[float] = None
    actual_commission: Optional[float] = None
    auto_deactivated: Optional[bool] = False
    deactivation_status: Optional[str] = None
    deactivation_reason: Optional[str] = None
    qr_aggregator: Optional[bool] = None
    qr_method: Optional[str] = None
    provider_id: Optional[str] = None
    markup_percent: Optional[float] = None
    
    class Config:
        extra = "allow"
