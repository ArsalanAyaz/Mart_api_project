from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone




class paymentCreate(SQLModel):

    order_id: int
    user_id: int
    amount: float
    payment_method: str
    status: str = Field(default="pending")



class paymentUpdate(SQLModel):

    order_id: Optional[int] = None
    user_id: Optional[int] = None
    amount: Optional[float] = None
    payment_method: Optional[str] = None
    status: Optional[str] = None  
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.now)) 




class paymentPublic(SQLModel):
    id: int
    order_id: int
    user_id: int
    amount: float
    payment_method: str
    status: str
    created_at: datetime
    updated_at: datetime    
