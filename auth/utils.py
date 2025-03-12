from fastapi.responses import RedirectResponse
from fastapi_users.authentication.strategy.jwt import generate_jwt
from config import get_settings

settings = get_settings()

def create_auth_cookie_response(user_id: str, redirect_url: str = "/dashboard"):
    """
    Creates a response with an authentication cookie and redirects to the specified URL.
    
    Args:
        user_id: The user ID to include in the JWT token
        redirect_url: The URL to redirect to after setting the cookie
        
    Returns:
        RedirectResponse with the auth cookie set
    """
    # Create JWT token
    token = generate_jwt(
        data={"sub": str(user_id), "aud": "fastapi-users:auth"},
        secret=settings.SECRET_KEY,
        lifetime_seconds=3600,
    )
    
    # Create redirect response
    response = RedirectResponse(url=redirect_url, status_code=302)
    
    # Set the cookie
    cookie_name = "auth"  # Make sure this matches your cookie_transport configuration
    response.set_cookie(
        key=cookie_name,
        value=token,
        max_age=3600,
        path="/",
        secure=False,  # Set to True in production with HTTPS
        httponly=True,
        samesite="lax"
    )
    
    return response