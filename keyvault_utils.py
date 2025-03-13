from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
import os

class KeyVaultClient:
    def __init__(self):
        """Initialize the Key Vault client."""
        # Get Key Vault URL from environment variable
        self.vault_url = os.getenv("AZURE_KEYVAULT_URL")
        
        if not self.vault_url:
            raise ValueError("AZURE_KEYVAULT_URL environment variable is required")
        
        # Use Managed Identity in production (Azure), DefaultAzureCredential for local dev
        try:
            # First try Managed Identity (works in Azure)
            self.credential = ManagedIdentityCredential()
            self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)
            # Test the connection
            self._test_connection()
        except Exception as e:
            print(f"Managed Identity not available, falling back to DefaultAzureCredential: {e}")
            # Fall back to DefaultAzureCredential (works locally with az login)
            self.credential = DefaultAzureCredential()
            self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)
    
    def _test_connection(self):
        """Test the connection to Key Vault."""
        # List a single secret to verify connection works
        next(self.client.list_properties_of_secrets(max_results=1), None)
    
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
