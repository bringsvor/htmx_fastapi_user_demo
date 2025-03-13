import logging
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
import os
import traceback


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KeyVaultClient:
    def __init__(self):
        """Initialize the Key Vault client."""
        try:
            # Get Key Vault URL from environment variable
            self.vault_url = os.getenv("AZURE_KEYVAULT_URL")
            logger.info(f"Key Vault URL: {self.vault_url}")
        
            if not self.vault_url:
                logger.error("AZURE_KEYVAULT_URL not found in environment variables")
                raise ValueError("AZURE_KEYVAULT_URL environment variable is required")
        
            # First try Managed Identity
            logger.info("Attempting to use Managed Identity...")
            self.credential = ManagedIdentityCredential(logging_enable=True)
            self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)
            logger.info("Testing connection...")
            self._test_connection()
            logger.info("Successfully connected to Key Vault using Managed Identity")
        except Exception as e:
            logger.error(f"Managed Identity failed: {str(e)}")
            logger.error(traceback.format_exc())
            try:
                # Fall back to DefaultAzureCredential
                logger.info("Falling back to DefaultAzureCredential...")
                self.credential = DefaultAzureCredential(logging_enable=True)
                self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)
                self._test_connection()
                logger.info("Successfully connected using DefaultAzureCredential")
            except Exception as fallback_error:
                logger.error(f"All authentication methods failed: {str(fallback_error)}")
                logger.error(traceback.format_exc())
                # Re-raise so the application knows authentication failed
                raise

    def _test_connection(self):
        """Test the connection to Key Vault."""
        try:
            # Just get a list but don't use max_results parameter
            secrets_list = list(self.client.list_properties_of_secrets())
            return True
        except Exception as e:
            print(f"Error testing Key Vault connection: {e}")
            raise
    
    
    def get_secret(self, secret_name):
        """
        Get a secret from Key Vault.
        
        Args:
            secret_name (str): The name of the secret to retrieve
            
        Returns:
            str: The secret value
        """
        try:
            secret = self.client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            print(f"Error retrieving secret {secret_name}: {e}")
            # Return None if the secret can't be retrieved
            return None
