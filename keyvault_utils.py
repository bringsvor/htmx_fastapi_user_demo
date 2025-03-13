# keyvault_utils.py

import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KeyVaultClient:
    def __init__(self):
        """Initialize the Key Vault client."""
        logger.info("Initializing Key Vault client")
        
        self.vault_url = os.getenv("AZURE_KEYVAULT_URL")
        if not self.vault_url:
            logger.error("AZURE_KEYVAULT_URL environment variable is required")
            raise ValueError("AZURE_KEYVAULT_URL environment variable is required")
        
        logger.info(f"Using Key Vault URL: {self.vault_url}")
        
        self.client = None
        
        # Check environment
        client_id = os.getenv("AZURE_CLIENT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        
        # Try different authentication methods in order
        self._try_authentication_methods(client_id, client_secret)
    
    def _try_authentication_methods(self, client_id, client_secret):
        """Try different authentication methods in order of preference."""
        
        # 1. Try Service Principal if credentials are provided
        if client_id and client_secret:
            self._try_service_principal_auth()
            
        # 2. Try Managed Identity (in Azure environments)
        if not self.client:
            self._try_managed_identity_auth()
            
        # 3. Fall back to DefaultAzureCredential
        if not self.client:
            self._try_default_credential_auth()
    
    def _try_service_principal_auth(self):
        """Try to authenticate using a service principal."""
        try:
            logger.info("Attempting to authenticate using Service Principal...")
            from azure.identity import ClientSecretCredential
            
            tenant_id = os.getenv("AZURE_TENANT_ID")
            client_id = os.getenv("AZURE_CLIENT_ID")
            client_secret = os.getenv("AZURE_CLIENT_SECRET")
            
            if tenant_id and client_id and client_secret:
                self.credential = ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret
                )
                
                from azure.keyvault.secrets import SecretClient
                self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)
                logger.info("Successfully authenticated using Service Principal")
                return True
        except Exception as e:
            logger.error(f"Service Principal authentication failed: {e}")
        
        return False
    
    def _try_managed_identity_auth(self):
        """Try to authenticate using Managed Identity."""
        try:
            logger.info("Attempting to authenticate using Managed Identity...")
            from azure.identity import ManagedIdentityCredential
            
            self.credential = ManagedIdentityCredential()
            from azure.keyvault.secrets import SecretClient
            self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)
            
            # Test with a quick check
            logger.info("Testing Managed Identity authentication...")
            self._test_connection()
            logger.info("Successfully authenticated using Managed Identity")
            return True
        except Exception as e:
            logger.error(f"Managed Identity authentication failed: {e}")
            self.client = None  # Reset client if authentication failed
        
        return False
    
    def _try_default_credential_auth(self):
        """Try to authenticate using DefaultAzureCredential."""
        try:
            logger.info("Attempting to authenticate using DefaultAzureCredential...")
            from azure.identity import DefaultAzureCredential
            
            self.credential = DefaultAzureCredential()
            from azure.keyvault.secrets import SecretClient
            self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)
            
            # Test with a quick check
            logger.info("Testing DefaultAzureCredential authentication...")
            self._test_connection()
            logger.info("Successfully authenticated using DefaultAzureCredential")
            return True
        except Exception as e:
            logger.error(f"DefaultAzureCredential authentication failed: {e}")
            self.client = None  # Reset client if authentication failed
        
        return False
    
    def _test_connection(self):
        """Test the connection to Key Vault."""
        try:
            # A simple operation that doesn't require listing all secrets
            vault_name = self.vault_url.split('.')[0].split('/')[-1]
            logger.info(f"Testing connection to vault: {vault_name}")
            return True
        except Exception as e:
            logger.error(f"Error testing connection: {e}")
            raise
    
    def get_secret(self, secret_name):
        """Get a secret from Key Vault with better error handling."""
        if not self.client:
            logger.warning(f"No KeyVault client available to retrieve {secret_name}")
            return None
        
        try:
            logger.info(f"Attempting to get secret: {secret_name}")
            secret = self.client.get_secret(secret_name)
            logger.info(f"Successfully retrieved secret: {secret_name}")
            return secret.value
        except Exception as e:
            logger.error(f"Error retrieving secret {secret_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

# Create singleton instance
key_vault = KeyVaultClient()