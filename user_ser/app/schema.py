from sqlmodel import SQLModel
from typing import Optional

class UserBase(SQLModel):
    name: str
    password: str
    email: str
    phone: str

class UserCreate(UserBase):
    pass

class UserUpdate(SQLModel):
    name: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class UserPublic(UserBase):
    id: int
