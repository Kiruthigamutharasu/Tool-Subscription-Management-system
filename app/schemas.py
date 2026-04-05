from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any, Dict
from datetime import date

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    role: Optional[str] = "user"

class UserCreate(UserBase):
    oauth_provider: Optional[str] = "google"

class UserResponse(UserBase):
    id: int
    oauth_provider: str
    
    class Config:
        from_attributes = True

# Subscription Schemas
class SubscriptionBase(BaseModel):
    tool_name: str
    cost: float
    billing_cycle: str
    purchase_date: date
    renewal_date: date

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionOut(SubscriptionBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True

# Memory Schemas
class MemoryBase(BaseModel):
    preferences: str
    session_context: str

class MemoryOut(MemoryBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True

# Dashboard Schemas
class ToolStats(BaseModel):
    tool_name: str
    monthly_equivalent: float
    yearly_equivalent: float

class DashboardStats(BaseModel):
    total_spending: float
    monthly_spending: float
    upcoming_renewals: List[SubscriptionOut]
    most_expensive_tools: List[SubscriptionOut]
    all_tools_stats: List[ToolStats] = []
