
from pydantic import BaseModel, ConfigDict
from typing import Optional

class ReviewCreate(BaseModel):
    shop_id: str
    rating: int  # 1-5
    comment: Optional[str] = None
    purchase_id: Optional[str] = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    shop_id: str
    reviewer_id: str
    reviewer_nickname: str
    rating: int
    comment: Optional[str] = None
    purchase_id: Optional[str] = None
    created_at: str
