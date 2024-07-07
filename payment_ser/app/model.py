from sqlmodel import SQLModel , Field
from typing import Optional
from datetime import datetime, timezone



class Payments(SQLModel, table=True):

    id : Optional[int] =Field(default=None, primary_key=True)
    order_id: int
    user_id: int
    amount: float
    payment_method: str
    status: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))