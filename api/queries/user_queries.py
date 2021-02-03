from sqlalchemy.orm import Session
from sqlalchemy.orm.query import Query

from api.db.models import User
from api.routers import schemas

def get_user(db: Session, user: User):
    return db.query(User).filter(User.login == user.login).first()

def create_user(db: Session, user: schemas.User, provider_name: str):
    db_user = User(login=user.login, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def all_users(db: Session):
    return db.query(User).all()

def save_user(db: Session, user: User):
    db.add(user)
    db.commit()
    db.refresh(user)
    return user