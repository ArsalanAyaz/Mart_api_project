from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables, engine
from app.model import Inventory
from app.schema import InventoryUpdate, InventoryCreate, InventoryPublic


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=============== creating tables ================")
    create_db_and_tables()
    yield
    print("=============== tables created ================")

app : FastAPI = FastAPI(
    lifespan = lifespan,
    title = "Inventory service",
    version = "0.0.0.1",
    # servers = [
    #     {
    #         "url": "http://127.0.0.1:8005",
    #         "description": "Inventory service Server"
    #     }
    # ]
)    


@app.get('/')
def start():
    return {"service": "Inventory service"}




@app.post("/create_inventory/", response_model=InventoryPublic)
def create_inventory(inventory: InventoryCreate):
    with Session(engine) as session:
        db_inventory = Inventory.model_validate(inventory)
        session.add(db_inventory)
        session.commit()
        session.refresh(db_inventory)
        return db_inventory


@app.get("/get_all_inventories/", response_model=list[InventoryPublic])
def get_all_inventories(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        inventories = session.exec(select(Inventory).offset(offset).limit(limit)).all()
        return inventories


@app.get("/get_single_inventory/{hero_id}", response_model=InventoryPublic)
def get_single_inventory(inventory_id: int):
    with Session(engine) as session:
        inventory = session.get(Inventory, inventory_id)
        if not inventory:
            raise HTTPException(status_code=404, detail="inventory not found")
        return inventory


@app.patch("/update_inventory/{inventory_id}", response_model=InventoryPublic)
def update_inventory(inventory_id: int, inventory: InventoryUpdate):
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
        return db_inventory


@app.delete("/delete_inventory/{hero_id}")
def delete_inventory(inventory_id: int):
    with Session(engine) as session:
        inventory = session.get(Inventory, inventory_id)
        if not inventory:
            raise HTTPException(status_code=404, detail="inventory not found")
        session.delete(inventory)
        session.commit()
        return {"ok": True}