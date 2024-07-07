from sqlmodel import SQLModel, Field
from typing import Optional


class UserBase(SQLModel):
    # id: int | None = Field(default=None)
    name: str
    password: str
    email: str
    phone: str

class UserCreate(UserBase):
    pass

class UserUpdate(UserBase):
    pass

class UserPublic(UserBase):
    id: int