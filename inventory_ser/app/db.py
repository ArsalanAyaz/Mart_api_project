from app import setting
from sqlmodel import SQLModel, Session, create_engine


connection_string = str(setting.DATABASE_URL).replace("postgresql", "postgresql+psycopg")

engine = create_engine(connection_string, connect_args={}, pool_recycle=300)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session    




