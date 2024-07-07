from sqlmodel import SQLModel
from typing import Annotated, Optional


class productBase(SQLModel):

    name: str
    description : Optional[str] = None
    price: float


class productCreate(productBase):
    pass    
 

class productUpdate(productBase):
    pass 

class productPublic(productBase):
    id: int

    class Config:
        orm_mode = True 
