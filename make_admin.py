import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.database import SessionLocal
from app.models import User

def set_admin(email: str):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.role = "admin"
        db.commit()
        print(f"User {email} successfully promoted to admin!")
    else:
        print(f"User {email} not found. Please login via the app first to create the account, then run this script.")
    db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py <your_email>")
    else:
        set_admin(sys.argv[1])
