#!/usr/bin/env python3

from typing import List, Optional
from fastapi import FastAPI, Form, Request, Depends, Response, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi import BackgroundTasks

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
import logging
import jwt
from fastapi_users.db import SQLAlchemyUserDatabase

from models import Base, User, get_async_session
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import CookieTransport, AuthenticationBackend, JWTStrategy
from config import get_settings
from starlette.middleware.sessions import SessionMiddleware

# Update fastapi-users routes to include verification
from schemas import UserRead, UserCreate, UserUpdate

from users import cookie_auth_backend, bearer_auth_backend, get_user_manager, UserManager

# Import from auth module
from auth import google_router, vipps_router, local_router

settings = get_settings()

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.SECRET_KEY, 
        lifetime_seconds=3600,
        algorithm=settings.JWT_ALGORITHM
    )

optional_user = None

def create_app(init_db=True):
    """
    Create and configure the FastAPI application
    
    Parameters:
    - init_db: Whether to initialize the database on startup
    
    Returns:
    - Configured FastAPI app
    """
    
    # Startup Event - Create Database Tables if needed
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if init_db:
            engine = create_async_engine(settings.DATABASE_URL)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        yield

    app = FastAPI(lifespan=lifespan if init_db else None)
    
    # Add SessionMiddleware for OAuth flows
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        max_age=3600,  # 1 hour in seconds
    )
    
    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Jinja2 templates
    templates = Jinja2Templates(directory="templates")
    
    # Authentication backend setup
    cookie_transport = CookieTransport(
        cookie_name="auth",
        cookie_max_age=3600,
        cookie_secure=False,  # Set to True in production
        cookie_httponly=True,
        cookie_samesite="lax"
    )
    
    # FastAPI Users setup
    fastapi_users = FastAPIUsers[User, int](
        get_user_manager,
        [cookie_auth_backend],
    )
    
    current_active_user = fastapi_users.current_user(active=True)
    global optional_user
    optional_user = fastapi_users.current_user(optional=True)
    
    # Set up routes
    setup_auth_routes(app, fastapi_users)
    setup_frontend_routes(app, templates, optional_user, current_active_user)
    app.state.templates = templates
    
    return app

