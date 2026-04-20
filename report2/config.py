"""Configuration for report2 application."""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


@dataclass
class AuthConfig:
    """Authentication configuration."""
    
    api_base_url: str
    jwt_public_key: str
    
    @classmethod
    def from_env(cls) -> "AuthConfig":
        """Load configuration from environment variables."""
        # Ensure .env is loaded
        load_dotenv()
        
        api_base_url = os.getenv("AUTH_API_BASE_URL", "")
        if not api_base_url:
            raise ValueError("AUTH_API_BASE_URL environment variable is required")
        
        jwt_public_key = os.getenv("JWT_PUBLIC_KEY", "")
        if not jwt_public_key:
            raise ValueError("JWT_PUBLIC_KEY environment variable is required")
        
        # Handle multiline public key from environment
        # Replace literal \n with actual newlines
        jwt_public_key = jwt_public_key.replace("\\n", "\n")
        
        return cls(
            api_base_url=api_base_url,
            jwt_public_key=jwt_public_key
        )


# Global config instance
_auth_config: Optional[AuthConfig] = None


def get_auth_config() -> AuthConfig:
    """Get or create authentication configuration."""
    global _auth_config
    
    if _auth_config is None:
        _auth_config = AuthConfig.from_env()
    
    return _auth_config


def reload_auth_config():
    """Reload authentication configuration from environment."""
    global _auth_config
    _auth_config = AuthConfig.from_env()
