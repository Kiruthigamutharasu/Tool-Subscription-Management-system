import logging
from sqlalchemy.orm import Session
from app.models import Subscription
from app.schemas import SubscriptionCreate, SubscriptionBase
from fastapi import HTTPException, status

import threading
from app.services.reminder_service import send_email, build_reminder_html
from app.models import User
from datetime import date, timedelta

def create_subscription(db: Session, subscription: SubscriptionCreate, user_id: int):
    logger = logging.getLogger(__name__)
    logger.info(f"Creating subscription '{subscription.tool_name}' for user {user_id}")
    db_subscription = Subscription(
        user_id=user_id,
        tool_name=subscription.tool_name,
        cost=subscription.cost,
        billing_cycle=subscription.billing_cycle,
        purchase_date=subscription.purchase_date,
        renewal_date=subscription.renewal_date
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    
    # Real-time email trigger for testing/demo scenarios
    today = date.today()
    tomorrow = today + timedelta(days=1)
    if subscription.renewal_date == tomorrow:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            subject = f"Reminder: Your {db_subscription.tool_name} subscription renews tomorrow!"
            html_body = build_reminder_html(db_subscription)
            threading.Thread(target=send_email, args=(user.email, subject, html_body)).start()
            
    return db_subscription

def get_subscriptions(db: Session, user_id: int):
    return db.query(Subscription).filter(Subscription.user_id == user_id).all()

def update_subscription(db: Session, sub_id: int, user_id: int, sub_update: SubscriptionBase):
    logger = logging.getLogger(__name__)
    logger.info(f"Updating subscription {sub_id} for user {user_id}")
    db_sub = db.query(Subscription).filter(Subscription.id == sub_id, Subscription.user_id == user_id).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    for key, value in sub_update.dict().items():
        setattr(db_sub, key, value)
    
    db.commit()
    db.refresh(db_sub)
    return db_sub

def delete_subscription(db: Session, sub_id: int, user_id: int):
    logger = logging.getLogger(__name__)
    logger.info(f"Deleting subscription {sub_id} for user {user_id}")
    db_sub = db.query(Subscription).filter(Subscription.id == sub_id, Subscription.user_id == user_id).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    db.delete(db_sub)
    db.commit()
    return {"detail": "Subscription deleted successfully"}