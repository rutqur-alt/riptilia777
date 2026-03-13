
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class TraderCreate(BaseModel):
    login: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[EmailStr] = None
    telegram: Optional[str] = None

class TraderUpdate(BaseModel):
    email: Optional[EmailStr] = None
    telegram: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    currency: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    is_online: Optional[bool] = None

class TraderResponse(BaseModel):
    id: str
    login: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    telegram: Optional[str] = None
    balance_usdt: float
    frozen_balance_usdt: float
    balance_rub: float = 0.0
    rating: float
    reviews_count: int
    trades_count: int
    is_verified: bool
    is_trusted: bool
    is_online: bool
    last_seen: Optional[datetime] = None
    created_at: datetime
    avatar_url: Optional[str] = None
    currency: str = "RUB"
    notifications_enabled: bool = True
    shop_balance: float = 0.0
    balance_escrow: float = 0.0
    referral_code: Optional[str] = None
    invited_count: int = 0
    referral_earnings: float = 0.0
    
    # Stats
    total_volume_usdt: float = 0.0
    success_rate: float = 100.0
    avg_response_time: Optional[float] = None
