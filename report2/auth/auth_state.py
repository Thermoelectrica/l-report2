"""Authentication state management."""

import reflex as rx
import httpx
from typing import Optional
import logging

from report2.auth.jwt_utils import verify_jwt_token, decode_jwt_token

logger = logging.getLogger(__name__)


class AuthState(rx.State):
    """Authentication state with localStorage-based token management."""
    
    # Authentication status
    is_authenticated: bool = False
    user_id: Optional[int] = None
    
    # Login form
    login_username: str = ""
    login_password: str = ""
    login_error: str = ""
    is_logging_in: bool = False
    
    # Token and username storage (using rx.LocalStorage)
    access_token: str = rx.LocalStorage()
    refresh_token: str = rx.LocalStorage()
    username: str = rx.LocalStorage()  # Store username from login form
    
    @rx.event
    async def on_load(self):
        """Check authentication on page load."""
        # If we're on the login page, don't redirect
        if self.router.page.path == "/login":
            return
        
        # Check if we have a token
        if not self.access_token or self.access_token == "":
            logger.info("No access token found, redirecting to login")
            return rx.redirect("/login")
        
        # Verify token signature
        await self.verify_token()
    
    @rx.event
    async def verify_token(self):
        """Verify the stored access token."""
        if not self.access_token:
            self.is_authenticated = False
            return rx.redirect("/login")
        
        try:
            # Get public key from config
            from report2.config import get_auth_config
            config = get_auth_config()
            
            # Verify token signature
            payload = decode_jwt_token(self.access_token, config.jwt_public_key)
            
            if payload:
                # Token is valid
                self.is_authenticated = True
                self.user_id = payload.get("user_id")
                logger.info(f"Token verified for user: {self.username} (user_id: {self.user_id})")
            else:
                # Token invalid or expired, try to refresh
                logger.info("Token invalid or expired, attempting refresh")
                await self.refresh_access_token()
                
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            self.is_authenticated = False
            return rx.redirect("/login")
    
    @rx.event
    async def login(self, form_data: dict):
        """Login to the API and store tokens."""
        username = form_data.get("username", "")
        password = form_data.get("password", "")
        
        if not username or not password:
            self.login_error = "Please enter username and password"
            return
        
        self.is_logging_in = True
        self.login_error = ""
        
        try:
            # Use static device_id
            device_id = "report generator"
            
            # Get API URL from config
            from report2.config import get_auth_config
            config = get_auth_config()
            
            # Call login API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{config.api_base_url}/auth/login",
                    json={
                        "username": username,
                        "password": password,
                        "device_id": device_id
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Store tokens and username in localStorage
                    self.access_token = data["access_token"]
                    self.refresh_token = data["refresh_token"]
                    self.username = username  # Store the username from login form
                    
                    # Verify the token and extract user info
                    payload = decode_jwt_token(self.access_token, config.jwt_public_key)
                    if payload:
                        self.is_authenticated = True
                        self.user_id = payload.get("user_id")
                    
                    self.is_logging_in = False
                    
                    logger.info(f"Login successful for user: {self.username} (user_id: {self.user_id})")
                    
                    # Redirect to main page
                    return rx.redirect("/")
                else:
                    self.login_error = "Invalid username or password"
                    self.is_logging_in = False
                    
        except httpx.TimeoutException:
            self.login_error = "Connection timeout. Please try again."
            self.is_logging_in = False
        except httpx.ConnectError:
            self.login_error = "Cannot connect to authentication server"
            self.is_logging_in = False
        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            self.login_error = f"Login failed: {str(e)}"
            self.is_logging_in = False
    
    @rx.event
    async def logout(self):
        """Logout and clear tokens."""
        logger.info(f"Logging out user: {self.username}")
        
        # Clear tokens
        self.access_token = ""
        self.refresh_token = ""
        self.is_authenticated = False
        self.username = ""
        self.user_id = None
        
        # Redirect to login
        return rx.redirect("/login")
    
    @rx.event
    async def refresh_access_token(self):
        """Refresh the access token using refresh token."""
        if not self.refresh_token:
            logger.info("No refresh token available")
            return rx.redirect("/login")
        
        try:
            from report2.config import get_auth_config
            config = get_auth_config()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{config.api_base_url}/auth/refresh",
                    json={"refresh_token": self.refresh_token},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Update tokens
                    self.access_token = data["access_token"]
                    self.refresh_token = data["refresh_token"]
                    
                    # Verify new token
                    payload = decode_jwt_token(self.access_token, config.jwt_public_key)
                    if payload:
                        self.is_authenticated = True
                        self.user_id = payload.get("user_id")
                        logger.info(f"Token refreshed successfully for user: {self.username}")
                    else:
                        raise Exception("Invalid token received from refresh")
                else:
                    logger.warning("Token refresh failed, redirecting to login")
                    return await self.logout()
                    
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return await self.logout()
    
    async def make_authenticated_request(
        self, 
        url: str, 
        method: str = "GET", 
        **kwargs
    ) -> httpx.Response:
        """
        Make an authenticated API request.
        
        Args:
            url: API endpoint URL
            method: HTTP method
            **kwargs: Additional arguments for httpx.request
            
        Returns:
            httpx.Response object
        """
        if not self.access_token:
            raise Exception("Not authenticated")
        
        # Add authorization header
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            
            # If 401, try to refresh token and retry
            if response.status_code == 401:
                logger.info("Received 401, attempting token refresh")
                await self.refresh_access_token()
                
                # Retry with new token
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await client.request(method, url, headers=headers, **kwargs)
            
            return response
