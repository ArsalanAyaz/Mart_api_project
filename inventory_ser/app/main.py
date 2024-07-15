from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables, engine
from app.model import Inventory
from app.schema import InventoryCreate, InventoryPublic, InventoryUpdate
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import asyncio
from app import inventory_pb2



async def start_consumer(topic, broker):
    kafka_consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=broker,
        group_id="product_inventory_Consumer"
    )

    await kafka_consumer.start()
    try:
        async for msg in kafka_consumer:
            print(f"Serialized message in consumer: {msg.value}")
            deserialized_inventory_data = inventory_pb2.Inventory_proto()
            deserialized_inventory_data.ParseFromString(msg.value)
            print(f"Deserialized message in consumer: {deserialized_inventory_data}")

            # Convert the deserialized data to a dictionary
            data_dict = {
                # "id": deserialized_inventory_data.id,
                "name": deserialized_inventory_data.name,
                "description": deserialized_inventory_data.description,
                "price": deserialized_inventory_data.price
            }

            # Sending data from product-topic to inventory database
            with Session(engine) as session:
                db_inventory = Inventory.model_validate(data_dict)
                session.add(db_inventory)
                session.commit()
                session.refresh(db_inventory)

    except Exception as e:
        print(f"Consumer error: {e}")
    finally:
        await kafka_consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== Tables creating & event firing ============")
    create_db_and_tables()
    consumer_task = asyncio.create_task(start_consumer("product", "broker:19092"))  # consumer of product-topic
    yield
    print("=============== Tables created & event fired ============")


app = FastAPI(lifespan=lifespan, title="inventory service")


@app.get("/")
def start():
    return {"service": "inventory service"}

@app.post("/create_inventory", response_model=InventoryPublic)
async def create_inventory(inventory: InventoryCreate):
    proto_data = inventory_pb2.Inventory_proto(
        name=inventory.name,
        description=inventory.description,
        price=inventory.price
    )

    serialized_inventory_data = proto_data.SerializeToString()

    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        with Session(engine) as session:
            db_inventory = Inventory.model_validate(inventory.dict())
            session.add(db_inventory)
            session.commit()
            session.refresh(db_inventory)

        await producer.send_and_wait("inventory", serialized_inventory_data)
    except Exception as e:
        session.rollback()
        print(f"Producer error: {e}")
        raise HTTPException(status_code=500, detail="Error creating inventory")
    finally:
        await producer.stop()

    return InventoryPublic.from_orm(db_inventory)

@app.get("/get_all_inventorys/", response_model=list[InventoryPublic])
def get_all_inventorys(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        inventorys = session.exec(select(Inventory).offset(offset).limit(limit)).all()
        return inventorys

@app.get("/get_single_inventory/{inventory_id}", response_model=InventoryPublic)
def get_single_inventory(inventory_id: int):
    with Session(engine) as session:
        inventory = session.get(Inventory, inventory_id)
        if not inventory:
            raise HTTPException(status_code=404, detail="inventory not found")
        return inventory

@app.patch("/update_inventory/{inventory_id}", response_model=InventoryPublic)
async def update_inventory(inventory_id: int, inventory: InventoryUpdate):
    proto_data = inventory_pb2.Inventory_proto(
        id=inventory_id,
        name=inventory.name,
        description=inventory.description,
        price=inventory.price
    )

    serialized_inventory_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            db_inventory = session.get(Inventory, inventory_id)
            if not db_inventory:
                raise HTTPException(status_code=404, detail="inventory not found")
            inventory_data = inventory.model_dump(exclude_unset=True)
            for key, value in inventory_data.items():
                setattr(db_inventory, key, value)
            session.add(db_inventory)
            session.commit()
            session.refresh(db_inventory)

            try:
                await producer.send_and_wait("inventory", serialized_inventory_data)
            except Exception as e:
                print(f"Error sending update message to Kafka: {e}")

    return InventoryPublic.from_orm(db_inventory)

@app.delete("/delete_inventory/{inventory_id}")
async def delete_inventory(inventory_id: int):
    proto_data = inventory_pb2.Inventory_proto(id=inventory_id)
    serialized_inventory_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            inventory = session.get(Inventory, inventory_id)
            if not inventory:
                raise HTTPException(status_code=404, detail="inventory not found")
            session.delete(inventory)
            session.commit()

            try:
                await producer.send_and_wait("inventory", serialized_inventory_data)
            except Exception as e:
                print(f"Error sending delete message to Kafka: {e}")

    return {"ok": True}
