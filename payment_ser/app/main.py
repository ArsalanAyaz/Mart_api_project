from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables
from app.db import engine
from app.schema import paymentPublic, paymentCreate, paymentUpdate
from app.model import Payments
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import asyncio
import json
from datetime import datetime
import json
from fastapi import HTTPException
from sqlalchemy.orm import Session
from aiokafka import AIOKafkaProducer


async def consumer(topic, broker):
    consumer = AIOKafkaConsumer(
        topic, 
        bootstrap_servers=broker,
        group_id="product_Cons")
    
    await consumer.start()
    try:       
        async for msg in consumer:
            print(f"consumed:  {msg.topic}, {msg.value.decode('utf-8')}")  
    except Exception as e:
        print("consumer error", e)
    finally:  
        await consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== tables creating & Firing event ===========")
    create_db_and_tables()
    task = asyncio.create_task(consumer("payment", "broker:19092"))
    yield
    print("=============== tables created & Event fired ===========")

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

@app.post("/create_payment", response_model=paymentPublic)
async def create_payment(payment: paymentCreate):
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    paymentJson = json.dumps(payment.model_dump()).encode('utf-8')  # Use model_dump for serialization

    await producer.start()

    try:
        await producer.send_and_wait("payment", paymentJson)
    except Exception as e:
        print("create_payment error", e)
        raise HTTPException(status_code=500, detail="Error sending payment to Kafka")
    finally:
        await producer.stop()

    # Save to the database
    with Session(engine) as session:
        db_payment = Payments.model_validate(payment)
        session.add(db_payment)
        session.commit()
        session.refresh(db_payment)
    
    # Return the created payment details
    payment_public = paymentPublic(
        id=db_payment.id, 
        order_id=db_payment.order_id, 
        user_id=db_payment.user_id, 
        amount=db_payment.amount,
        payment_method=db_payment.payment_method,  
        status=db_payment.status,                  
        created_at=db_payment.created_at,          
        updated_at=db_payment.updated_at  
    )
    
    return payment_public





# @app.post("/create_payment", response_model=paymentPublic)
# async def create_payment(payment: paymentCreate):
#     producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
#     paymentJson = json.dumps(payment.model_dump()).encode('utf-8')

#     await producer.start()

#     try:
#         await producer.send_and_wait("payment", paymentJson)
#     except Exception as e:
#         print("create_payment error", e)
#     finally:
#         await producer.stop()

#     with Session(engine) as session:
#         db_payment = Payments.model_validate(payment)
#         session.add(db_payment)
#         session.commit()
#         session.refresh(db_payment)
    
#     payment_public = paymentPublic(
#         id=db_payment.id, 
#         order_id=db_payment.order_id, 
#         user_id=db_payment.user_id, 
#         amount=db_payment.amount
#     )
    
#     return payment_public


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




@app.patch("/update_payment/{payment_id}", response_model=paymentPublic)
async def update_payment(payment_id: int, payment: paymentUpdate):
    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        # Update the payment in the database
        with Session(engine) as session:
            db_payment = session.get(Payments, payment_id)
            if not db_payment:
                raise HTTPException(status_code=404, detail="Payment not found")
            
            # Update payment fields from paymentUpdate model
            payment_data = payment.model_dump(exclude_unset=True)
            for key, value in payment_data.items():
                setattr(db_payment, key, value)
            session.commit()
            session.refresh(db_payment)

        # Convert datetime fields to strings
        created_at_str = db_payment.created_at.isoformat()
        updated_at_str = db_payment.updated_at.isoformat()

        # Create the public payment object
        payment_public = paymentPublic(
            id=db_payment.id, 
            order_id=db_payment.order_id, 
            user_id=db_payment.user_id, 
            amount=db_payment.amount,
            payment_method=db_payment.payment_method,  
            status=db_payment.status,                 
            created_at=created_at_str,  # Convert to string
            updated_at=updated_at_str   # Convert to string
        )
        
        # Serialize payment_public to JSON
        payment_json = {
            "id": payment_public.id,
            "order_id": payment_public.order_id,
            "user_id": payment_public.user_id,
            "amount": payment_public.amount,
            "payment_method": payment_public.payment_method,
            "status": payment_public.status,
            "created_at": str(payment_public.created_at),  # Convert datetime to string
            "updated_at": str(payment_public.updated_at)   # Convert datetime to string
        }

        # Send update message to Kafka
        payment_Json_msg = json.dumps({"action": "update", "payment": payment_json}).encode("utf-8")
        try:
            await producer.send_and_wait("payment", payment_Json_msg)
            print(f"Sent update message to Kafka: {payment_Json_msg}")
        except Exception as e:
            print(f"Error sending update message to Kafka: {e}")

    return payment_public





@app.delete("/delete_payment/{payment_id}")
async def delete_payment(payment_id: int):
    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            payment = session.get(Payments, payment_id)
            if not payment:
                raise HTTPException(status_code=404, detail="payment not found")
            session.delete(payment)
            session.commit()
        
        
        delete_msg = json.dumps({"action": "delete", "payment_id": payment_id}).encode("utf-8")  

        try:
            await producer.send_and_wait("payment", delete_msg)
            print(f"Sent delete message to Kafka: {delete_msg}")
        except Exception as e:
            print(f"Delete error: {e}")
            raise HTTPException(status_code=500, detail="Error sending delete message to Kafka")  

    return {"ok": "payment deleted successfully"}
