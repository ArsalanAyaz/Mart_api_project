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
from datetime import datetime, timezone
import json
from fastapi import HTTPException
from sqlalchemy.orm import Session
from aiokafka import AIOKafkaProducer
from app import payment_pb2
from sqlalchemy.orm import Session
from sqlalchemy import select
from google.protobuf.timestamp_pb2 import Timestamp



async def consumer(topic, broker):
    consumer = AIOKafkaConsumer(
        topic, 
        bootstrap_servers=broker,
        group_id="product_Cons1")
    
    await consumer.start()
    try:       
        async for msg in consumer:
            print(f"Serialized message ......: {msg.value}")
            Deserialized_payment_data = payment_pb2.Payment_proto()
            Deserialized_payment_data.ParseFromString(msg.value) 
            print(f"Derialized message ......: {Deserialized_payment_data}") 
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
)    



@app.get("/")
def start():
    return {"service": "payment service"}

@app.post("/create_payment", response_model=paymentPublic)
async def create_payment(payment: paymentCreate):

    proto_data = payment_pb2.Payment_proto(

        order_id = payment.order_id,
        user_id = payment.user_id,
        amount = payment.amount,
        payment_method = payment.payment_method,
        status = payment.status,

    )

    Serialized_payment_data = proto_data.SerializeToString()


    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    #paymentJson = json.dumps(payment.model_dump()).encode('utf-8')  # Use model_dump for serialization

    await producer.start()

    try:
        await producer.send_and_wait("payment", Serialized_payment_data)
        # await producer.send_and_wait("payment", paymentJson)
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





@app.get("/get_all_payments/", response_model=list[paymentPublic])
def get_all_payments(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        query = session.execute(select(Payments).offset(offset).limit(limit))
        payments = query.scalars().all()
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

    proto_data = payment_pb2.Payment_proto()
    proto_data.id = payment_id
    proto_data.order_id = payment.order_id
    proto_data.user_id = payment.user_id
    proto_data.amount = payment.amount
    proto_data.payment_method = payment.payment_method
    proto_data.status = payment.status

    # Create a Timestamp object for updated_at
    updated_at_proto = Timestamp()
    updated_at_proto.GetCurrentTime()  # Sets to current time

    proto_data.updated_at.CopyFrom(updated_at_proto)  # Set updated_at field


    Serialized_payment_data = proto_data.SerializeToString()

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
        
       
        try:
            await producer.send_and_wait("payment", Serialized_payment_data)
            print(f"Sent update message to Kafka: {Serialized_payment_data}")
            
        except Exception as e:
            print(f"Error sending update message to Kafka: {e}")

    return payment_public





@app.delete("/delete_payment/{payment_id}")
async def delete_payment(payment_id: int):

    proto_data = payment_pb2.Payment_proto(
        id = payment_id,
    )

    Serialized_payment_data= proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            payment = session.get(Payments, payment_id)
            if not payment:
                raise HTTPException(status_code=404, detail="payment not found")
            session.delete(payment)
            session.commit()
        
        
        #delete_msg = json.dumps({"action": "delete", "payment_id": payment_id}).encode("utf-8")  

        try:
            await producer.send_and_wait("payment", Serialized_payment_data)
            print(f"Sent delete message to Kafka: {Serialized_payment_data}")
            # await producer.send_and_wait("payment", delete_msg)
            # print(f"Sent delete message to Kafka: {delete_msg}")
        except Exception as e:
            print(f"Delete error: {e}")
            raise HTTPException(status_code=500, detail="Error sending delete message to Kafka")  

    return {"ok": "payment deleted successfully"}
