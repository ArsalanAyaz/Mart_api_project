# from sqlmodel import SQLModel, Field
# from typing import Optional
# from datetime import datetime, timezone

# class Inventory(SQLModel, table=True):
#     id: Optional[int] = Field(default=None, primary_key=True)
#     product_id: int
#     quantity: int
#     location: Optional[str] = None
#     status: str = Field(default="Pending")
#     last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


from sqlmodel import SQLModel, Field
from typing import Optional

class Inventory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str
    price: float