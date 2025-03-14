from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
import os
import logging
from keyvault_utils import key_vault  # Import the singleton instance directly

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    
    # Authentication settings
    SECRET_KEY: str = "CHANGE_ME_TO_A_SECURE_SECRET"
    JWT_ALGORITHM: str = "HS256"
    
    # Google OAuth settings
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_CALLBACK_URL: str = "http://localhost:8000/auth/google/callback"
    
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
    USE_KEYVAULT: bool = False
    AZURE_KEYVAULT_URL: str = ''
    
    # Use environment variables first, fall back to Key Vault
    def __init__(self, **kwargs):
        # First attempt to load environment variables
        logger.info("Initializing Settings")
        
        # Check if we should use Key Vault
        use_keyvault = os.getenv("USE_KEYVAULT", "false").lower() == "true"
        logger.info(f"USE_KEYVAULT: {use_keyvault}")
        
        # Pre-load values from KeyVault if needed
        if use_keyvault:
            logger.info("Attempting to load secrets from KeyVault")
            try:
                # Fetch from KeyVault before Pydantic initialization
                client_id_from_vault = key_vault.get_secret("GOOGLE_CLIENT_ID")
                if client_id_from_vault:
                    logger.info("Found GOOGLE_CLIENT_ID in KeyVault")
                    # Set in environment so Pydantic picks it up
                    os.environ["GOOGLE_CLIENT_ID"] = client_id_from_vault
                else:
                    # Try with hyphen
                    client_id_from_vault = key_vault.get_secret("GOOGLE-CLIENT-ID")
                    if client_id_from_vault:
                        logger.info("Found GOOGLE-CLIENT-ID in KeyVault")
                        os.environ["GOOGLE_CLIENT_ID"] = client_id_from_vault
                
                client_secret_from_vault = key_vault.get_secret("GOOGLE_CLIENT_SECRET")
                if client_secret_from_vault:
                    logger.info("Found GOOGLE_CLIENT_SECRET in KeyVault")
                    os.environ["GOOGLE_CLIENT_SECRET"] = client_secret_from_vault
                else:
                    # Try with hyphen
                    client_secret_from_vault = key_vault.get_secret("GOOGLE-CLIENT-SECRET")
                    if client_secret_from_vault:
                        logger.info("Found GOOGLE-CLIENT-SECRET in KeyVault")
                        os.environ["GOOGLE_CLIENT_SECRET"] = client_secret_from_vault
                
                # Do the same for other secrets
                for env_var, vault_key in [
                    ("VIPPS_CLIENT_ID", "VIPPS-CLIENT-ID"),
                    ("VIPPS_CLIENT_SECRET", "VIPPS-CLIENT-SECRET"),
                    ("SMTP_PASSWORD", "SMTP-PASSWORD")
                ]:
                    secret_value = key_vault.get_secret(vault_key)
                    if secret_value:
                        logger.info(f"Found {vault_key} in KeyVault")
                        os.environ[env_var] = secret_value
                
            except Exception as e:
                logger.error(f"Error loading secrets from KeyVault: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # Now call Pydantic's init which will use the updated environment variables
        super().__init__(**kwargs)
        logger.info("Settings initialized successfully")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

@lru_cache()
def get_settings():
    logger.info("Creating settings instance")
    return Settings()

settings = get_settings()