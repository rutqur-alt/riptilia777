from pydantic import BaseModel, Field
from typing import Optional


class QRProviderCreate(BaseModel):
    login: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    display_name: str = Field(..., min_length=2, max_length=100)

    # NSPK (QR) integration settings
    nspk_api_key: str = Field(default="")
    nspk_secret_key: str = Field(default="")
    nspk_api_url: str = Field(default="https://api.trustgain.io")
    nspk_merchant_id: str = Field(default="")
    nspk_gateway_id: str = Field(default="")
    nspk_enabled: bool = Field(default=True)
    nspk_commission_percent: float = Field(default=5.0, ge=0, le=50)

    # TransGrant (CNG) integration settings
    transgrant_api_key: str = Field(default="")
    transgrant_secret_key: str = Field(default="")
    transgrant_api_url: str = Field(default="https://api.trustgain.io")
    transgrant_merchant_id: str = Field(default="")
    transgrant_gateway_id: str = Field(default="")
    transgrant_enabled: bool = Field(default=False)
    transgrant_commission_percent: float = Field(default=7.0, ge=0, le=50)

    # General
    weight: int = Field(default=100, ge=1, le=1000)
    max_concurrent_operations: int = Field(default=10, ge=1, le=100)


class QRProviderUpdate(BaseModel):
    display_name: Optional[str] = None

    # NSPK
    nspk_api_key: Optional[str] = None
    nspk_secret_key: Optional[str] = None
    nspk_api_url: Optional[str] = None
    nspk_merchant_id: Optional[str] = None
    nspk_gateway_id: Optional[str] = None
    nspk_enabled: Optional[bool] = None
    nspk_commission_percent: Optional[float] = None

    # TransGrant
    transgrant_api_key: Optional[str] = None
    transgrant_secret_key: Optional[str] = None
    transgrant_api_url: Optional[str] = None
    transgrant_merchant_id: Optional[str] = None
    transgrant_gateway_id: Optional[str] = None
    transgrant_enabled: Optional[bool] = None
    transgrant_commission_percent: Optional[float] = None

    # General
    weight: Optional[int] = None
    max_concurrent_operations: Optional[int] = None
    is_active: Optional[bool] = None


class QRProviderLogin(BaseModel):
    login: str
    password: str


class QRAggregatorSettings(BaseModel):
    is_enabled: bool = True
    health_check_interval: int = Field(default=45, ge=10, le=300)

    # NSPK settings
    nspk_min_amount: float = Field(default=100, ge=0)
    nspk_max_amount: float = Field(default=500000, ge=0)
    nspk_commission_percent: float = Field(default=5.0, ge=0, le=50)

    # TransGrant settings
    transgrant_min_amount: float = Field(default=100, ge=0)
    transgrant_max_amount: float = Field(default=300000, ge=0)
    transgrant_commission_percent: float = Field(default=7.0, ge=0, le=50)


class WithdrawRequest(BaseModel):
    amount: float = Field(..., gt=0)
    to_address: str = Field(..., min_length=48)


class AdminAdjustBalance(BaseModel):
    amount: float


class QRDisputeRequest(BaseModel):
    reason: str = "Оплата не прошла"


class QRDisputeResolveRequest(BaseModel):
    decision: str
    comment: Optional[str] = None


class QRAggregatorBuyRequest(BaseModel):
    offer_id: str
    amount_usdt: float


class QRAggregatorBuyPublicRequest(BaseModel):
    offer_id: str
    amount_usdt: float
    invoice_id: Optional[str] = None
