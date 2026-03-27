from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    uid = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    displayName = Column(String)
    role = Column(String, default="student")
    photoURL = Column(String)
    createdAt = Column(DateTime(timezone=True), server_default=func.now())
    lastLogin = Column(DateTime(timezone=True), onupdate=func.now())