def setup_auth_routes(app: FastAPI, fastapi_users):
    """Configure all authentication-related routes"""
    
    # Include FastAPI Users routes for core functionality
    app.include_router(
        fastapi_users.get_auth_router(cookie_auth_backend),
        prefix="/auth/jwt",
        tags=["auth"],
    )

    app.include_router(
        fastapi_users.get_auth_router(bearer_auth_backend),
        prefix="/auth/bearer",
        tags=["auth"],
    )

    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
    )

    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/auth",
        tags=["auth"],
    )

    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/auth",
        tags=["auth"],
    )

    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )

    # Include modular auth routes
    app.include_router(google_router)
    app.include_router(vipps_router)
    app.include_router(local_router)
    
    # Set up custom auth routes
    @app.get("/auth/request-verify-token", response_class=HTMLResponse)
    async def request_verify_token_form(request: Request):
        """Show request verification token form"""        
        return templates.TemplateResponse(request, "request_verify.html")


    @app.post("/auth/request-verify-token")
    async def request_verify_token(
        request: Request,
        background_tasks: BackgroundTasks,
        email: str = Form(...),  # Using Form to handle form data
        user_manager: UserManager = Depends(get_user_manager),
    ):
        """Request a new verification token"""
        try:
            logging.info(f"Verification token requested for email: {email}")
            
            # Find user by email
            async for session in get_async_session():
                user_db = SQLAlchemyUserDatabase(session, User)
                user = await user_db.get_by_email(email)
                
                if user:
                    # Send verification email
                    if not user.is_verified:
                        logging.info(f"Sending verification email for user {user.id}")
                        await user_manager.request_verify(user, request, background_tasks)
                        logging.info(f"Verification email sent for user {user.id}")
                    else:
                        logging.info(f"User {user.id} is already verified")
                    
                    return templates.TemplateResponse(
                        request,
                        "verify.html", 
                        {"message": "If your email is registered, a verification link has been sent."}
                    )
                else:
                    # Don't reveal if email is registered for security
                    logging.info(f"Verification requested for non-existent email: {email}")
                    return templates.TemplateResponse(
                        request,
                        "verify.html", 
                        {"message": "If your email is registered, a verification link has been sent."}
                    )
        except Exception as e:
            logging.error(f"Request verification error: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return templates.TemplateResponse(
                request,
                "verify.html", 
                {"error": "Failed to send verification email"}
            )

    @app.get("/auth/forgot-password", response_class=HTMLResponse)
    async def forgot_password_form(request: Request):
        """Show forgot password form"""
        return templates.TemplateResponse(request, "reset_password.html")

    @app.post("/auth/forgot-password")
    async def forgot_password(
        request: Request,
        background_tasks: BackgroundTasks,
        email: str = Form(...),  # Using Form to handle form data
        user_manager: UserManager = Depends(get_user_manager),
    ):
        """Request password reset"""
        try:
            logging.info(f"Password reset requested for email: {email}")
            
            # Find user by email
            async for session in get_async_session():
                user_db = SQLAlchemyUserDatabase(session, User)
                user = await user_db.get_by_email(email)
                
                if user:
                    # Send password reset email
                    logging.info(f"Sending password reset email for user {user.id}")
                    await user_manager.forgot_password(user, request, background_tasks)
                    logging.info(f"Password reset email sent for user {user.id}")
                else:
                    logging.info(f"Password reset requested for non-existent email: {email}")
                
                # Don't reveal if email is registered for security
                return templates.TemplateResponse(
                    request,
                    "reset_password.html", 
                    {"success": "If your email is registered, a password reset link has been sent."}
                )
        except Exception as e:
            logging.error(f"Forgot password error: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return templates.TemplateResponse(
                request,
                "reset_password.html", 
                {"error": "Failed to send password reset email"}
            )
        
    @app.get("/auth/reset-password")
    async def reset_password_form(request: Request, token: str):
        """Show reset password form with token"""
        return templates.TemplateResponse(request, "reset_password_form.html", { "token": token})

    @app.post("/auth/reset-password")
    async def reset_password(
        request: Request,
        token: str = Form(...),
        password: str = Form(...),
        user_manager: UserManager = Depends(get_user_manager),
    ):
        """Reset password with token"""
        try:
            # Validate password strength
            if len(password) < 8:
                return templates.TemplateResponse(
                    request,
                    "reset_password_form.html", 
                    {                        
                        "error": "Password must be at least 8 characters long",
                        "token": token
                    }
                )
                
            # Reset password using fastapi-users
            await user_manager.reset_password(token, password)
            
            return templates.TemplateResponse(
                request,
                "reset_password_success.html", 
                {"success": "Your password has been reset successfully."}
            )
        except Exception as e:
            logger.error(f"Reset password error: {str(e)}")
            return templates.TemplateResponse(
                request,
                "reset_password_form.html", 
                {"error": "Failed to reset password. The token may be invalid or expired.", "token": token}
            )

    @app.get("/auth/verify")
    async def verify_email(request: Request, token: str):
        """Handle email verification with token"""
        try:
            logger.info(f"Verifying token: {token[:20]}...")
            
            try:
                # Decode the token
                payload = jwt.decode(
                    token, 
                    settings.SECRET_KEY, 
                    algorithms=[settings.JWT_ALGORITHM],
                )
                logger.info(f"Decoded token payload: {payload}")
                
                # Verify token type
                if payload.get("type") != "verification":
                    logger.warning(f"Invalid token type: {payload.get('type')}")
                    return templates.TemplateResponse(
                        request,
                        "verify.html", 
                        {"error": "Invalid verification token"}
                    )
                
                # Get user ID from token
                user_id = payload.get("sub")
                if not user_id:
                    logger.warning(f"No user ID in token")
                    return templates.TemplateResponse(
                        request,
                        "verify.html", 
                        {"error": "Invalid verification token"}
                    )
                
                # Find and verify the user
                async for session in get_async_session():
                    # Find the user. Token contains string ID, so convert to int
                    int_id = int(user_id)
                    user = await session.get(User, int_id)
                    
                    if not user:
                        logger.warning(f"User not found for ID {user_id}")
                        return templates.TemplateResponse(
                            request,
                            "verify.html", 
                            { "error": "User not found"}
                        )
                    
                    # Mark user as verified
                    user.is_verified = True
                    await session.commit()
                    logger.info(f"User {user.email} verified successfully")
                    
                    return templates.TemplateResponse(
                        request,
                        "verify.html", 
                        {"success": True}
                    )
                    
            except jwt.PyJWTError as e:
                logger.error(f"JWT error: {str(e)}")
                return templates.TemplateResponse(
                    request,
                    "verify.html", 
                    {"error": "Invalid verification token"}
                )
                
        except Exception as e:
            logger.error(f"Verification error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return templates.TemplateResponse(
                request,
                "verify.html", 
                {"error": "Verification failed"}
            )

    @app.get("/auth/OLDverify")
    async def old_verify_email(request: Request, token: str):
        """Handle email verification with token"""
        try:
            # Verify token using fastapi-users
            user = await fastapi_users.verify.verify_user(token)
            if user:
                return templates.TemplateResponse(request, "verify.html", {"success": True})
            else:
                return templates.TemplateResponse(request, "verify.html", {"error": "Invalid verification token"})
        except Exception as e:
            logger.error(f"Verification error: {str(e)}")
            return templates.TemplateResponse(request, "verify.html", {"request": request, "error": "Verification failed"})

