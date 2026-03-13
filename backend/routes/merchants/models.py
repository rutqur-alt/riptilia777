
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class MerchantCreate(BaseModel):
    login: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    merchant_name: str = Field(..., min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    telegram: Optional[str] = None
    description: Optional[str] = None

class MerchantUpdate(BaseModel):
    merchant_name: Optional[str] = None
    email: Optional[EmailStr] = None
    telegram: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    callback_url: Optional[str] = None
    notifications_enabled: Optional[bool] = None

class MerchantResponse(BaseModel):
    id: str
    login: str
    merchant_name: str
    email: Optional[str] = None
    telegram: Optional[str] = None
    description: Optional[str] = None
    balance_usdt: float
    frozen_balance_usdt: float
    status: str
    is_verified: bool
    created_at: datetime
    api_key: Optional[str] = None
    callback_url: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    commission_rate: float = 0.0
    total_turnover: float = 0.0
    total_transactions: int = 0
    
    # Stats
    today_turnover: float = 0.0
    today_transactions: int = 0
