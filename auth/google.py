from fastapi import APIRouter, Request, Response, Depends, HTTPException
from fastapi.responses import RedirectResponse
import httpx
import logging
from httpx_oauth.clients.google import GoogleOAuth2

from models import User, get_async_session
from fastapi_users.db import SQLAlchemyUserDatabase
from config import get_settings
from auth.utils import create_auth_cookie_response

settings = get_settings()

# Create router for Google authentication
google_router = APIRouter(prefix="/auth/google", tags=["auth"])

# Set up Google OAuth client
google_oauth_client = GoogleOAuth2(
    settings.GOOGLE_CLIENT_ID,
    settings.GOOGLE_CLIENT_SECRET,
)

# Logger setup
logger = logging.getLogger(__name__)

@google_router.get("/login")
async def login_google():
    """Google login redirect"""
    return RedirectResponse(await google_oauth_client.get_authorization_url(
        settings.CALLBACK_URL, 
        scope=["email", "profile"]
    ))

@google_router.get("/callback")
async def auth_google_callback(request: Request, response: Response):
    """Google OAuth callback URL"""
    try:
        logger.info("Google OAuth callback received")
        # Get code from query parameters
        code = request.query_params.get("code")
        
        # Exchange code for token
        token_data = await google_oauth_client.get_access_token(code, settings.CALLBACK_URL)
        access_token = token_data["access_token"]
        
        logger.info(f"Successfully obtained access token")
        
        # Get user data directly from Google's userinfo endpoint
        async with httpx.AsyncClient() as client:
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if userinfo_response.status_code != 200:
                logger.error(f"Failed to get user info: {userinfo_response.text}")
                return RedirectResponse(url="/login?error=Failed+to+get+user+info", status_code=302)
                
            user_data = userinfo_response.json()
            logger.info(f"Got user data: {user_data}")
        
        # Extract user information
        email = user_data.get("email")
        if not email:
            logger.error("No email found in user data")
            return RedirectResponse(url="/login?error=No+email+provided", status_code=302)
            
        name = user_data.get("name")
        picture = user_data.get("picture")
        
        # Check if user exists in database
        user = None
        async for session in get_async_session():
            user_db = SQLAlchemyUserDatabase(session, User)
            user = await user_db.get_by_email(email)
            
            if not user:
                # Create a new user
                logger.info(f"Creating new user with email: {email}")
                new_user = User(
                    email=email,
                    hashed_password=None,  # OAuth users don't need passwords
                    is_active=True,
                    is_verified=True,
                    is_superuser=False,
                    name=name,
                    picture=picture
                )
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                user = new_user
            else:
                # Update existing user with latest info
                logger.info(f"Updating existing user: {email}")
                user.name = name
                user.picture = picture
                await session.commit()
                await session.refresh(user)
        
        if user:
            # Create auth cookie and redirect to dashboard
            logger.info(f"Authentication successful for user: {email}")
            return create_auth_cookie_response(user.id)
        else:
            logger.error("Failed to create or retrieve user")
            return RedirectResponse(url="/login?error=User+Creation+Failed", status_code=302)
            
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return RedirectResponse(url="/login?error=Authentication+Failed", status_code=302)