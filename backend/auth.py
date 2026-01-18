import os
from fastapi import Request, HTTPException, status
from jose import jwt, jwk
import requests
from functools import lru_cache

# Cache JWKS to avoid fetch on every request
@lru_cache(maxsize=1)
def get_jwks():
    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        raise ValueError("SUPABASE_URL not set")
    
    # JWKS endpoint: {PROJECT_URL}/rest/v1/.well-known/jwks.json
    # Note: Check if project uses custom domain or standard supabase.co
    # Standard: https://[project-ref].supabase.co/auth/v1/.well-known/jwks.json
    # Or sometimes at root. Bento docs say "validates using Supabase JWKS".
    
    # Try the standard Auth path
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch JWKS: {e}")
        # Fallback/Retry logic could go here
        raise e

async def get_current_user_token(request: Request):
    """
    Validates Supabase JWT using JWKS (Asymmetric Keys).
    Expects: Authorization: Bearer <token>
    Returns: (user_payload, raw_token)
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        # Allow anonymous for now if endpoint handles it, or raise 401
        # For strict auth:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Authorization Header")

    try:
        scheme, token = auth_header.split(" ")
        if scheme.lower() != "bearer":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Auth Scheme")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Auth Format")

    # 1. Get Key ID (kid) from header
    try:
        headers = jwt.get_unverified_headers(token)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Token Headers")
        
    kid = headers.get("kid")
    if not kid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing 'kid' in token")

    # 2. Fetch JWKS from Supabase
    try:
        jwks = get_jwks()
    except Exception:
         raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Auth Provider Unavailable")
    
    # 3. Find matching key
    key_data = next((k for k in jwks["keys"] if k["kid"] == kid), None)
    if not key_data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Key ID")
    
    # 4. Verify & Decode
    try:
        public_key = jwk.construct(key_data)
        payload = jwt.decode(
            token, 
            public_key.to_pem().decode("utf-8"), 
            algorithms=[headers.get("alg", "RS256")],
            options={"verify_aud": False} 
        )
        return payload, token
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token Verification Failed: {str(e)}")

async def get_current_user(request: Request):
    # Convenience wrapper returning just the payload
    payload, _ = await get_current_user_token(request)
    return payload
