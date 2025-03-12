from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
import logging
import httpx

from models import User, get_async_session
from fastapi_users.db import SQLAlchemyUserDatabase
from config import get_settings
from auth.utils import create_auth_cookie_response

settings = get_settings()

# Create router for Vipps authentication
vipps_router = APIRouter(prefix="/auth/vipps", tags=["auth"])

# Constants
AUTH_SOURCE = 'VIPPS'
BASEURL = 'https://apitest.vipps.no/'

# OAuth setup for Vipps Login
oauth = OAuth()
oauth.register(
    name='vipps',
    client_id=settings.VIPPS_CLIENT_ID,
    client_secret=settings.VIPPS_CLIENT_SECRET,
    server_metadata_url='https://apitest.vipps.no/access-management-1.0/access/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email address birthdate name phoneNumber'}
)

# Logger setup
logger = logging.getLogger(__name__)

@vipps_router.get("/login")
async def login_vipps(request: Request):
    """Initiate Vipps authentication flow"""
    redirect_uri = request.url_for('auth_vipps_callback')
    logger.info(f"Vipps redirect URI: {redirect_uri}")
    
    return await oauth.vipps.authorize_redirect(request, redirect_uri)

async def get_userinfo(access_token: str):
    """Get user information from Vipps API using access token"""
    url = f'{BASEURL}/vipps-userinfo-api/userinfo/'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to get Vipps user info: {response.text}")
            return None
            
        user_data = response.json()
        logger.info(f"Got Vipps user data: {user_data}")
        return user_data

@vipps_router.get("/callback", name="auth_vipps_callback")
async def auth_vipps_callback(request: Request):
    """Handle callback from Vipps authentication"""
    try:
        # Get token from Vipps
        token = await oauth.vipps.authorize_access_token(request)
        logger.info("Received token from Vipps")
        
        # Get user info from token and API
        access_token = token.get('access_token')
        if not access_token:
            logger.error("No access token in Vipps response")
            return RedirectResponse(url="/login?error=No+access+token+from+Vipps", status_code=302)
        
        userinfo = await get_userinfo(access_token)
        if not userinfo:
            logger.error("Failed to get user info from Vipps")
            return RedirectResponse(url="/login?error=Failed+to+get+user+info+from+Vipps", status_code=302)
        
        # Extract user information
        email = userinfo.get('email')
        if not email:
            logger.error("No email found in Vipps user data")
            return RedirectResponse(url="/login?error=No+email+provided+by+Vipps", status_code=302)
        
        # Get name from user data - use direct fields from the flattened API response
        # Vipps provides both separate fields and a combined 'name' field
        name = userinfo.get('name')
        
        # If the combined name isn't available, try to construct it from given_name and family_name
        if not name:
            given_name = userinfo.get('given_name', '')
            family_name = userinfo.get('family_name', '')
            name = f"{given_name} {family_name}".strip()
        
        # Check if user exists in database or create new user
        user = None
        async for session in get_async_session():
            user_db = SQLAlchemyUserDatabase(session, User)
            user = await user_db.get_by_email(email)
            
            if not user:
                # Create a new user
                logger.info(f"Creating new user with Vipps authentication: {email}")
                new_user = User(
                    email=email,
                    hashed_password=None,  # OAuth users don't need passwords
                    is_active=True,
                    is_verified=True,
                    is_superuser=False,
                    name=name or None,
                    picture=None  # Vipps doesn't provide a picture
                )
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                user = new_user
            else:
                # Update existing user with latest info
                logger.info(f"Updating existing user: {email}")
                if name:
                    user.name = name
                await session.commit()
                await session.refresh(user)
        
        if user:
            # Create auth cookie and redirect to dashboard
            logger.info(f"Vipps authentication successful for user: {email}")
            return create_auth_cookie_response(user.id)
        else:
            logger.error("Failed to create or retrieve user")
            return RedirectResponse(url="/login?error=User+Creation+Failed", status_code=302)
            
    except Exception as e:
        logger.error(f"Vipps authentication error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return RedirectResponse(url="/login?error=Vipps+Authentication+Failed", status_code=302)