from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables, engine
from app.model import Product
from app.schema import productResponse, productCreate, productUpdate
 

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== tables creating ===========")
    create_db_and_tables()
    yield
    print("=============== tables created ===========")

app : FastAPI = FastAPI(
    lifespan=lifespan,
    title="product service",
    version="0.0.1",
    # servers=[
    #     {
    #         "url": "http://127.0.0.1:8000",
    #         "description": "product service server"
    #     }
    # ]
)    

@app.get("/")
def start():
    return {"service": "product service"}


# create product

@app.post("/products/", response_model=productResponse)
def create_hero(product: productCreate):
    with Session(engine) as session:
        db_product = Product.model_validate(product)
        session.add(db_product)
        session.commit()
        session.refresh(db_product)
        return db_product

# @app.post("/products/", response_model=productResponse)
# def create_hero(product: productCreate):
#     with Session(engine) as session:
#         db_product = Product.from_orm(product)  # Convert productCreate to Product
#         session.add(db_product)
#         session.commit()
#         session.refresh(db_product)
#         return db_product


# get_all_products

# @app.get("/all_products/", response_model=list[productResponse])
# def read_all_products(offset: int = 0, limit: int = Query(default=100, le=100)):
#     with Session(engine) as session:
#         all_products = session.exec(select(read_all_products).offset(offset).limit(limit)).all()
#         return all_products



@app.get("/all_products/")
def read_all_products(offset: int = 0, limit: int = 100):
    with Session(engine) as session:
        stmt = select(Product).offset(offset).limit(limit)
        all_products = session.exec(stmt).all()
        return all_products




# get_single_product

@app.get("/single_product/{hero_id}", response_model=productResponse)
def single_product(single_product_id: int):
    with Session(engine) as session:
        single_product = session.get(Product, single_product_id)
        if not single_product:
            raise HTTPException(status_code=404, detail="Hero not found")
        return single_product


# update_product

@app.patch("/update_product/{hero_id}", response_model=productResponse)
def update_product(update_product_id: int, update_product: productUpdate):
    with Session(engine) as session:
        db_update_product = session.get(Product, update_product_id)
        if not db_update_product:
            raise HTTPException(status_code=404, detail="Hero not found")
        update_product_data = update_product.model_dump(exclude_unset=True)
        for key, value in update_product_data.items():
            setattr(db_update_product, key, value)
        session.add(db_update_product)
        session.commit()
        session.refresh(db_update_product)
        return db_update_product

# delete_product

@app.delete("/delete_product/{hero_id}")
def delete_product(delete_product_id: int):
    with Session(engine) as session:
        delete_product = session.get(Product, delete_product_id)
        if not delete_product:
            raise HTTPException(status_code=404, detail="product not found")
        session.delete(delete_product)
        session.commit()
        return {"ok": True}