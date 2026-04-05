import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import SessionLocal
from app.models import Subscription, User
from datetime import date, timedelta
import logging
from app.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SMTP_SERVER = config.SMTP_SERVER
SMTP_PORT = config.SMTP_PORT
SMTP_USERNAME = config.SMTP_USERNAME
SMTP_PASSWORD = config.SMTP_PASSWORD
SENDER_EMAIL = config.SENDER_EMAIL

def build_reminder_html(sub, timeframe="tomorrow"):
    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #4285F4;">Tool Subscription Reminder</h2>
        <p>Hello,</p>
        <p>This is a friendly reminder that your subscription for <strong>{sub.tool_name}</strong> is renewing {timeframe}.</p>
        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 8px; border-left: 5px solid #4285F4; margin: 20px 0;">
            <p style="margin: 5px 0;"><strong>Tool Name:</strong> {sub.tool_name}</p>
            <p style="margin: 5px 0;"><strong>Cost:</strong> ₹{sub.cost:.2f}</p>
            <p style="margin: 5px 0;"><strong>Purchase Date:</strong> {sub.purchase_date}</p>
            <p style="margin: 5px 0;"><strong>Renewal Date:</strong> {sub.renewal_date}</p>
            <p style="margin: 5px 0;"><strong>Billing Cycle:</strong> {sub.billing_cycle}</p>
        </div>
        <p><strong>What to do now?</strong><br>
        If you are still using the tool, ensure your payment method is active. If you no longer need it, please visit the provider's website to cancel before the renewal to avoid charges.</p>
        <br>
        <p>Best regards,<br><em>Your Subscription Dashboard</em></p>
      </body>
    </html>
    """

def send_email(to_email: str, subject: str, html_body: str):
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning(f"SMTP Credentials not mapped. Skipping email to {to_email}. Message: {html_body[:20]}...")
        return

    msg = MIMEMultipart("alternative")
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info(f"Email sent successfully to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")

def check_renewals():
    db = SessionLocal()
    try:
        tomorrow = date.today() + timedelta(days=1)
        next_week = date.today() + timedelta(days=7)
        
        subs_tomorrow = db.query(Subscription).filter(Subscription.renewal_date == tomorrow).all()
        subs_next_week = db.query(Subscription).filter(Subscription.renewal_date == next_week).all()
        
        # Process 1-day reminders
        for sub in subs_tomorrow:
            user = db.query(User).filter(User.id == sub.user_id).first()
            if user:
                subject = f"Reminder: Your {sub.tool_name} subscription renews tomorrow!"
                html_body = build_reminder_html(sub, "tomorrow")
                logger.info(f"Triggering 1-day email to {user.email} for {sub.tool_name}")
                send_email(user.email, subject, html_body)

        # Process 7-day reminders
        for sub in subs_next_week:
            user = db.query(User).filter(User.id == sub.user_id).first()
            if user:
                subject = f"Reminder: Your {sub.tool_name} subscription renews in 7 days!"
                html_body = build_reminder_html(sub, "in 7 days")
                logger.info(f"Triggering 7-day email to {user.email} for {sub.tool_name}")
                send_email(user.email, subject, html_body)
    finally:
        db.close()

scheduler = BackgroundScheduler()

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(check_renewals, 'cron', hour=8, minute=0)
        scheduler.start()
        logger.info("Scheduler started.")