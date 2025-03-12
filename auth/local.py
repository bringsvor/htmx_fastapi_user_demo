from typing import Optional, Union
from fastapi import APIRouter, Request, Depends, HTTPException, Form, Response, status, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import logging
from pydantic import EmailStr

# Updated password imports
from fastapi_users.password import PasswordHelper
from passlib.context import CryptContext

from models import User, get_async_session
from fastapi_users.db import SQLAlchemyUserDatabase
from auth.utils import create_auth_cookie_response
from config import get_settings
from users import get_user_manager, UserManager
from utils.email import send_verification_email
from datetime import datetime, timedelta
import jwt
from config import get_settings


settings = get_settings()


def generate_verification_token(user_id):
    """Generate a JWT token for email verification"""
    print(f"DEBUG: Generating token for user {user_id}")
    expire = datetime.utcnow() + timedelta(hours=24)
    token_data = {
        "sub": str(user_id),
        "exp": expire,
        "type": "verification"
    }
    token = jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    print(f"DEBUG: Generated token: {token[:20]}...")
    return token

# Create router for local authentication
local_router = APIRouter(prefix="/auth/local", tags=["auth"])

# Logger setup
logger = logging.getLogger(__name__)
email_logger = logging.getLogger("email")

# Create password helper
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
password_helper = PasswordHelper(pwd_context)

# Jinja2 templates
templates = Jinja2Templates(directory="templates")

@local_router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    """Show registration form"""
    return templates.TemplateResponse("register.html", {
        "request": request,
        "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
    })

@local_router.post("/register")
async def register_user(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    password: str = Form(...),
    name: Optional[str] = Form(None),
    user_manager: UserManager = Depends(get_user_manager),
):
    """Register a new local user with email verification"""
    try:
        # Debug information
        print(f"DEBUG: Register called for {email}")
        print(f"DEBUG: Has background_tasks: {background_tasks is not None}")
        print(f"DEBUG: user_manager type: {type(user_manager)}")
        
        # Make sure background_tasks is assigned to user_manager
        user_manager.background_tasks = background_tasks
        print(f"DEBUG: Set background_tasks on user_manager")
        
        # Validate email format
        if "@" not in email:
            return templates.TemplateResponse(
                "register.html", 
                {
                    "request": request, 
                    "error": "Invalid email address",
                    "email": email,
                    "name": name,
                    "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
                }
            )
            
        # Validate password strength
        if len(password) < 8:
            return templates.TemplateResponse(
                "register.html", 
                {
                    "request": request, 
                    "error": "Password must be at least 8 characters long",
                    "email": email,
                    "name": name,
                    "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
                }
            )
        
        # Check if user already exists
        async for session in get_async_session():
            user_db = SQLAlchemyUserDatabase(session, User)
            existing_user = await user_db.get_by_email(email)
            
            if existing_user:
                return templates.TemplateResponse(
                    "register.html", 
                    {
                        "request": request, 
                        "error": "Email already registered",
                        "email": email,
                        "name": name,
                        "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
                    }
                )
            
            # Create new user (not verified yet)
            hashed_password = password_helper.hash(password)
            new_user = User(
                email=email,
                hashed_password=hashed_password,
                is_active=True,
                is_verified=False,  # Not verified until email confirmed
                is_superuser=False,
                name=name,
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            
            logger.info(f"Registered new local user: {email}")
            
            # Generate token directly since on_after_register might not be working
            print(f"DEBUG: Generating verification token directly")
            #token = user_manager.generate_verification_token(new_user)
            

            token_data = {"sub": str(new_user.id), "type": "verification"}
            #token = user_manager.verification_token_generator.generate_token(token_data)
            
            token = generate_verification_token(new_user.id)

            print(f"DEBUG: Generated token: {token[:10]}...")
            
            # Get base URL for the verification link
            origin = request.headers.get("origin", str(request.base_url).rstrip('/'))
            verify_url = f"{origin}/auth/verify?token={token}"
            print(f"DEBUG: Generated verify_url: {verify_url}")
            
            # Send verification email directly instead of using on_after_register
            print(f"DEBUG: Sending verification email directly")
            try:
                await send_verification_email(background_tasks, new_user.email, new_user.name, verify_url)
                print(f"DEBUG: Email sending initiated")
            except Exception as e:
                print(f"DEBUG: Error sending email: {str(e)}")
                import traceback
                print(traceback.format_exc())
            
            # Also try the normal on_after_register flow
            print(f"DEBUG: About to call user_manager.on_after_register")
            try:
                await user_manager.on_after_register(new_user, request)
                print(f"DEBUG: After calling user_manager.on_after_register")
            except Exception as e:
                print(f"DEBUG: Error in on_after_register: {str(e)}")
                import traceback
                print(traceback.format_exc())
            
            # Show verification page
            return templates.TemplateResponse("verify.html", {"request": request})
            
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        print(f"DEBUG: Exception in register_user: {str(e)}")
        print(traceback.format_exc())
        return templates.TemplateResponse(
            "register.html", 
            {
                "request": request, 
                "error": "Registration failed. Please try again.",
                "email": email,
                "name": name,
                "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
            }
        )

@local_router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    """Show login form"""
    return templates.TemplateResponse(
        "local_login.html", 
        {
            "request": request,
            "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
        }
    )

@local_router.post("/login")
async def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Login a local user"""
    try:
        # Find user by email
        async for session in get_async_session():
            user_db = SQLAlchemyUserDatabase(session, User)
            user = await user_db.get_by_email(email)
            
            # Check if user exists and password is correct
            if not user or not user.hashed_password:
                return templates.TemplateResponse(
                    "local_login.html", 
                    {
                        "request": request, 
                        "error": "Invalid email or password",
                        "email": email,
                        "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
                    }
                )
            
            # Use password helper to verify password
            verified, updated_password_hash = password_helper.verify_and_update(
                password, user.hashed_password
            )
            
            if not verified:
                return templates.TemplateResponse(
                    "local_login.html", 
                    {
                        "request": request, 
                        "error": "Invalid email or password",
                        "email": email,
                        "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
                    }
                )
            
            # Update password hash if needed (if password hashing algorithm has been upgraded)
            if updated_password_hash is not None:
                user.hashed_password = updated_password_hash
                await session.commit()
            
            # Check if user is active
            if not user.is_active:
                return templates.TemplateResponse(
                    "local_login.html", 
                    {
                        "request": request, 
                        "error": "Account is inactive",
                        "email": email,
                        "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
                    }
                )

            # Check if user is verified
            if not user.is_verified:
                return templates.TemplateResponse(
                    "verify.html", 
                    {
                        "request": request,
                        "error": "Please verify your email before logging in."
                    }
                )
            
            logger.info(f"Local user login successful: {email}")
            
            # Authenticate the user and redirect to dashboard
            return create_auth_cookie_response(user.id)
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return templates.TemplateResponse(
            "local_login.html", 
            {
                "request": request, 
                "error": "Login failed. Please try again.",
                "email": email,
                "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
            }
        )

@local_router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_form(request: Request):
    """Show forgot password form"""
    return templates.TemplateResponse("reset_password.html", {"request": request})