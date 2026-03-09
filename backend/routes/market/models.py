from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional, Dict, Any
from .utils import SHOP_CATEGORIES

class ShopApplicationCreate(BaseModel):
    shop_name: str
    shop_description: str
    categories: List[str]
    telegram: str
    experience: Optional[str] = None

    @field_validator('categories')
    @classmethod
    def validate_categories(cls, v):
        for cat in v:
            if cat not in SHOP_CATEGORIES:
                raise ValueError(f'Недопустимая категория: {cat}. Допустимые: {", ".join(SHOP_CATEGORIES)}')
        return v


class ShopApplicationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    user_nickname: str
    shop_name: str
    shop_description: str
    categories: List[str]
    telegram: str
    experience: Optional[str] = None
    status: str
    admin_comment: Optional[str] = None
    created_at: str
    reviewed_at: Optional[str] = None


class PriceVariant(BaseModel):
    quantity: int
    price: float
    label: Optional[str] = None


class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    currency: str = "USDT"
    category: str
    image_url: Optional[str] = None
    quantity: int = 0
    auto_content: List[str] = []
    is_active: bool = True
    is_infinite: bool = False
    price_variants: List[PriceVariant] = []
    attached_files: List[str] = []

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    is_infinite: Optional[bool] = None
    price_variants: Optional[List[PriceVariant]] = None
    attached_files: Optional[List[str]] = None


class ShopSettings(BaseModel):
    shop_name: str
    shop_description: Optional[str] = None
    shop_logo: Optional[str] = None
    shop_banner: Optional[str] = None
    categories: List[str] = []
    is_active: bool = True
    commission_rate: Optional[float] = None

class QuickPaymentCreate(BaseModel):
    amount_rub: int
    description: Optional[str] = "Пополнение баланса"
    merchant_api_key: Optional[str] = None

class DemoCallbackData(BaseModel):
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[float] = None
    amount_usdt: Optional[float] = None
    timestamp: Optional[str] = None
    sign: Optional[str] = None
    
    class Config:
        extra = "allow"
