from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    oauth_provider = Column(String, default="google")
    role = Column(String, default="user")  # "user" or "admin"

    subscriptions = relationship("Subscription", back_populates="owner")
    memory = relationship("Memory", back_populates="owner", uselist=False)

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    tool_name = Column(String, index=True, nullable=False)
    cost = Column(Float, nullable=False)
    billing_cycle = Column(String, nullable=False) # "monthly", "yearly"
    purchase_date = Column(Date, nullable=False)
    renewal_date = Column(Date, nullable=False)

    owner = relationship("User", back_populates="subscriptions")

class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    preferences = Column(Text, default="{}") # JSON string
    session_context = Column(Text, default="[]") # JSON string containing chat history

    owner = relationship("User", back_populates="memory")
