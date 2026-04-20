"""JWT token verification utilities."""

import jwt
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def verify_jwt_token(token: str, public_key: Optional[str]) -> bool:
    """
    Verify JWT token signature using public key.
    
    Args:
        token: JWT token string
        public_key: RSA public key in PEM format (optional - if None, signature verification is disabled)
        
    Returns:
        True if token is valid, False otherwise
    """
    # Use decode_jwt_token and return True if payload is not None
    payload = decode_jwt_token(token, public_key)
    return payload is not None


def decode_jwt_token(token: str, public_key: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Decode JWT token and return payload if valid.
    
    Args:
        token: JWT token string
        public_key: RSA public key in PEM format (optional - if None, signature verification is disabled)
        
    Returns:
        Token payload dict if valid, None otherwise
    """
    try:
        if public_key:
            # Verify signature with public key
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={"verify_signature": True, "verify_exp": True}
            )
            logger.info(f"Token verified and decoded for user: {payload.get('sub', 'unknown')}")
        else:
            # No public key provided - skip signature verification
            logger.warning("JWT signature verification is DISABLED - no public key configured")
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
            logger.info(f"Token decoded without verification for user: {payload.get('sub', 'unknown')}")
        
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
