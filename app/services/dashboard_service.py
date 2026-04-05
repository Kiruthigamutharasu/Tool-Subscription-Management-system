from sqlalchemy.orm import Session
from app.models import Subscription
from datetime import date, timedelta

def get_dashboard(db: Session, user_id: int):
    subs = db.query(Subscription).filter(Subscription.user_id == user_id).all()

    total = sum(s.cost for s in subs)

    monthly = sum(
        s.cost if s.billing_cycle == "monthly" else s.cost / 12
        for s in subs
    )

    upcoming = [
        s for s in subs
        if s.renewal_date <= date.today() + timedelta(days=7)
    ]

    def _monthly_impact(s):
        if s.billing_cycle == "monthly":
            return s.cost
        if s.billing_cycle in ("yearly", "annual"):
            return s.cost / 12
        if s.billing_cycle == "weekly":
            return s.cost * 4.33
        return s.cost

    expensive = sorted(subs, key=_monthly_impact, reverse=True)[:3]

    return {
        "total_spending": total,
        "monthly_spending": monthly,
        "upcoming_renewals": upcoming,
        "most_expensive_tools": expensive
    }