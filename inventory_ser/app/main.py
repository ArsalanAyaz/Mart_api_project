from fastapi import FastAPI, HTTPException, Query
from sqlmodel import SQLModel, Session, select
from typing import Optional
from contextlib import asynccontextmanager
from app.db import create_db_and_tables, engine
from app.schema import InventoryPublic, InventoryCreate, InventoryUpdate
from app.model import Inventory
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import asyncio
from app import inventory_pb2
from app.product_model import Products
from app.schema import ProductCreate
from app import product_pb2

async def consumer():
    consumer = AIOKafkaConsumer(
        "product",
        bootstrap_servers="broker:19092",
        group_id="product_inventory_consumer"
    )

    await consumer.start()
    try:
        async for msg in consumer:
            print(f"Serialized data: {msg.value}")
            deserialized_data = product_pb2.Product_proto()
            deserialized_data = product_pb2.Product_proto()
            # deserialized_data = inventory_pb2.Inventory_proto()
            # deserialized_data = inventory_pb2.Inventory_proto()
            deserialized_data.ParseFromString(msg.value)
            print(f"Deserialized data: {deserialized_data}")

            with Session(engine) as session:
                session.begin()
                inventory_data = ProductCreate(
                    name=deserialized_data.name,
                    description=deserialized_data.description,
                    price=deserialized_data.price
                )
                # db_inventory = Inventory.model_validate(inventory_data)
                db_inventory = Products.model_validate(inventory_data)
                session.add(db_inventory)
                session.commit()
                session.refresh(db_inventory)
    except Exception as e:
        print("Consumer error", e)
    finally:
        await consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== Tables creating & Firing event ===========")
    create_db_and_tables()
    task = asyncio.create_task(consumer())
    yield
    task.cancel()
    print("=============== Tables created & Event fired ===========")

app = FastAPI(
    lifespan=lifespan,
    title="inventory service",
    version="0.0.1",
)

@app.get("/")
def start():
    return {"service": "inventory service"}

@app.post("/create_inventory", response_model=InventoryPublic)
async def create_inventory(inventory: InventoryCreate):
    proto_data = inventory_pb2.Inventory_proto(
        product_id=inventory.product_id,
        quantity=inventory.quantity,
        location=inventory.location,
    )
    serialized_data = proto_data.SerializeToString()

    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        with Session(engine) as session:
            session.begin()
            db_inventory = Inventory.model_validate(inventory)
            session.add(db_inventory)
            session.commit()
            session.refresh(db_inventory)

        await producer.send_and_wait("inventory", serialized_data)
    except Exception as e:
        print("create_inventory error", e)
        raise HTTPException(status_code=500, detail="Error sending inventory to Kafka")
    finally:
        await producer.stop()

    last_updated_str = db_inventory.last_updated.isoformat()
    inventory_public = InventoryPublic(
        id=db_inventory.id,
        product_id=db_inventory.product_id,
        quantity=db_inventory.quantity,
        location=db_inventory.location,
        status=db_inventory.status,
        last_updated=last_updated_str
    )

    return inventory_public

@app.get("/get_all_orders/", response_model=list[InventoryPublic])
def get_all_orders(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        inventories = session.exec(select(Inventory).offset(offset).limit(limit)).all()
        return inventories

@app.get("/get_single_order/{order_id}", response_model=InventoryPublic)
def get_single_order(order_id: int):
    with Session(engine) as session:
        inventory = session.get(Inventory, order_id)
        if not inventory:
            raise HTTPException(status_code=404, detail="Order not found")
        return inventory

@app.patch("/update_inventory/{order_id}", response_model=InventoryPublic)
async def update_inventory(order_id: int, inventory: InventoryUpdate):
    proto_data = inventory_pb2.Inventory_proto(
        id=order_id,
        product_id=inventory.product_id,
        quantity=inventory.quantity,
        location=inventory.location,
    )
    serialized_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            db_inventory = session.get(Inventory, order_id)
            if not db_inventory:
                raise HTTPException(status_code=404, detail="Order not found")
            inventory_data = inventory.model_dump(exclude_unset=True)
            for key, value in inventory_data.items():
                setattr(db_inventory, key, value)
            session.add(db_inventory)
            session.commit()
            session.refresh(db_inventory)

            inventory_public = InventoryPublic(
                id=db_inventory.id,
                product_id=db_inventory.product_id,
                quantity=db_inventory.quantity,
                location=db_inventory.location,
                status=db_inventory.status,
                last_updated=db_inventory.last_updated.isoformat()
            )
            
            try:
                await producer.send_and_wait("inventory", serialized_data)
            except Exception as e:
                print(f"Error sending update message to Kafka: {e}")

    return inventory_public

@app.delete("/delete_order/{order_id}")
async def delete_order(order_id: int):
    proto_data = inventory_pb2.Inventory_proto(
        id=order_id,
    )
    serialized_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            inventory = session.get(Inventory, order_id)
            if not inventory:
                raise HTTPException(status_code=404, detail="Order not found")
            session.delete(inventory)
            session.commit()
        
            try:
                await producer.send_and_wait("inventory", serialized_data)
            except Exception as e:
                print(f"Error sending delete message to Kafka: {e}")

    return {"ok": True}
