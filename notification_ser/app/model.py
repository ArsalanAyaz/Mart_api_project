from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone

class Notifications(SQLModel, table=True):

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int  
    message: str
    type: str  #  'email', 'sms', 'push'
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))