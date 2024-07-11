

from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables
from app.model import Product
from app.schema import ProductCreate, ProductPublic, ProductUpdate
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import asyncio
from app import product_pb2
from app.db import engine



# =========== Function for inventory topic consumer

async def start_consumer(topic, broker):
    kafka_consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=broker,
        group_id="inventory_product_Consumer"  # inventory_ser is producer and product_ser is consumer
    )

    await kafka_consumer.start()
    try:
        async for msg in kafka_consumer:
            print(f"Serialized message in consumer: {msg.value}")
            deserialized_product_data = product_pb2.Product_proto()
            deserialized_product_data.ParseFromString(msg.value)
            print(f"Deserialized message in consumer: {msg.value}")
    except Exception as e:
        print(f"Consumer error: {e}")
    finally:
        await kafka_consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== Tables creating & event firing ============")
    create_db_and_tables()
    consumer_task = asyncio.create_task(start_consumer("inventory", "broker:19092"))  # consumer of inventory-topic
    yield
    print("=============== Tables created & event fired ============")


app = FastAPI(lifespan=lifespan, title= "product service")

@app.get("/")
def start():
    return {"service": "product service"}

@app.post("/create_product", response_model=ProductPublic)
async def create_product(product: ProductCreate):
    proto_data = product_pb2.Product_proto(
        name=product.name,
        description=product.description,
        price=product.price,
    )
    serialized_product_data = proto_data.SerializeToString()

    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        with Session(engine) as session:
            db_product = Product.model_validate(product)
            session.add(db_product)
            session.commit()
            session.refresh(db_product)

        await producer.send_and_wait("product", serialized_product_data)
    except Exception as e:
        session.rollback()
        print(f"Producer error: {e}")
        raise HTTPException(status_code=500, detail="Error creating product")
    finally:
        await producer.stop()

    product_public = ProductPublic(
        id=db_product.id,
        name=db_product.name,
        description=db_product.description,
        price=db_product.price
    )
    return product_public

