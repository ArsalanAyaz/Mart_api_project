from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables
from app.db import engine
from app.schema import paymentPublic, paymentCreate, paymentUpdate
from app.model import Payments


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== tables creating ===========")
    create_db_and_tables()
    yield
    print("=============== tables created ===========")

app : FastAPI = FastAPI(
    lifespan=lifespan,
    title="payment service",
    version="0.0.1",
    # servers=[
    #     {
    #         "url": "http://127.0.0.1:8002",
    #         "description": "payment service server"
    #     }
    # ]
)    

@app.get("/")
def start():
    return {"service": "payment service"}


@app.post("/create_payment/", response_model=paymentPublic)
def create_payment(payment: paymentCreate):
    with Session(engine) as session:
        db_payment = Payments.model_validate(payment)
        session.add(db_payment)
        session.commit()
        session.refresh(db_payment)
        return db_payment


@app.get("/get_all_payments/", response_model=list[paymentPublic])
def get_all_payments(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        payments = session.exec(select(Payments).offset(offset).limit(limit)).all()
        return payments


@app.get("/get_single_payment/{hero_id}", response_model=paymentPublic)
def get_single_payment(payment_id: int):
    with Session(engine) as session:
        payment = session.get(Payments, payment_id)
        if not payment:
            raise HTTPException(status_code=404, detail="payment not found")
        return payment


@app.patch("/update_payment/{hero_id}", response_model=paymentPublic)
def update_payment(payment_id: int, payment: paymentUpdate):
    with Session(engine) as session:
        db_payment = session.get(Payments, payment_id)
        if not db_payment:
            raise HTTPException(status_code=404, detail="payment not found")
        payment_data = payment.model_dump(exclude_unset=True)
        for key, value in payment_data.items():
            setattr(db_payment, key, value)
        session.add(db_payment)
        session.commit()
        session.refresh(db_payment)
        return db_payment


@app.delete("/delete_payment/{hero_id}")
def delete_payment(payment_id: int):
    with Session(engine) as session:
        payment = session.get(Payments, payment_id)
        if not payment:
            raise HTTPException(status_code=404, detail="payment not found")
        session.delete(payment)
        session.commit()
        return {"ok": "payment deleted successfully"}