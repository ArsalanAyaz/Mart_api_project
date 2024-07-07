from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables
from app.db import engine
from app.model import Orders
from app.schema import UpdateOrder,CreateOrder, OrderPublic


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== tables creating ===========")
    create_db_and_tables()
    yield
    print("=============== tables created ===========")

app : FastAPI = FastAPI(
    lifespan=lifespan,
    title="Order service",
    version="0.0.1",
    # servers=[
    #     {
    #         "url": "http://127.0.0.1:8003",
    #         "description": "Order service server"
    #     }
    # ]
)    

@app.get("/")
def start():
    return {"service": "order service"}



@app.post("/create_order/", response_model=OrderPublic)
def create_order(order: CreateOrder):
    with Session(engine) as session:
        db_order = Orders.model_validate(order)
        session.add(db_order)
        session.commit()
        session.refresh(db_order)
        return db_order


@app.get("/get_all_orders/", response_model=list[OrderPublic])
def get_all_orders(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        orders = session.exec(select(Orders).offset(offset).limit(limit)).all()
        return orders


@app.get("/get_single_order/{hero_id}", response_model=OrderPublic)
def get_single_order(order_id: int):
    with Session(engine) as session:
        order = session.get(Orders, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="order not found")
        return order


@app.patch("/update_order/{hero_id}", response_model=OrderPublic)
def update_order(order_id: int, order: UpdateOrder):
    with Session(engine) as session:
        db_order = session.get(Orders, order_id)
        if not db_order:
            raise HTTPException(status_code=404, detail="order not found")
        order_data = order.model_dump(exclude_unset=True)
        for key, value in order_data.items():
            setattr(db_order, key, value)
        session.add(db_order)
        session.commit()
        session.refresh(db_order)
        return db_order


@app.delete("/delete_order/{hero_id}")
def delete_order(order_id: int):
    with Session(engine) as session:
        order = session.get(Orders, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="order not found")
        session.delete(order)
        session.commit()
        return {"ok": True}