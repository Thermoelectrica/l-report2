"""JWT token verification utilities."""

import jwt
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def verify_jwt_token(token: str, public_key: str) -> bool:
    """
    Verify JWT token signature using public key.
    
    Args:
        token: JWT token string
        public_key: RSA public key in PEM format
        
    Returns:
        True if token is valid, False otherwise
    """
    try:
        # Decode and verify token
        jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_signature": True, "verify_exp": True}
        )
        return True
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return False
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return False
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return False


def decode_jwt_token(token: str, public_key: str) -> Optional[Dict[str, Any]]:
    """
    Decode JWT token and return payload if valid.
    
    Args:
        token: JWT token string
        public_key: RSA public key in PEM format
        
    Returns:
        Token payload dict if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_signature": True, "verify_exp": True}
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired without verifying signature.
    
    Args:
        token: JWT token string
        
    Returns:
        True if token is expired, False otherwise
    """
    try:
        # Decode without verification to check expiration
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False}
        )
        
        exp = payload.get("exp")
        if exp is None:
            return False
        
        return datetime.utcnow().timestamp() > exp
    except Exception:
        return True
