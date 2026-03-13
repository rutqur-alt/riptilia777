
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class RequisiteCreate(BaseModel):
    type: str = Field(..., description="card, sbp, qr, etc.")
    data: Dict[str, Any] = Field(..., description="Requisite details")
    is_active: bool = True

class RequisiteResponse(BaseModel):
    id: str
    trader_id: str
    type: str
    data: Dict[str, Any]
    is_active: bool
    created_at: datetime
