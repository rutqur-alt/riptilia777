
from pydantic import BaseModel

class TransferRequest(BaseModel):
    recipient_nickname: str
    amount: float
