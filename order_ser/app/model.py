from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone


class Orders(SQLModel, table=True):

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id : int
    user_id : int
    quantity : int
    price: float
    status: str
    created_at : datetime = Field(default_factory=lambda: datetime.now(timezone.utc))