from typing import Optional, Union, Dict, Any
import uuid
from fastapi import Depends, Request, BackgroundTasks
from fastapi_users import IntegerIDMixin, BaseUserManager
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.models import UP
import logging

from models import User, get_async_session
from config import get_settings
from utils.email import send_verification_email, send_reset_password_email

settings = get_settings()
logger = logging.getLogger(__name__)
email_logger = logging.getLogger("email")

# Configure email functionality
class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    # In your users.py file, add this method to your UserManager class
    async def get(self, id: int):
        """Get a user by ID"""
        async for session in get_async_session():
            return await session.get(User, id)

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        """Called after user registration"""
        logger.info(f"User {user.id} has registered.")
        email_logger.info(f"Processing registration for user {user.id} ({user.email})")
    
        email_logger.debug(f"Has request object: {request is not None}")
        email_logger.debug(f"Has background_tasks attribute: {hasattr(self, 'background_tasks')}")
        email_logger.debug(f"background_tasks is not None: {hasattr(self, 'background_tasks') and self.background_tasks is not None}")
    
        if request and hasattr(self, 'background_tasks') and self.background_tasks:
            email_logger.info(f"Starting verification process for {user.email}")
            # Use our custom token generation from auth/local.py
            from auth.local import generate_verification_token
        
            try:
                # Generate token
                token = generate_verification_token(user.id)
            
                # Get base URL for the verification link
                origin = request.headers.get("origin", str(request.base_url).rstrip('/'))
                verify_url = f"{origin}/auth/verify?token={token}"
            
                # Import send_verification_email
                from utils.email import send_verification_email
            
                # Send the email
                await send_verification_email(self.background_tasks, user.email, user.name, verify_url)
            except Exception as e:
                logger.error(f"Error sending verification email: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.warning(f"Cannot send verification email - missing request or background_tasks")

        async def on_after_forgot_password(
            self, user: User, token: str, request: Optional[Request] = None, background_tasks: Optional[BackgroundTasks] = None
        ):
            """Called after password reset request"""
            logger.info(f"User {user.id} has requested password reset.")
            email_logger.info(f"Processing password reset for user {user.id} ({user.email})")
        
            if request and background_tasks:
                origin = request.headers.get("origin", request.base_url)
                reset_url = f"{origin}/auth/reset-password?token={token}"
                email_logger.info(f"Generated password reset URL: {reset_url}")
            
                # Send reset email
                await send_reset_password_email(background_tasks, user.email, user.name, reset_url)
    
        async def on_after_request_verify(
            self, user: User, token: str, request: Optional[Request] = None, background_tasks: Optional[BackgroundTasks] = None
        ):
            """Called after verification request"""
            logger.info(f"Verification requested for user {user.id}.")
            email_logger.info(f"Processing verification request for user {user.id} ({user.email})")
        
            if request and background_tasks:
                await self.send_verification_email(background_tasks, user, token, request)
    
        async def send_verification_email(self, background_tasks: BackgroundTasks, user: User, token: str, request: Request):
            """Send verification email to user"""
            origin = request.headers.get("origin", request.base_url)
            verify_url = f"{origin}/auth/verify?token={token}"
        
            email_logger.info(f"Sending verification email to {user.email} with URL: {verify_url}")
            await send_verification_email(background_tasks, user.email, user.name, verify_url)
    


    
        def generate_verification_token(self, user: User) -> str:
            """Generate a verification token for the user"""
            token_data = {"sub": str(user.id), "type": "verification"}
            return self.verification_token_generator.generate_token(token_data)

# Update the get_user_manager function in users.py
async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_async_session),
    background_tasks: BackgroundTasks = None,
):
    # Create manager without passing background_tasks to constructor
    manager = UserManager(user_db)
    # Store background_tasks as an attribute that can be accessed later
    manager.background_tasks = background_tasks
    yield manager
    
# Cookie transport for browser authentication
cookie_transport = CookieTransport(
    cookie_name="auth",
    cookie_max_age=3600,
    cookie_secure=False,  # Set to True in production
    cookie_httponly=True,
    cookie_samesite="lax"
)

# Bearer transport for API authentication
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

# Strategy for authentication
def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.SECRET_KEY, 
        lifetime_seconds=3600,
        algorithm=settings.JWT_ALGORITHM
    )

# Authentication backends
cookie_auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

bearer_auth_backend = AuthenticationBackend(
    name="bearer",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)