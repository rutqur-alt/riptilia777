from pydantic import BaseModel
from typing import Optional

class AuthRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str

class CreateInvoiceRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    amount_rub: int  # Сумма пополнения клиента (то что он получит на сайте мерчанта)
    order_id: Optional[str] = None
    description: Optional[str] = "Пополнение баланса"
    callback_url: Optional[str] = None
    signature: Optional[str] = None

class InvoiceStatusRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    invoice_id: str

class BalanceRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str

class TransactionsRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    status: Optional[str] = None
    limit: int = 50
    offset: int = 0

class OperatorsRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    amount_rub: float

class RequisitesRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    invoice_id: str
    operator_id: str
    method: str

class MarkPaidRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    invoice_id: str

class OpenDisputeRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    invoice_id: str
    reason: str

class DisputeMessagesRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    invoice_id: str

class SendDisputeMessageRequest(BaseModel):
    api_key: str
    api_secret: str
    merchant_id: str
    invoice_id: str
    message: str
