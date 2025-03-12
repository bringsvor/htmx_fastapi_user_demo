from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache

class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    
    # Authentication settings
    SECRET_KEY: str = "CHANGE_ME_TO_A_SECURE_SECRET"
    JWT_ALGORITHM: str = "HS256"
    
    # Google OAuth settings
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    CALLBACK_URL: str = "http://localhost:8000/auth/google/callback"
    
    # Vipps OAuth settings
    VIPPS_CLIENT_ID: Optional[str] = None
    VIPPS_CLIENT_SECRET: Optional[str] = None
    VIPPS_MSN: Optional[str] = None
    
    # Email settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_TLS: bool = True
    FROM_EMAIL: Optional[str] = None
    
    # Application settings
    APP_NAME: str = "FastAPI HTMX App"
    BASE_URL: str = "http://localhost:8000"
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()