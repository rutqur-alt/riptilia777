from pydantic import BaseModel, Field
from typing import Optional

class InvoiceCreateRequest(BaseModel):
    """Запрос на создание инвойса"""
    merchant_id: str = Field(..., description="ID мерчанта в системе")
    order_id: str = Field(..., description="Уникальный ID заказа в системе мерчанта")
    amount: float = Field(..., gt=0, description="Сумма к оплате в рублях")
    currency: str = Field(default="RUB", description="Код валюты")
    user_id: Optional[str] = Field(None, description="ID пользователя в системе мерчанта")
    callback_url: str = Field(..., description="URL для callback уведомлений")
    description: Optional[str] = Field(None, description="Описание платежа")
    payment_method: Optional[str] = Field(None, description="Метод оплаты")
    sign: str = Field(..., description="HMAC-SHA256 подпись запроса")


class InvoiceStatusRequest(BaseModel):
    """Запрос статуса инвойса"""
    merchant_id: str
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    sign: str


class SelectOperatorRequest(BaseModel):
    operator_id: str
    payment_method: str


class SendMessageRequest(BaseModel):
    message: str


class LinkTradeRequest(BaseModel):
    trade_id: str


class DisputeOpenRequest(BaseModel):
    reason: str
    description: Optional[str] = None


class DisputeMessageRequest(BaseModel):
    message: str
