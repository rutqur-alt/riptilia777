"""
Pydantic models (schemas) for API
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any


# ==================== AUTH MODELS ====================

class UserBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    login: str
    role: str

class UserCreate(BaseModel):
    login: str
    password: str
    nickname: str

class TraderCreate(UserCreate):
    referral_code: Optional[str] = None

class MerchantCreate(BaseModel):
    login: str
    password: str
    nickname: str
    merchant_name: str
    merchant_type: Optional[str] = "other"  # legacy; not used in UI/logic
    telegram: Optional[str] = None
    referral_code: Optional[str] = None

class LoginRequest(BaseModel):
    login: str
    password: str

class TokenResponse(BaseModel):
    token: str
    user: Dict[str, Any]


# ==================== USER MODELS ====================

class MerchantResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    login: str
    nickname: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_type: Optional[str] = None
    telegram: Optional[str] = None
    status: Optional[str] = None
    balance_usdt: Optional[float] = 0.0
    commission_rate: Optional[float] = 0.0
    api_key: Optional[str] = None
    created_at: Optional[str] = None
    approved_at: Optional[str] = None
    is_active: Optional[bool] = True
    is_verified: Optional[bool] = False
    balance_btc: Optional[float] = 0.0
    frozen_balance: Optional[float] = 0.0
    role: Optional[str] = None

class TraderResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    login: str
    nickname: str
    display_name: Optional[str] = None
    balance_usdt: float
    commission_rate: Optional[float] = None
    accepted_merchant_types: Optional[List[str]] = None
    created_at: str
    has_shop: Optional[bool] = False
    is_balance_locked: Optional[bool] = False
    is_blocked: Optional[bool] = False

class TraderUpdate(BaseModel):
    accepted_merchant_types: Optional[List[str]] = None
    display_name: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class Toggle2FARequest(BaseModel):
    enabled: bool


# ==================== TRADE MODELS ====================

class TradeCreate(BaseModel):
    amount_usdt: float
    price_rub: float
    trader_id: str
    payment_link_id: Optional[str] = None
    offer_id: Optional[str] = None
    requisite_ids: Optional[List[str]] = None
    payment_detail_ids: Optional[List[str]] = None
    buyer_id: Optional[str] = None
    buyer_type: Optional[str] = None
    client_session_id: Optional[str] = None

class TradeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    amount_usdt: float
    price_rub: Optional[float] = 0.0
    amount_rub: float
    trader_id: str
    trader_login: Optional[str] = None
    buyer_id: Optional[str] = None
    buyer_login: Optional[str] = None
    merchant_id: Optional[str] = None
    payment_link_id: Optional[str] = None
    offer_id: Optional[str] = None
    requisite_ids: Optional[List[str]] = None
    payment_detail_ids: Optional[List[str]] = None
    requisites: Optional[List[dict]] = None
    status: str
    trader_commission: Optional[float] = 0.0
    merchant_commission: Optional[float] = 0.0
    created_at: str
    expires_at: Optional[str] = None
    rate: Optional[float] = None
    payment_method: Optional[str] = None
    dispute_reason: Optional[str] = None
    disputed_at: Optional[str] = None


# ==================== OFFER MODELS ====================

class OfferCreate(BaseModel):
    amount_usdt: float
    min_amount: float = 1.0
    max_amount: Optional[float] = None
    price_rub: float
    payment_methods: List[str]
    accepted_merchant_types: Optional[List[str]] = None
    requisite_ids: Optional[List[str]] = None
    payment_detail_ids: Optional[List[str]] = None
    conditions: Optional[str] = None

class OfferResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    trader_id: str
    trader_login: str
    amount_usdt: float
    available_usdt: float
    min_amount: Optional[float] = 0.0
    max_amount: Optional[float] = 0.0
    price_rub: float
    payment_methods: List[str]
    accepted_merchant_types: Optional[List[str]] = None
    requisite_ids: Optional[List[str]] = None
    payment_detail_ids: Optional[List[str]] = None
    requisites: Optional[List[Dict[str, Any]]] = None
    payment_details: Optional[List[Dict[str, Any]]] = None
    conditions: Optional[str] = None
    is_active: bool
    created_at: str
    trades_count: Optional[int] = 0
    success_rate: Optional[float] = 100.0


# ==================== REQUISITES MODELS ====================

class RequisiteCard(BaseModel):
    bank_name: str
    card_number: str
    card_holder: str
    is_primary: bool = False

class RequisiteSBP(BaseModel):
    phone: str
    recipient_name: str
    bank_name: str
    is_primary: bool = False

class RequisiteQR(BaseModel):
    qr_data: str
    bank_name: str
    description: Optional[str] = None
    is_primary: bool = False

class RequisiteSIM(BaseModel):
    phone: str
    operator: str
    is_primary: bool = False

class RequisiteCIS(BaseModel):
    country: str
    bank_name: str
    account_number: str
    recipient_name: str
    swift_bic: Optional[str] = None
    is_primary: bool = False

class RequisiteCreate(BaseModel):
    type: str
    data: Dict[str, Any]

class RequisiteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    trader_id: str
    type: str
    data: Dict[str, Any]
    is_primary: bool
    created_at: str


# ==================== PAYMENT LINK MODELS ====================

class PaymentLinkCreate(BaseModel):
    amount_rub: float
    price_rub: float

class PaymentLinkResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    merchant_id: str
    amount_rub: float
    amount_usdt: float
    price_rub: float
    status: str
    link_url: str
    created_at: str
    expires_at: str


# ==================== COMMISSION MODELS ====================

class CommissionSettings(BaseModel):
    trader_commission: float = 1.0
    casino_commission: float = 0.5
    shop_commission: float = 0.3
    stream_commission: float = 0.4
    other_commission: float = 0.6
    minimum_commission: float = 0.5
    guarantor_commission_percent: float = 3.0
    guarantor_auto_complete_days: int = 3

class UpdateCommissionSettings(BaseModel):
    trader_commission: Optional[float] = None
    casino_commission: Optional[float] = None
    shop_commission: Optional[float] = None
    stream_commission: Optional[float] = None
    other_commission: Optional[float] = None
    minimum_commission: Optional[float] = None
    guarantor_commission_percent: Optional[float] = None
    guarantor_auto_complete_days: Optional[int] = None


# ==================== ADMIN MODELS ====================

class MerchantApproval(BaseModel):
    approved: bool
    reason: Optional[str] = None
    custom_commission: Optional[float] = None
    withdrawal_commission: Optional[float] = None


# ==================== MESSAGING MODELS ====================

class MessageCreate(BaseModel):
    content: str
    attachment_url: Optional[str] = None

class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    chat_id: str
    sender_id: str
    sender_type: str
    sender_name: str
    content: str
    attachment_url: Optional[str] = None
    created_at: str


# ==================== SUPPORT MODELS ====================

class TicketCreate(BaseModel):
    category: str
    subject: str
    message: str

class TicketMessage(BaseModel):
    content: str


# ==================== SHOP MODELS ====================

class StockItem(BaseModel):
    text: str = ""
    file_url: Optional[str] = None
    photo_url: Optional[str] = None


class DirectTradeCreate(BaseModel):
    amount_usdt: float
    payment_method: str
    requisite_id: Optional[str] = None


class ShopApplicationCreate(BaseModel):
    user_id: str
    merchant_type: Optional[str] = "marketplace"


class ShopApplicationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    status: str
    created_at: str


class PriceVariant(BaseModel):
    quantity: int
    price: float


class ProductCreate(BaseModel):
    title: str
    description: str
    price: float
    currency: str = "USDT"
    category: str
    stock: int = 0
    stock_items: Optional[List[StockItem]] = None
    has_variants: bool = False
    price_variants: Optional[List["PriceVariant"]] = None
    image_urls: Optional[List[str]] = None


class ProductUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    stock: Optional[int] = None
    stock_items: Optional[List[StockItem]] = None
    has_variants: Optional[bool] = None
    price_variants: Optional[List["PriceVariant"]] = None
    image_urls: Optional[List[str]] = None


class ShopSettings(BaseModel):
    banner_url: Optional[str] = None
    description: Optional[str] = None
    auto_delivery: bool = True
    categories: Optional[List[str]] = None


class GuarantorDealCreate(BaseModel):
    product_id: str
    quantity: int
    variant_quantity: Optional[int] = None


class GuarantorDealResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    status: str


class ForumMessageCreate(BaseModel):
    content: str
    reply_to: Optional[str] = None


class ForumMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    content: str
    sender_id: str
    created_at: str


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    order_id: str
    rating: int
    comment: Optional[str] = None
    created_at: str


class TransferRequest(BaseModel):
    recipient_nickname: str
    amount: float


class PrivateMessageCreate(BaseModel):
    content: str
    attachment_url: Optional[str] = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    participants: List[str]
    created_at: str
    last_message_at: Optional[str] = None


class PrivateMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    conversation_id: str
    sender_id: str
    content: str
    created_at: str


class PasswordReset(BaseModel):
    login: str
    recovery_key: str
    new_password: str


class BalanceFreeze(BaseModel):
    user_id: str
    amount: float
    reason: str


class AdminMessage(BaseModel):
    content: str
    recipient_id: Optional[str] = None
    recipient_type: Optional[str] = None


class MaintenanceToggle(BaseModel):
    enabled: bool


class UserRoleUpdate(BaseModel):
    user_id: str
    role: str


class UserBan(BaseModel):
    user_id: str
    reason: str
    days: Optional[int] = None


class BalanceAdjustment(BaseModel):
    user_id: str
    amount: float
    reason: str


class CommissionUpdate(BaseModel):
    user_id: str
    commission_rate: float


class MessageTemplateCreate(BaseModel):
    name: str
    content: str
    category: str = "general"


class MessageTemplateUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
