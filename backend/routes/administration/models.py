from pydantic import BaseModel
from typing import Optional

class MaintenanceToggle(BaseModel):
    enabled: bool
    message: Optional[str] = "Ведутся технические работы"

class PasswordReset(BaseModel):
    new_password: str

class BalanceFreeze(BaseModel):
    frozen: bool
    reason: Optional[str] = None

class AdminMessage(BaseModel):
    content: str

class MessageTemplateCreate(BaseModel):
    title: str
    content: str
    category: str = "general"  # general, merchant_app, shop_app, dispute, support, guarantor

class MessageTemplateUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None

class DisputeResolution(BaseModel):
    decision: str

class MessageCreate(BaseModel):
    content: str
