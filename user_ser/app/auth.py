from passlib.context import CryptContext
from typing import Annotated
from sqlmodel import Session, select
from fastapi import Depends
from app.db import get_session
from app.model import Users



pwd_context = CryptContext(schemes='bcrypt')


def hash_password(password):
    return pwd_context.hash(password)


def get_user_from_db(session: Annotated[Session, Depends(get_session)], 
                     name:str, 
                     email:str):
    
    statement = select(Users).where(Users.name == name)
    user = session.exec(statement).first()
    if not user:
        statement = select(Users).where(Users.email == email)
        user = session.exec(statement).first()
        if user:
            return user
        
    return user    