from sqlmodel import SQLModel , Field
from typing import Optional
from datetime import datetime, timezone

class NotificationCreate(SQLModel):

    user_id: int
    message: str
    type: str
    status: str = Field(default="pending")

class NotificationPublic(SQLModel):

    id: int
    user_id: int
    message: str
    type: str
    status: str = Field(default="pending")
    created_at: datetime
    updated_at: datetime

class NotificationUpdate(SQLModel):

    user_id: Optional[int] = None
    message: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))