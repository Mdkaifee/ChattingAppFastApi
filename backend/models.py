import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, Table            #help to interact with relational database                       # assuming correct import path
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):                                         #a table for users in the database
    __tablename__ = "users"                               #Set the table name

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)      #define fields in table
    last_name = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=False)     
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    profile_photo = relationship("UserPhoto", uselist=False, back_populates="user")
    groups = relationship("Group", secondary="group_members", back_populates="members")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String(1000))
    timestamp = Column(DateTime, default=datetime.utcnow)

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])

group_members = Table(
    'group_members', Base.metadata,
    Column('group_id', ForeignKey('groups.id'), primary_key=True),
    Column('user_id', ForeignKey('users.id'), primary_key=True)
)

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    profile_photo = relationship("GroupPhoto", uselist=False, back_populates="group")
    members = relationship("User", secondary=group_members, back_populates="groups")

class GroupMessage(Base):
    __tablename__ = "group_messages"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"))
    sender_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String(1000))
    timestamp = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", backref="messages")
    sender = relationship("User")


class UserPhoto(Base):
    __tablename__ = "user_photos"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    photo = Column(LargeBinary, nullable=False)
    mime_type = Column(String(100), nullable=False)

    user = relationship("User", back_populates="profile_photo")


class GroupPhoto(Base):
    __tablename__ = "group_photos"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), unique=True)
    photo = Column(LargeBinary, nullable=False)
    mime_type = Column(String(100), nullable=False)

    group = relationship("Group", back_populates="profile_photo")

