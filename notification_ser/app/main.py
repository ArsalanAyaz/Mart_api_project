from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables
from app.db import engine
from app.schema import NotificationPublic, NotificationCreate, NotificationUpdate
from app.model import Notifications
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import asyncio
import json
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app import notifi_pb2
from google.protobuf.timestamp_pb2 import Timestamp



# Order Service to Notification Service

# order_service (Producer): After processing an order, order_service publishes an OrderProcessed event to the order-processed # topic.
# notification_service (Consumer): notification_service subscribes to the order-processed topic, processes the OrderProcessed # event, and sends notifications to the user.




# ===== function for order_ser topic

async def consumer(topic, broker):
    consumer = AIOKafkaConsumer(
        topic, 
        bootstrap_servers=broker,
        group_id="order_notification_Consumer") # order_ser is producer and notification_ser is consumer
    
    await consumer.start()
    try:       
        async for msg in consumer:
            print(f"Serialized Data .......:   {msg.value}") 
            Deserialized_data =  notifi_pb2.Notification_proto()
            Deserialized_data.ParseFromString(msg.value)
            print(f"Deserialized Data .......:   {Deserialized_data}")
    except Exception as e:
        print("consumer error", e)
    finally:  
        await consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== tables creating & Firing event ===========")
    create_db_and_tables()
    task = asyncio.create_task(consumer("order", "broker:19092")) # consumer of order-topic
    yield
    print("=============== tables created & Event fired ===========")








app : FastAPI = FastAPI(
    lifespan=lifespan,
    title="notification service",
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
    return {"service": "notification service"}



@app.post("/create_notification", response_model=NotificationPublic)
async def create_notification(notification: NotificationCreate):

    proto_data = notifi_pb2.Notification_proto(
        
        user_id = notification.user_id,
        message = notification.message,
        type = notification.type,
        status = notification.status,
    )

    Serialized_data = proto_data.SerializeToString()

    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    #notification_json = json.dumps(notification.model_dump()).encode('utf-8')  # Use model_dump for serialization

    await producer.start()

    try:
        await producer.send_and_wait("notification", Serialized_data)
    except Exception as e:
        print("create_notification error", e)
        raise HTTPException(status_code=500, detail="Error sending notification to Kafka")
    finally:
        await producer.stop()

    # Save to the database
    with Session(engine) as session:  # Ensure using Session from sqlmodel
        db_notification = Notifications.model_validate(notification)  # Validate model correctly
        session.add(db_notification)
        session.commit()
        session.refresh(db_notification)
    
    created_at_str = db_notification.created_at.isoformat()  # Convert datetime to string
    updated_at_str = db_notification.updated_at.isoformat()  # Convert datetime to string

    # Create the public notification object
    notification_public = NotificationPublic(
        id=db_notification.id, 
        user_id=db_notification.user_id, 
        message=db_notification.message,
        type=db_notification.type,  
        status=db_notification.status,                 
        created_at=created_at_str,  # Use converted string
        updated_at=updated_at_str   # Use converted string
    )
        
    # Serialize notification_public to JSON
    # notification_json = {
    #     "id": notification_public.id,
    #     "user_id": notification_public.user_id,
    #     "message": notification_public.message,
    #     "type": notification_public.type,
    #     "status": notification_public.status,
    #     "created_at": str(notification_public.created_at),  # Convert datetime to string
    #     "updated_at": str(notification_public.updated_at)   # Convert datetime to string
    # }
    
    return notification_public



@app.get("/get_all_orders/", response_model=list[NotificationPublic])
def get_all_orders(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        statement = select(Notifications).offset(offset).limit(limit)
        results = session.execute(statement)
        orders = results.scalars().all()
        return orders


@app.get("/get_single_notification/{hero_id}", response_model=NotificationPublic)
def get_single_notification(notification_id: int):
    with Session(engine) as session:
        notification = session.get(Notifications, notification_id)
        if not notification:
            raise HTTPException(status_code=404, detail="notification not found")
        return notification




@app.patch("/update_notification/{notification_id}", response_model=NotificationPublic)
async def update_notification(notification_id: int, notification: NotificationUpdate):

    proto_data = notifi_pb2.Notification_proto()
    proto_data.id = notification_id
    proto_data.user_id=notification.user_id
    proto_data.message=notification.message
    proto_data.type=notification.type
    proto_data.status=notification.status

    time = Timestamp()
    time.GetCurrentTime()
    proto_data.updated_at.CopyFrom(time)

    Serialized_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        # Update the notification in the database
        with Session(engine) as session:
            db_notification = session.get(Notifications, notification_id)
            if not db_notification:
                raise HTTPException(status_code=404, detail="notification not found")
            
            # Update notification fields from notificationUpdate model
            notification_data = notification.model_dump(exclude_unset=True)
            for key, value in notification_data.items():
                setattr(db_notification, key, value)
            session.commit()
            session.refresh(db_notification)

        # Convert datetime fields to strings
        created_at_str = db_notification.created_at.isoformat()
        updated_at_str = db_notification.updated_at.isoformat()

        # Create the public notification object
        notification_public = NotificationPublic(
            id=db_notification.id, 
            user_id=db_notification.user_id, 
            message=db_notification.message,
            type=db_notification.type,  
            status=db_notification.status,                 
            created_at=created_at_str,  # Convert to string
            updated_at=updated_at_str   # Convert to string
        )
        
        # Serialize notification_public to JSON
        # notification_json = {
        #     "id": notification_public.id,
        #     "user_id": notification_public.user_id,
        #     "message": notification_public.message,
        #     "type": notification_public.type,
        #     "status": notification_public.status,
        #     "created_at": str(notification_public.created_at),  # Convert datetime to string
        #     "updated_at": str(notification_public.updated_at)   # Convert datetime to string
        # }

        # Send update message to Kafka
        # notification_Json_msg = json.dumps({"action": "update", "notification": notification_json}).encode("utf-8")
        try:
            await producer.send_and_wait("notification", Serialized_data)
            print(f"Sent update message to Kafka: {Serialized_data}")
            # await producer.send_and_wait("notification", notification_Json_msg)
            # print(f"Sent update message to Kafka: {notification_Json_msg}")
        except Exception as e:
            print(f"Error sending update message to Kafka: {e}")

    return notification_public





@app.delete("/delete_notification/{notification_id}")

async def delete_notification(notification_id: int):

    proto_data = notifi_pb2.Notification_proto(
       id = notification_id
     )
    
    Serialized_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            notification = session.get(Notifications, notification_id)
            if not notification:
                raise HTTPException(status_code=404, detail="notification not found")
            session.delete(notification)
            session.commit()
        
        
        #delete_msg = json.dumps({"action": "delete", "notification_id": notification_id}).encode("utf-8")  

        try:
            await producer.send_and_wait("notification", Serialized_data)
            print(f"Sent delete message to Kafka: {Serialized_data}")
            # await producer.send_and_wait("notification", delete_msg)
            # print(f"Sent delete message to Kafka: {delete_msg}")
        except Exception as e:
            print(f"Delete error: {e}")
            raise HTTPException(status_code=500, detail="Error sending delete message to Kafka")  

    return {"ok": "notification deleted successfully"}
