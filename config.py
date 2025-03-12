from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
from .keyvault_utils import key_vault


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
    
    # Use environment variables first, fall back to Key Vault
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Check if we should use Key Vault
        use_keyvault = os.getenv("USE_KEYVAULT", "false").lower() == "true"
        
        if use_keyvault:
            # Only fetch from Key Vault if not already set via environment variables
            if not self.GOOGLE_CLIENT_ID:
                vault_client_id = key_vault.get_secret("GOOGLE-CLIENT-ID")
                if vault_client_id:
                    self.GOOGLE_CLIENT_ID = vault_client_id
            
            if not self.GOOGLE_CLIENT_SECRET:
                vault_client_secret = key_vault.get_secret("GOOGLE-CLIENT-SECRET")
                if vault_client_secret:
                    self.GOOGLE_CLIENT_SECRET = vault_client_secret

            if not self.VIPPS_CLIENT_ID:
                vault_client_id = key_vault.get_secret("VIPPS-CLIENT-ID")
                if vault_client_id:
                    self.VIPPS_CLIENT_ID = vault_client_id

            if not self.VIPPS_CLIENT_SECRET:
                vault_client_secret = key_vault.get_secret("VIPPS-CLIENT-SECRET")
                if vault_client_secret:
                    self.VIPPS_CLIENT_SECRET = vault_client_secret

            if not self.SMTP_PASSWORD:
                vault_smtp_password = key_vault.get_secret("SMTP-PASSWORD")
                if vault_smtp_password:
                    self.SMTP_PASSWORD = vault_smtp_password        

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()