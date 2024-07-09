from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select, SQLModel
from contextlib import asynccontextmanager
from app.db import create_db_and_tables, engine
from app.schema import OrderPublic, UpdateOrder, CreateOrder
from app.model import Orderss
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import asyncio
from app import order_pb2
from google.protobuf.timestamp_pb2 import Timestamp

async def consumer(topic, broker):
    consumer = AIOKafkaConsumer(
        topic, 
        bootstrap_servers=broker,
        group_id="order_Cons"
    )
    
    await consumer.start()
    try:       
        async for msg in consumer:
            print(f"Serialized Messages ....:  {msg.value}")
            Deserialized_order_data = order_pb2.Orders_proto()
            Deserialized_order_data.ParseFromString(msg.value)
            print("Deserialized Message ...", Deserialized_order_data)
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
    title="order service",
    version="0.0.1",
)    

@app.get("/")
def start():
    return {"service": "order service"}

@app.post("/create_order", response_model=OrderPublic)
async def create_order(order: CreateOrder):

    proto_data = order_pb2.Orders_proto()
    proto_data.product_id = order.product_id
    proto_data.user_id  = order.user_id
    proto_data.quantity = order.quantity
    proto_data.price = order.price
    proto_data.status = order.status
    proto_data.total_price = order.total_price

    time = Timestamp()
    time.GetCurrentTime()
    proto_data.created_at.CopyFrom(time)

    Serialized_order_data = proto_data.SerializeToString()

    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')

    await producer.start()

    try:
        await producer.send_and_wait("order", Serialized_order_data)
    except Exception as e:
        print("Error sending order to Kafka:", e)
        raise HTTPException(status_code=500, detail="Error sending order to Kafka")
    finally:
        await producer.stop()

    with Session(engine) as session:
        db_order = Orderss.model_validate(order)
        session.add(db_order)
        session.commit()
        session.refresh(db_order)

    order_public = OrderPublic(
        id=db_order.id,
        product_id=db_order.product_id,
        user_id=db_order.user_id,
        quantity=db_order.quantity,
        price=db_order.price,
        status=db_order.status,
        total_price=db_order.total_price,  # Added this line
        created_at=db_order.created_at
    )

    return order_public

@app.get("/get_all_orders/", response_model=list[OrderPublic])
def get_all_orders(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        statement = select(Orderss).offset(offset).limit(limit)
        results = session.exec(statement)
        orders = results.all()
        return orders

@app.get("/get_single_order/{order_id}", response_model=OrderPublic)
def get_single_order(order_id: int):
    with Session(engine) as session:
        order = session.get(Orderss, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="order not found")
        return order

@app.patch("/update_order/{order_id}", response_model=OrderPublic)
async def update_order(order_id: int, order: UpdateOrder):

    proto_data = order_pb2.Orders_proto()

    proto_data.id = order_id
    proto_data.product_id = order.product_id
    proto_data.user_id = order.user_id
    proto_data.quantity = order.quantity
    proto_data.price= order.price
    proto_data.status = order.status
    proto_data.total_price = order.total_price
      
    time = Timestamp()
    time.GetCurrentTime()
    proto_data.updated_at.CopyFrom(time)


    Serialized_order_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            db_order = session.get(Orderss, order_id)
            if not db_order:
                raise HTTPException(status_code=404, detail="Order not found")
            
            order_data = order.model_dump(exclude_unset=True)
            for key, value in order_data.items():
                setattr(db_order, key, value)
            session.commit()
            session.refresh(db_order)

        created_at_str = db_order.created_at.isoformat()

        order_public = OrderPublic(
            id=db_order.id, 
            product_id=db_order.product_id, 
            user_id=db_order.user_id, 
            quantity=db_order.quantity,
            price=db_order.price,  
            status=db_order.status,                  
            created_at=created_at_str,
            total_price=db_order.total_price  # Added this line
        )

        try:
            await producer.send_and_wait("order", Serialized_order_data)
            print(f"Sent update message to Kafka: {Serialized_order_data}")
        except Exception as e:
            print(f"Error sending update message to Kafka: {e}")

    return order_public

@app.delete("/delete_order/{order_id}")
async def delete_order(order_id: int):

    proto_data = order_pb2.Orders_proto(
        id= order_id,
    )

    Serialized_order_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            order = session.get(Orderss, order_id)
            if not order:
                raise HTTPException(status_code=404, detail="order not found")
            session.delete(order)
            session.commit()

        try:
            await producer.send_and_wait("order", Serialized_order_data)
            print(f"Sent delete message to Kafka: {Serialized_order_data}")
        except Exception as e:
            print(f"Delete error: {e}")
            raise HTTPException(status_code=500, detail="Error sending delete message to Kafka")  

    return {"ok": "order deleted successfully"}
