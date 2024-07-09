#
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from typing import Optional



class OrderBase(SQLModel):

    product_id : int
    user_id : int
    quantity : int
    price: float
    status: str
    total_price: float
    created_at : datetime = Field(default_factory=lambda: datetime.now(timezone.now))
    


class UpdateOrder(SQLModel):

    product_id : Optional[int] = None
    user_id : Optional[int] = None
    quantity : Optional[int] = None
    price: Optional[float] = None
    status: Optional[str] = None
    total_price : Optional[float] = None
    updated_at : datetime = Field(default_factory=lambda: datetime.now(timezone.now))

class CreateOrder(SQLModel):

    product_id : int
    user_id : int
    quantity : int
    price: float
    status: str
    total_price: float
    created_at : datetime = Field(default_factory=lambda: datetime.now(timezone.now))
     

class OrderPublic(OrderBase):
    id : int