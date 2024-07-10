from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables
from app.db import engine
from app.schema import InventoryPublic, InventoryCreate, InventoryUpdate
from app.model import Inventory
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import asyncio
import json
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app import inventory_pb2
from google.protobuf.timestamp_pb2 import Timestamp





# ====== Consumer function for the order_service topic

async def consumer(topic, broker):
    consumer = AIOKafkaConsumer(
        topic, 
        bootstrap_servers=broker,
        group_id="order_Inventory_consumer") # order_service is producer and inventory_ser is consumer
    
    await consumer.start()
    try:       
        async for msg in consumer:
            print(f"Serialized data ....:   {msg.value}")
            Deserialized_data = inventory_pb2.Inventory_proto()
            Deserialized_data.ParseFromString(msg.value)
            print(f"Serialized data ....:   {Deserialized_data}")  
    except Exception as e:
        print("consumer error", e)
    finally:  
        await consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== tables creating & Firing event ===========")
    create_db_and_tables()
    task = asyncio.create_task(consumer("order", "broker:19092")) # consuming from order-topic
    yield
    print("=============== tables created & Event fired ===========")








app : FastAPI = FastAPI(
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

        product_id = inventory.product_id,
        quantity = inventory.quantity,
        location = inventory.location,

    )

    Serialized_data = proto_data.SerializeToString()


    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    # inventory_json = json.dumps(inventory.model_dump()).encode('utf-8')  # Use model_dump for serialization

    await producer.start()

    try:
        await producer.send_and_wait("inventory", Serialized_data)
        # await producer.send_and_wait("inventory", inventory_json)
    except Exception as e:
        print("create_inventory error", e)
        raise HTTPException(status_code=500, detail="Error sending inventory to Kafka")
    finally:
        await producer.stop()

    # Save to the database
    with Session(engine) as session:  # Ensure using Session from sqlmodel
        db_inventory = Inventory.model_validate(inventory)  # Validate model correctly
        session.add(db_inventory)
        session.commit()
        session.refresh(db_inventory)
    
    
    last_updated_str = db_inventory.last_updated.isoformat()  # Convert datetime to string

    # Create the public inventory object
    inventory_public = InventoryPublic(
        id=db_inventory.id, 
        product_id=db_inventory.product_id, 
        quantity=db_inventory.quantity,
        location=db_inventory.location,  
        status=db_inventory.status,                 
        last_updated=last_updated_str   # Use converted string
    )
        
    # # Serialize inventory_public to JSON
    # inventory_json = {
    #     "id": inventory_public.id,
    #     "product_id": inventory_public.product_id,
    #     "quantity": inventory_public.quantity,
    #     "location": inventory_public.location,
    #     "status": inventory_public.status,
    #     "last_updated": str(inventory_public.last_updated)   # Convert datetime to string
    # }
    
    return inventory_public



@app.get("/get_all_orders/", response_model=list[InventoryPublic])
def get_all_orders(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        statement = select(Inventory).offset(offset).limit(limit)
        results = session.execute(statement)
        orders = results.scalars().all()
        return orders


@app.get("/get_single_inventory/{hero_id}", response_model=InventoryPublic)
def get_single_inventory(inventory_id: int):
    with Session(engine) as session:
        inventory = session.get(Inventory, inventory_id)
        if not inventory:
            raise HTTPException(status_code=404, detail="inventory not found")
        return inventory




@app.patch("/update_inventory/{inventory_id}", response_model=InventoryPublic)
async def update_inventory(inventory_id: int, inventory: InventoryUpdate):

    proto_data = inventory_pb2.Inventory_proto()
    proto_data.id = inventory_id
    proto_data.product_id = inventory.product_id
    proto_data.quantity= inventory.quantity
    proto_data.location= inventory.location

    time = Timestamp()
    time.GetCurrentTime()
    proto_data.last_updated.CopyFrom(time)



    Serialized_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        # Update the inventory in the database
        with Session(engine) as session:
            db_inventory = session.get(Inventory, inventory_id)
            if not db_inventory:
                raise HTTPException(status_code=404, detail="inventory not found")
            
            # Update inventory fields from inventoryUpdate model
            inventory_data = inventory.model_dump(exclude_unset=True)
            for key, value in inventory_data.items():
                setattr(db_inventory, key, value)
            session.commit()
            session.refresh(db_inventory)

        # Convert datetime fields to strings
        last_updated_str = db_inventory.last_updated.isoformat()  # Convert datetime to string

        # Create the public inventory object
        inventory_public = InventoryPublic(
            id=db_inventory.id, 
            product_id=db_inventory.product_id, 
            quantity=db_inventory.quantity,
            location=db_inventory.location,  
            status=db_inventory.status,                 
            last_updated=last_updated_str   # Use converted string
        )
            
        # # Serialize inventory_public to JSON
        # inventory_json = {
        #     "id": inventory_public.id,
        #     "product_id": inventory_public.product_id,
        #     "quantity": inventory_public.quantity,
        #     "location": inventory_public.location,
        #     "status": inventory_public.status,
        #     "last_updated": str(inventory_public.last_updated)   # Convert datetime to string
        # }
    
        # Send update message to Kafka
        # inventory_Json_msg = json.dumps({"action": "update", "inventory": inventory_json}).encode("utf-8")
        try:
            await producer.send_and_wait("inventory", Serialized_data)
            print(f"Sent update message to Kafka: {Serialized_data}")
            # await producer.send_and_wait("inventory", inventory_Json_msg)
            # print(f"Sent update message to Kafka: {inventory_Json_msg}")
        except Exception as e:
            print(f"Error sending update message to Kafka: {e}")

    return inventory_public





@app.delete("/delete_inventory/{inventory_id}")
async def delete_inventory(inventory_id: int):

    proto_data = inventory_pb2.Inventory_proto(
        id = inventory_id,
    )

    Serialized_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            inventory = session.get(Inventory, inventory_id)
            if not inventory:
                raise HTTPException(status_code=404, detail="inventory not found")
            session.delete(inventory)
            session.commit()
        
        
        # delete_msg = json.dumps({"action": "delete", "inventory_id": inventory_id}).encode("utf-8")  

        try:
            await producer.send_and_wait("inventory", Serialized_data)
            print(f"Sent delete message to Kafka: {Serialized_data}")
            # await producer.send_and_wait("inventory", delete_msg)
            # print(f"Sent delete message to Kafka: {delete_msg}")
        except Exception as e:
            print(f"Delete error: {e}")
            raise HTTPException(status_code=500, detail="Error sending delete message to Kafka")  

    return {"ok": "inventory deleted successfully"}
