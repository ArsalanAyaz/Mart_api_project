from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select, SQLModel
from contextlib import asynccontextmanager
from app.db import create_db_and_tables, engine
from app.schema import OrderPublic, UpdateOrder, CreateOrder
from app.model import Orders
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import asyncio
import json
from fastapi import HTTPException


async def consumer(topic, broker):
    consumer = AIOKafkaConsumer(
        topic, 
        bootstrap_servers=broker,
        group_id="order_Cons"
    )
    
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
    task = asyncio.create_task(consumer("order", "broker:19092"))
    yield
    print("=============== tables created & Event fired ===========")

app = FastAPI(
    lifespan=lifespan,
    title="payment service",
    version="0.0.1",
)    

@app.get("/")
def start():
    return {"service": "payment service"}

@app.post("/create_order", response_model=OrderPublic)
async def create_order(order: CreateOrder):
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')

    # Serialize order data for Kafka
    order_dict = order.model_dump()  # Assuming model_dump() returns a dictionary
    order_dict['created_at'] = order.created_at.isoformat()  # Convert datetime to ISO string

    orderJson = json.dumps(order_dict).encode('utf-8')

    await producer.start()

    try:
        await producer.send_and_wait("order", orderJson)
    except Exception as e:
        print("Error sending order to Kafka:", e)
        raise HTTPException(status_code=500, detail="Error sending order to Kafka")
    finally:
        await producer.stop()

    # Save to the database
    with Session(engine) as session:
        db_order = Orders.model_validate(order)
        session.add(db_order)
        session.commit()
        session.refresh(db_order)

    # Create the public order object to return
    order_public = OrderPublic(
        id=db_order.id,
        product_id=db_order.product_id,
        user_id=db_order.user_id,
        quantity=db_order.quantity,
        price=db_order.price,
        status=db_order.status,
        created_at=db_order.created_at  # Assuming db_order.created_at is already a datetime object
    )

    return order_public

@app.get("/get_all_orders/", response_model=list[OrderPublic])
def get_all_orders(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        statement = select(Orders).offset(offset).limit(limit)
        results = session.exec(statement)
        orders = results.all()
        return orders

@app.get("/get_single_order/{order_id}", response_model=OrderPublic)
def get_single_order(order_id: int):
    with Session(engine) as session:
        order = session.get(Orders, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="order not found")
        return order

@app.patch("/update_order/{order_id}", response_model=OrderPublic)
async def update_order(order_id: int, order: UpdateOrder):
    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        # Update the order in the database
        with Session(engine) as session:
            db_order = session.get(Orders, order_id)
            if not db_order:
                raise HTTPException(status_code=404, detail="Order not found")
            
            # Update order fields from orderUpdate model
            order_data = order.model_dump(exclude_unset=True)
            for key, value in order_data.items():
                setattr(db_order, key, value)
            session.commit()
            session.refresh(db_order)

        # Convert datetime fields to strings
        created_at_str = db_order.created_at.isoformat()

        # Create the public order object
        order_public = OrderPublic(
            id=db_order.id, 
            product_id=db_order.product_id, 
            user_id=db_order.user_id, 
            quantity=db_order.quantity,
            price=db_order.price,  
            status=db_order.status,                  
            created_at=created_at_str
        )
        
        # Serialize order_public to JSON
        order_json = {
            "id": order_public.id,
            "product_id": order_public.product_id,
            "user_id": order_public.user_id,
            "quantity": order_public.quantity,
            "price": order_public.price,
            "status": order_public.status,
            "created_at": str(order_public.created_at)
        }

        # Send update message to Kafka
        order_json_msg = json.dumps({"action": "update", "order": order_json}).encode("utf-8")
        try:
            await producer.send_and_wait("order", order_json_msg)
            print(f"Sent update message to Kafka: {order_json_msg}")
        except Exception as e:
            print(f"Error sending update message to Kafka: {e}")

    return order_public

@app.delete("/delete_order/{order_id}")
async def delete_order(order_id: int):
    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            order = session.get(Orders, order_id)
            if not order:
                raise HTTPException(status_code=404, detail="order not found")
            session.delete(order)
            session.commit()
        
        
        delete_msg = json.dumps({"action": "delete", "order_id": order_id}).encode("utf-8")  

        try:
            await producer.send_and_wait("order", delete_msg)
            print(f"Sent delete message to Kafka: {delete_msg}")
        except Exception as e:
            print(f"Delete error: {e}")
            raise HTTPException(status_code=500, detail="Error sending delete message to Kafka")  

    return {"ok": "order deleted successfully"}