def setup_frontend_routes(app: FastAPI, templates, optional_user, current_active_user):
    """Configure all frontend routes"""
    
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        return templates.TemplateResponse(request, "home.html", {"request": request})

    @app.get("/login", response_class=HTMLResponse)
    async def login(request: Request):
        return templates.TemplateResponse(request, "login.html", {
            "request": request,
            "vipps_enabled": bool(settings.VIPPS_CLIENT_ID and settings.VIPPS_CLIENT_SECRET)
        })

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(
        request: Request,
        user: Optional[User] = Depends(optional_user)
    ):
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        return templates.TemplateResponse(request, "dashboard.html", {"request": request, "user": user})

    @app.get("/profile", response_class=HTMLResponse)
    async def profile(
        request: Request,
        user: Optional[User] = Depends(optional_user)
    ):
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        return templates.TemplateResponse(request, "profile.html", {"request": request, "user": user})

    @app.get("/logout")
    async def logout():
        response = RedirectResponse(url="/", status_code=302)
        response.delete_cookie(key="auth")
        response.delete_cookie(key="session")  # Also clear the session cookie
        return response

    # API Endpoint for HTMX to fetch dashboard data
    @app.get("/api/dashboard-data")
    async def dashboard_data(user: User = Depends(current_active_user)):
        """Endpoint to fetch dashboard data with HTMX"""
        html_content = f"""
        <div class="card">
            <div class="card-header">Your Dashboard Data</div>
            <div class="card-body">
                <p>Hello, {user.name or user.email}! This content was loaded dynamically with HTMX.</p>
                <ul>
                    <li>This is some dynamic content</li>
                    <li>Updated just now</li>
                    <li>Using HTMX to fetch from the server</li>
                </ul>
            </div>
        </div>
        """
        return HTMLResponse(content=html_content)

# Create the FastAPI application
app = create_app()

# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run('main:app', host="0.0.0.0", port=8000, reload=True)