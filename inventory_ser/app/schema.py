# from sqlmodel import SQLModel, Field
# from typing import Optional
# from datetime import datetime, timezone

# class InventoryCreate(SQLModel):

#     product_id: int
#     quantity: int
#     location: Optional[str] = None
#     status: str = Field(default="Pending")
#     last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# class ProductCreate(SQLModel):
#     name: str
#     description: Optional[str] = None
#     price: float

# class InventoryPublic(SQLModel):
#     id: int
#     product_id: int
#     quantity: int
#     location: Optional[str] = None
#     status: str = Field(default="Pending")
#     last_updated: datetime

# class InventoryUpdate(SQLModel):
#     product_id: int
#     quantity: int
#     location: Optional[str] = None
#     status: str = Field(default="Pending")
#     last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



from pydantic import BaseModel
from sqlmodel import SQLModel
from typing import Optional

class InventoryCreate(SQLModel):
    name: str
    description: str
    price: float

class InventoryUpdate(SQLModel):
    name: Optional[str]
    description: Optional[str]
    price: Optional[float]

class InventoryPublic(InventoryCreate):
    id: int
