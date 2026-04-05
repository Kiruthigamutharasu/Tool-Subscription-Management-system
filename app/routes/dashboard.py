from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import User, Subscription
from app.schemas import DashboardStats, SubscriptionOut
from app.utils.dependencies import get_current_user
from datetime import date, timedelta

router = APIRouter()

@router.get("/", response_model=DashboardStats)
def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        user_id = current_user.id
        
        subs = db.query(Subscription).filter(Subscription.user_id == user_id).all()
        
        all_tools_stats = []
        monthly_spending = 0.0
        total_spending = 0.0
        
        for sub in subs:
            cycle = sub.billing_cycle.lower()
            
            if cycle == 'monthly': me = sub.cost
            elif cycle in ('yearly', 'annual'): me = sub.cost / 12
            elif cycle == 'weekly': me = sub.cost * 4.33
            else: me = sub.cost
            
            if cycle in ('yearly', 'annual'): ye = sub.cost
            elif cycle == 'monthly': ye = sub.cost * 12
            elif cycle == 'weekly': ye = sub.cost * 52
            else: ye = sub.cost * 12
            
            me = round(me, 2)
            ye = round(ye, 2)
            monthly_spending += me
            total_spending += ye
            
            all_tools_stats.append({
                "tool_name": sub.tool_name,
                "monthly_equivalent": me,
                "yearly_equivalent": ye
            })
            
        total_spending = round(total_spending, 2)
        monthly_spending = round(monthly_spending, 2)
        
        today = date.today()
        next_week = today + timedelta(days=7)
        upcoming_renewals = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.renewal_date >= today,
            Subscription.renewal_date <= next_week
        ).all()
        
        most_expensive = sorted(subs, key=lambda x: x.cost, reverse=True)[:5]
        
        return DashboardStats(
            total_spending=total_spending,
            monthly_spending=monthly_spending,
            upcoming_renewals=upcoming_renewals,
            most_expensive_tools=most_expensive,
            all_tools_stats=all_tools_stats
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading dashboard: {str(e)}")