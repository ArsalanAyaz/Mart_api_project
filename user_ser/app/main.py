from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables, engine
from app.model import Users
from app.schema import UserCreate, UserPublic, UserUpdate
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json
import asyncio
from app import user_pb2


async def start_consumer(topic, broker):
    kafka_consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=broker,
        group_id="user_Cons1"
    )

    await kafka_consumer.start()
    try:
        async for msg in kafka_consumer:
            print(f"Serialized data in consumer....:{msg.value}")
            deserialized_user_data = user_pb2.Users_proto()
            deserialized_user_data.ParseFromString(msg.value)
            print(f"Deserialized data in consumer ....", deserialized_user_data)

    except Exception as e:
        print(f"Consumer error: {e}")
    finally:
        await kafka_consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== Tables creating & event fire ============")
    create_db_and_tables()
    consumer_task = asyncio.create_task(start_consumer("user", "broker:19092"))
    yield
    print("=============== Tables created & event fired ============")


app = FastAPI(lifespan=lifespan)


@app.get("/")
def start():
    return {"service": "user service"}


@app.post("/create_user", response_model=UserPublic)
async def create_user(user: UserCreate):
    proto_user = user_pb2.Users_proto(name=user.name, password=user.password, email=user.email, phone=user.phone)
    serialized_user_data = proto_user.SerializeToString()

    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')

    await producer.start()
    try:
        await producer.send_and_wait("user", serialized_user_data)
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


@app.get("/get_all_users/", response_model=list[UserPublic])
def get_all_users(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        users = session.exec(select(Users).offset(offset).limit(limit)).all()
        return users


@app.get("/get_single_user/{user_id}", response_model=UserPublic)
def get_single_user(user_id: int):
    with Session(engine) as session:
        user = session.get(Users, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="user not found")
        return user


@app.patch("/update_user/{user_id}", response_model=UserPublic)
async def update_user(user_id: int, user: UserUpdate):
    proto_user = user_pb2.Users_proto(
        id=user_id,
        name=user.name or "",
        password=user.password or "",
        email=user.email or "",
        phone=user.phone or ""
    )

    serialized_user_data = proto_user.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        # Update the user in the database
        with Session(engine) as session:
            db_user = session.get(Users, user_id)
            if not db_user:
                raise HTTPException(status_code=404, detail="User not found")
            user_data = user.model_dump(exclude_unset=True)
            for key, value in user_data.items():
                setattr(db_user, key, value)
            session.add(db_user)
            session.commit()
            session.refresh(db_user)

            user_public = UserPublic(
                id=db_user.id,
                name=db_user.name,
                password=db_user.password,
                email=db_user.email,
                phone=db_user.phone
            )

        # Send update message to Kafka
        try:
            await producer.send_and_wait("user", serialized_user_data)
        except Exception as e:
            print(f"Error sending update message to Kafka: {e}")

    return user_public


@app.delete("/delete_user/{user_id}")
async def delete_user(user_id: int):
    proto_data = user_pb2.Users_proto(
        id=user_id
    )
    serialized_user_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            user = session.get(Users, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="user not found")
            session.delete(user)
            session.commit()

            # Send delete message to Kafka
            try:
                await producer.send_and_wait("user", serialized_user_data)
            except Exception as e:
                print(f"Error sending delete message to Kafka: {e}")

    return {"ok": True}
