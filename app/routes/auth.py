from fastapi import APIRouter, Request, Depends, HTTPException, status, Header
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.services.auth_service import oauth
from app.database import get_db
from app.models import User

router = APIRouter()

@router.get("/login")
async def login(request: Request):
    try:
        # Enforce exactly this URI for Google Console
        redirect_uri = "http://localhost:8000/auth/callback"
        return await oauth.google.authorize_redirect(request, redirect_uri)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

import requests
from app.config import config

@router.get("/callback")
async def auth_callback(request: Request, code: str, db: Session = Depends(get_db)):
    try:
        # Directly exchange the authorization code for an access token to bypass flaky session-state browser issues
        # Using synchronous `requests` instead of `httpx` to avoid Windows async socket ConnectTimeout bugs
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:8000/auth/callback"
        }
        
        resp = requests.post(token_url, data=data, timeout=15)
        token_data = resp.json()
            
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to fetch token: {token_data}")
            
        # Manually fetch the user profile using the access token
        user_resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo", 
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15
        )
        user_info = user_resp.json()
            
        email = user_info.get("email")
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No email found in user info: {user_info}")
        
        # Verify and initialize the database User
        admin_mail = config.ADMIN_MAIL
        target_role = "admin" if email == admin_mail else "user"
        
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, oauth_provider="google", role=target_role)
            db.add(user)
            db.commit()
            db.refresh(user)
        elif user.role != target_role and email == admin_mail:
            # Upgrade existing user automatically if they are the designated admin
            user.role = "admin"
            db.commit()
        
        # Redirect back to the Streamlit URL with the email directly to log in
        return RedirectResponse(url=f"http://localhost:8501/?user_email={email}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=repr(e))