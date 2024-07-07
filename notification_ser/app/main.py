from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from app.db import create_db_and_tables
from app.db import engine
from app.model import Notifications
from app.schema import NotificationUpdate, NotificationCreate, NotificationPublic


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=========== creating tables==========")
    create_db_and_tables()
    yield
    print("=========== tables created ==========")


app : FastAPI = FastAPI(

    lifespan=lifespan,
    title="Notification service",
    version="0.0.1",
    # servers=[
    #     {
    #         "url": "http://127.0.0.1:8004",
    #         "description":"Notification service server"
    #     }
    # ]
)    


@app.get("/")
def start():
    return {"service": "Notification service"}



@app.post("/create_notification/", response_model=NotificationPublic)
def create_notification(notification: NotificationCreate):
    with Session(engine) as session:
        db_notification = Notifications.model_validate(notification)
        session.add(db_notification)
        session.commit()
        session.refresh(db_notification)
        return db_notification


@app.get("/get_all_notifications/", response_model=list[NotificationPublic])
def get_all_notifications(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        notifications = session.exec(select(Notifications).offset(offset).limit(limit)).all()
        return notifications


@app.get("/get_single_notification/{notification_id}", response_model=NotificationPublic)
def get_single_notification(notification_id: int):
    with Session(engine) as session:
        notification = session.get(Notifications, notification_id)
        if not notification:
            raise HTTPException(status_code=404, detail="notification not found")
        return notification


@app.patch("/update_notification/{notification_id}", response_model=NotificationPublic)
def update_notification(notification_id: int, notification: NotificationUpdate):
    with Session(engine) as session:
        db_notification = session.get(Notifications, notification_id)
        if not db_notification:
            raise HTTPException(status_code=404, detail="notification not found")
        notification_data = notification.model_dump(exclude_unset=True)
        for key, value in notification_data.items():
            setattr(db_notification, key, value)
        session.add(db_notification)
        session.commit()
        session.refresh(db_notification)
        return db_notification


@app.delete("/delete_notification/{hero_id}")
def delete_notification(notification_id: int):
    with Session(engine) as session:
        notification = session.get(Notifications, notification_id)
        if not notification:
            raise HTTPException(status_code=404, detail="notification not found")
        session.delete(notification)
        session.commit()
        return {"ok": True}