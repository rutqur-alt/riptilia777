
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
    balance_usdt: float = 0.0
    frozen_usdt: Optional[float] = 0.0
    frozen_balance_usdt: Optional[float] = 0.0
    balance_rub: float = 0.0
    rating: Optional[float] = 5.0
    reviews_count: Optional[int] = 0
    trades_count: Optional[int] = 0
    is_verified: Optional[bool] = False
    is_trusted: Optional[bool] = False
    is_online: Optional[bool] = False
    last_seen: Optional[datetime] = None
    created_at: Optional[datetime] = None
    avatar_url: Optional[str] = None
    currency: str = "RUB"
    notifications_enabled: bool = True
    shop_balance: float = 0.0
    balance_escrow: float = 0.0
    referral_code: Optional[str] = None
    invited_count: int = 0
    referral_earnings: float = 0.0
    deposit_code: Optional[str] = None
    commission_rate: Optional[float] = 1.0
    accepted_merchant_types: Optional[List[str]] = []
    referred_by: Optional[str] = None
    is_blocked: Optional[bool] = False
    is_deleted: Optional[bool] = False
    has_shop: Optional[bool] = False
    shop_settings: Optional[Dict[str, Any]] = None
    shop_stats: Optional[Dict[str, Any]] = None
    recovery_key: Optional[str] = None
    last_forum_message: Optional[str] = None
    pending_shop_commission: Optional[float] = None
    
    # Stats
    total_trades: Optional[int] = 0
    completed_trades: Optional[int] = 0
    total_volume_usdt: float = 0.0
    success_rate: float = 100.0
    avg_response_time: Optional[float] = None

    class Config:
        extra = "allow"
