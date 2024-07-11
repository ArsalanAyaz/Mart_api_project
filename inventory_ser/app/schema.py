from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone



class InventoryCreate(SQLModel):

    product_id: int
    quantity: int
    location: Optional[str] = None

class ProductCreate(SQLModel):

    name: str
    description : Optional[str] = None
    price: float


class InventoryPublic(SQLModel):

    id: int
    product_id: int
    quantity: int
    location: Optional[str] = None
    status: str = Field(default="Pending")
    last_updated: datetime



class InventoryUpdate(SQLModel):
    
    product_id: Optional[int] = None
    quantity: Optional[int] = None
    location: Optional[str] = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))