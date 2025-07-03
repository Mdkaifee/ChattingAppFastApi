from sqlalchemy.orm import Session
from . import models, schemas

def get_user_by_email(db: Session, email: str):                                         #“Look in the database. If there’s a user with this email, return that user.”
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(
        first_name=user.first_name,
        last_name=user.last_name,                                                       #Creates a new user using the data provided.
        phone_number=user.phone_number,
        email=user.email,
        hashed_password=user.password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

