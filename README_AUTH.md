# Authentication Setup Guide

This application now includes JWT-based authentication using localStorage for token storage.

## Configuration

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Add the following to your `.env` file:

```bash
# Authentication API
AUTH_API_BASE_URL=https://your-api-url.com

# JWT Public Key (RSA format)
# Replace \n with actual newlines or use the format below
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END PUBLIC KEY-----
```

**Note:** The public key should be in PEM format. You can either:
- Use literal `\n` in the environment variable (will be converted to newlines)
- Use actual newlines in a `.env` file

### 3. Get the JWT Public Key

To get the public key from your authentication server, you need the RSA public key that was used to sign the JWT tokens. This is typically provided by your API administrator.

Example format:
```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyourpublickey...
-----END PUBLIC KEY-----
```

## How It Works

### Authentication Flow

1. **User visits the app** → Redirected to `/login` if no token
2. **User enters credentials** → Sent to `AUTH_API_BASE_URL/auth/login`
3. **API returns tokens** → Stored in `rx.LocalStorage()`
4. **Token verified** → Signature checked using `JWT_PUBLIC_KEY`
5. **Access granted** → User can access protected pages

### Token Storage

- **Access Token**: Stored in browser's localStorage
- **Refresh Token**: Stored in browser's localStorage
- **Device ID**: Generated once per browser, stored in localStorage

### Token Verification

On every page load:
1. Check if access token exists in localStorage
2. Verify token signature using the public key
3. Check token expiration
4. If invalid/expired, attempt to refresh using refresh token
5. If refresh fails, redirect to login

### Security Features

- ✅ JWT signature verification (RS256 algorithm)
- ✅ Token expiration checking
- ✅ Automatic token refresh
- ✅ Per-browser authentication (shared across tabs)
- ✅ Server-side token validation

## API Endpoints Used

### Login
```
POST /auth/login
Body: {
  "username": "string",
  "password": "string",
  "device_id": "string"
}
Response: {
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer"
}
```

### Refresh Token
```
POST /auth/refresh
Body: {
  "refresh_token": "string"
}
Response: {
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer"
}
```

### Check Authentication
```
GET /auth/check
Headers: {
  "Authorization": "Bearer <access_token>"
}
Response: 204 No Content (if valid)
```

## Usage in Code

### Making Authenticated Requests

```python
from report2.main.main_state import State

class MyState(State):
    @rx.event
    async def fetch_data(self):
        # This automatically includes the Bearer token
        response = await self.make_authenticated_request(
            "https://api.com/data",
            method="GET"
        )
        
        if response.status_code == 200:
            data = response.json()
            # Process data...
```

### Checking Authentication

```python
# In your page component
def my_protected_page() -> rx.Component:
    return rx.container(
        # ... your content ...
        on_mount=State.on_load  # This checks authentication
    )
```

## Troubleshooting

### "Cannot connect to authentication server"
- Check that `AUTH_API_BASE_URL` is correct
- Verify the API is accessible from your server
- Check network/firewall settings

### "Invalid token" or "Token verification failed"
- Ensure `JWT_PUBLIC_KEY` matches the key used by the API
- Check that the key is in correct PEM format
- Verify newlines are properly formatted

### "Token has expired"
- This is normal - the app will automatically try to refresh
- If refresh fails, user will be redirected to login

### Tokens not persisting across tabs
- Check browser's localStorage is enabled
- Verify `rx.LocalStorage()` is working correctly
- Clear browser cache and try again

## Development Tips

### Testing Without Real API

For development, you can mock the authentication:

```python
# In report2/config.py, add a development mode
@dataclass
class AuthConfig:
    api_base_url: str
    jwt_public_key: str
    dev_mode: bool = False  # Add this
    
    @classmethod
    def from_env(cls) -> "AuthConfig":
        dev_mode = os.getenv("AUTH_DEV_MODE", "false").lower() == "true"
        
        if dev_mode:
            # Use dummy values for development
            return cls(
                api_base_url="http://localhost:8000",
                jwt_public_key="dummy-key",
                dev_mode=True
            )
        # ... rest of the code
```

### Viewing Stored Tokens

In browser console:
```javascript
// View access token
localStorage.getItem('access_token')

// View refresh token
localStorage.getItem('refresh_token')

// Clear tokens (logout)
localStorage.removeItem('access_token')
localStorage.removeItem('refresh_token')
```

## Security Considerations

### ✅ What's Protected
- JWT signature verification prevents token tampering
- Token expiration prevents old tokens from being used
- Automatic refresh keeps sessions alive securely

### ⚠️ Important Notes
- Tokens are stored in localStorage (accessible by JavaScript)
- Implement Content Security Policy (CSP) to prevent XSS
- Always use HTTPS in production
- Keep JWT_PUBLIC_KEY secret in production (use environment variables)
- Consider implementing rate limiting on login attempts

### 🔒 Best Practices
1. Use short-lived access tokens (15 minutes recommended)
2. Use longer-lived refresh tokens (7 days recommended)
3. Implement token rotation on refresh
4. Clear tokens on logout
5. Validate tokens on every protected route
