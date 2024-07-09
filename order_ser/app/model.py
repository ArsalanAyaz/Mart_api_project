from sqlmodel import Field, SQLModel
from datetime import datetime
from typing import Optional

class Orderss(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int
    user_id: int
    quantity: int
    price: float
    status: str
    total_price: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
