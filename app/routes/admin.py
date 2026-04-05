from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Subscription
from app.schemas import UserResponse, SubscriptionOut
from app.utils.dependencies import get_admin_user

router = APIRouter()

@router.get("/users", response_model=List[UserResponse])
def get_all_users(db: Session = Depends(get_db), admin_user: User = Depends(get_admin_user)):
    return db.query(User).all()

@router.get("/subscriptions", response_model=List[SubscriptionOut])
def get_all_subscriptions(db: Session = Depends(get_db), admin_user: User = Depends(get_admin_user)):
    return db.query(Subscription).all()

from app.services.reminder_service import check_renewals
from fastapi import HTTPException

@router.post("/trigger-reminders")
def trigger_reminders(admin_user: User = Depends(get_admin_user)):
    try:
        check_renewals()
        return {"message": "Reminders triggered successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 