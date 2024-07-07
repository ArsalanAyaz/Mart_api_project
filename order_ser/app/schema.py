#
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone



class OrderBase(SQLModel):

    product_id : int
    user_id : int
    quantity : int
    price: float
    status: str
    created_at : datetime 


class UpdateOrder(OrderBase):
    pass 

class CreateOrder(OrderBase):
    pass 

class OrderPublic(OrderBase):
    id : int