@app.get("/get_all_products/", response_model=list[ProductPublic])
def get_all_products(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        products = session.exec(select(Product).offset(offset).limit(limit)).all()
        return products

@app.get("/get_single_product/{product_id}", response_model=ProductPublic)
def get_single_product(product_id: int):
    with Session(engine) as session:
        product = session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

@app.patch("/update_product/{product_id}", response_model=ProductPublic)
async def update_product(product_id: int, product: ProductUpdate):
    proto_data = product_pb2.Product_proto(
        id=product_id,
        name=product.name,
        description=product.description,
        price=product.price,
    )
    serialized_product_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            db_product = session.get(Product, product_id)
            if not db_product:
                raise HTTPException(status_code=404, detail="Product not found")
            product_data = product.model_dump(exclude_unset=True)
            for key, value in product_data.items():
                setattr(db_product, key, value)
            session.add(db_product)
            session.commit()
            session.refresh(db_product)

            product_public = ProductPublic(
                id=db_product.id,
                name=db_product.name,
                description=db_product.description,
                price=db_product.price
            )
            
            try:
                await producer.send_and_wait("product", serialized_product_data)
            except Exception as e:
                print(f"Error sending update message to Kafka: {e}")
    
    return product_public

@app.delete("/delete_product/{product_id}")
async def delete_product(product_id: int):
    proto_data = product_pb2.Product_proto(
        id=product_id,
    )
    serialized_product_data = proto_data.SerializeToString()

    async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
        with Session(engine) as session:
            product = session.get(Product, product_id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            session.delete(product)
            session.commit()

            try:
                await producer.send_and_wait("product", serialized_product_data)
            except Exception as e:
                print(f"Error sending delete message to Kafka: {e}")

    return {"ok": True}














# from fastapi import FastAPI, HTTPException, Query
# from sqlmodel import Session, select
# from contextlib import asynccontextmanager
# from app.db import create_db_and_tables
# from typing import Optional
# from app.db import engine
# from app.model import Product
# from app.schema import productCreate, productPublic, productUpdate
# from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
# import json
# import asyncio
# from app import product_pb2

# # =========== Function for inventory topic consumer

# async def start_consumer(topic, broker):
#     kafka_consumer = AIOKafkaConsumer(
#         topic,
#         bootstrap_servers=broker,
#         group_id="inventory_product_Consumer"  # inventory_ser is producer and product_ser is consumer
#     )

#     await kafka_consumer.start()
#     try:
#         async for msg in kafka_consumer:
#             print(f"Serialized message in consumer: {msg.value}")
#             deserialized_product_data = product_pb2.Product_proto()
#             deserialized_product_data.ParseFromString(msg.value)
#             print(f"Deserialized message in consumer: {msg.value}")
#     except Exception as e:
#         print(f"Consumer error: {e}")
#     finally:
#         await kafka_consumer.stop()

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     print("=============== Tables creating & event firing ============")
#     create_db_and_tables()
#     consumer_task = asyncio.create_task(start_consumer("inventory", "broker:19092"))  # consumer of inventory-topic
#     yield
#     print("=============== Tables created & event fired ============")

# app = FastAPI(lifespan=lifespan)

# @app.get("/")
# def start():
#     return {"service": "product service"}

# @app.post("/create_product", response_model=productPublic)
# async def create_product(product: productCreate):
#     proto_data = product_pb2.Product_proto(
#         name=product.name,
#         description=product.description,
#         price=product.price,
#     )
#     serialized_product_data = proto_data.SerializeToString()

#     producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
#     await producer.start()
#     try:
#         with Session(engine) as session:  # Save to database within a transaction
#             session.begin()
#             db_product = Product.model_validate(product)
#             session.add(db_product)
#             session.commit()
#             session.refresh(db_product)

#         await producer.send_and_wait("product", serialized_product_data)
#     except Exception as e:
#         session.rollback()
#         print(f"Producer error: {e}")
#         raise HTTPException(status_code=500, detail="Error creating product")
#     finally:
#         await producer.stop()

#     product_public = productPublic(
#         id=db_product.id,
#         name=db_product.name,
#         description=db_product.description,
#         price=db_product.price
#     )
#     return product_public

# @app.get("/get_all_products/", response_model=list[productPublic])
# def get_all_products(offset: int = 0, limit: int = Query(default=100, le=100)):
#     with Session(engine) as session:
#         products = session.exec(select(Product).offset(offset).limit(limit)).all()
#         return products

# @app.get("/get_single_product/{product_id}", response_model=productPublic)
# def get_single_product(product_id: int):
#     with Session(engine) as session:
#         product = session.get(Product, product_id)
#         if not product:
#             raise HTTPException(status_code=404, detail="Product not found")
#         return product

# @app.patch("/update_product/{product_id}", response_model=productPublic)
# async def update_product(product_id: int, product: productUpdate):
#     proto_data = product_pb2.Product_proto(
#         id=product_id,
#         name=product.name,
#         description=product.description,
#         price=product.price,
#     )
#     serialized_product_data = proto_data.SerializeToString()

#     async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
#         with Session(engine) as session:
#             db_product = session.get(Product, product_id)
#             if not db_product:
#                 raise HTTPException(status_code=404, detail="Product not found")
#             product_data = product.model_dump(exclude_unset=True)
#             for key, value in product_data.items():
#                 setattr(db_product, key, value)
#             session.add(db_product)
#             session.commit()
#             session.refresh(db_product)
        
#             product_public = productPublic(
#                 id=db_product.id,
#                 name=db_product.name,
#                 description=db_product.description,
#                 price=db_product.price
#             )
            
#             try:
#                 await producer.send_and_wait("product", serialized_product_data)
#                 print(f"Sent update message to Kafka: {serialized_product_data}")
#             except Exception as e:
#                 print(f"Error sending update message to Kafka: {e}")
    
#     return product_public

# @app.delete("/delete_product/{product_id}")
# async def delete_product(product_id: int):
#     proto_data = product_pb2.Product_proto(
#         id=product_id,
#     )
#     serialized_product_data = proto_data.SerializeToString()

#     async with AIOKafkaProducer(bootstrap_servers='broker:19092') as producer:
#         with Session(engine) as session:
#             product = session.get(Product, product_id)
#             if not product:
#                 raise HTTPException(status_code=404, detail="Product not found")
#             session.delete(product)
#             session.commit()
        
#             try:
#                 await producer.send_and_wait("product", serialized_product_data)
#                 print(f"Sent delete message to Kafka: {serialized_product_data}")
#             except Exception as e:
#                 print(f"Error sending delete message to Kafka: {e}")

#     return {"ok": True}
















