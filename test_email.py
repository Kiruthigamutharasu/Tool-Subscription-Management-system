import sys
import os
from dotenv import load_dotenv

load_dotenv()

from app.services.reminder_service import send_email

def test():
    test_email = os.getenv("ADMIN_MAIL", os.getenv("SENDER_EMAIL"))
    print(f"Attempting to send a test email to: {test_email} using {os.getenv('SMTP_USERNAME')}...")
    
    try:
        send_email(test_email, "Test Email from Support", "If you receive this, SMTP is working perfectly!")
        print("send_email function finished execution.")
    except Exception as e:
        print(f"Error caught in test script: {e}")

if __name__ == "__main__":
    test()
