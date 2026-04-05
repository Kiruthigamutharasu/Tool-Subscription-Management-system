from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User
from app.schemas import SubscriptionCreate, SubscriptionOut, SubscriptionBase
from app.utils.dependencies import get_current_user
from app.services import subscription_service

router = APIRouter()

@router.post("/", response_model=SubscriptionOut)
def create_subscription(
    subscription: SubscriptionCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    try:
        return subscription_service.create_subscription(db, subscription, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating subscription: {str(e)}")

@router.get("/", response_model=List[SubscriptionOut])
def get_subscriptions(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    try:
        return subscription_service.get_subscriptions(db, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching subscriptions: {str(e)}")

@router.put("/{sub_id}", response_model=SubscriptionOut)
def update_subscription(
    sub_id: int, 
    sub_update: SubscriptionBase, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    try:
        return subscription_service.update_subscription(db, sub_id, current_user.id, sub_update)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating subscription: {str(e)}")

@router.delete("/{sub_id}")
def delete_subscription(
    sub_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    try:
        return subscription_service.delete_subscription(db, sub_id, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting subscription: {str(e)}")