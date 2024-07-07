from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables
from typing import Optional
from app.db import engine
from app.model import Users
from app.schema import UserCreate, UserPublic, UserUpdate
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json
import asyncio




async def consumer(topic, broker):
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=broker,
        group_id="my-group"
    )

    await consumer.start()
    try:
        async for msg in consumer:
            print("Consumed message: ", msg.topic, msg.partition, msg.offset, msg.key, msg.value.decode("utf-8"), msg.timestamp)
    except Exception as e:
        print(f"consumer error : {e} ")
    
    finally:
        await consumer.stop()

    return {"data": consumer}    



@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== tables creating & event fire ===========")
    create_db_and_tables()
    task = asyncio.create_task(consumer("order","broker:19092"))
    yield
    task.cancel()
    await task
    print("=============== tables created ===========")

app : FastAPI = FastAPI(
    lifespan=lifespan,
    title="user service",
    version="0.0.1",
    # servers=[
    #     {
    #         "url": "http://127.0.0.1:8001",
    #         "description": "user service server"
    #     }
    # ]
)    

@app.get("/")
def start():
    return {"service": "user service"}




# ==================== kafka ========================


# producer

# @app.post("/create_user", response_model=UserPublic)
# # @app.post("/create_user")
# async def create_user(user: UserCreate):

#     producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
#     userJson = json.dumps(user.__dict__).encode("utf-8")
    
#     await producer.start()
#     try:
#         await producer.send_and_wait("order", userJson)
#     finally:
#         await producer.stop()

#     with Session(engine) as session: # save to database
#         db_user = Users.model_validate(user)
#         session.add(db_user)
#         session.commit()
#         session.refresh(db_user)

#     user_public = UserPublic(id=db_user.id, name=db_user.name, password=db_user.password, email=db_user.email, phone=db_user.phone)
#     # return userJson
#     return user_public

@app.post("/create_user", response_model=UserPublic)
async def create_user(user: UserCreate):
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    userJson = json.dumps(user.__dict__).encode("utf-8")
    
    print(f"Sending message to Kafka: {userJson}")
    
    await producer.start()
    try:
        await producer.send_and_wait("order", userJson)
    except Exception as e:
        print(f"producer error : {e}")    
    finally:
        await producer.stop()

    with Session(engine) as session:  # Save to database
        db_user = Users.model_validate(user)
        session.add(db_user)
        session.commit()
        session.refresh(db_user)

    user_public = UserPublic(id=db_user.id, name=db_user.name, password=db_user.password, email=db_user.email, phone=db_user.phone)
    return user_public





# consumer
# @app.get("/consumer")
# async def consumer():
#     consumer = AIOKafkaConsumer( 

#         'order', 
#         bootstrap_servers='broker:19092', 
#         group_id="my-group"
        
#         )
    
#     await consumer.start()
#     try:
#         # Consume messages
#         async for msg in consumer:
#             print("consumed: ", msg.topic, msg.partition, msg.offset,
#                   msg.key, msg.value, msg.timestamp)
#     finally:
#         # Will leave consumer group; perform autocommit if enabled.
#         await consumer.stop()

#     return {"data": consumer}



# ============================================================




# @app.post("/create_user/", response_model=UserPublic)
# def create_user(user: UserCreate):
#     with Session(engine) as session:
#         db_user = Users.model_validate(user)
#         session.add(db_user)
#         session.commit()
#         session.refresh(db_user)
#         return db_user


@app.get("/get_all_users/", response_model=list[UserPublic])
def get_all_users(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        users = session.exec(select(Users).offset(offset).limit(limit)).all()
        return users


@app.get("/get_single_user/{hero_id}", response_model=UserPublic)
def get_single_user(user_id: int):
    with Session(engine) as session:
        user = session.get(Users, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="user not found")
        return user


@app.patch("/update_user/{hero_id}", response_model=UserPublic)
def update_user(user_id: int, user: UserUpdate):
    with Session(engine) as session:
        db_user = session.get(Users, user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="user not found")
        user_data = user.model_dump(exclude_unset=True)
        for key, value in user_data.items():
            setattr(db_user, key, value)
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return db_user


@app.delete("/delete_user/{hero_id}")
def delete_user(user_id: int):
    with Session(engine) as session:
        user = session.get(Users, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="user not found")
        session.delete(user)
        session.commit()
        return {"ok": True}