import os
from fastapi import Request, HTTPException, status
from jose import jwt, jwk
import requests
from functools import lru_cache

from datetime import datetime, timedelta

# Cache JWKS with 1-hour TTL
_jwks_cache = {"data": None, "expires_at": None}

def get_jwks():
    now = datetime.now()
    if _jwks_cache["data"] and _jwks_cache["expires_at"] and _jwks_cache["expires_at"] > now:
        return _jwks_cache["data"]

    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        raise ValueError("SUPABASE_URL not set")
    
    # JWKS endpoint logic
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url)
        response.raise_for_status()
        data = response.json()
        
        # Update Cache
        _jwks_cache["data"] = data
        _jwks_cache["expires_at"] = now + timedelta(hours=1)
        
        return data
    except Exception as e:
        print(f"Failed to fetch JWKS: {e}")
        raise e

async def get_current_user_token(request: Request):
    """
    Validates Supabase JWT using JWKS (Asymmetric Keys).
    Expects: Authorization: Bearer <token>
    Returns: (user_payload, raw_token)
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
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
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Token Headers")
        
    kid = headers.get("kid")
    if not kid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing 'kid' in token")

    # 2. Fetch JWKS from Supabase
    try:
        jwks = get_jwks()
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Auth Provider Unavailable")
    
    # 3. Find matching key
    key_data = next((k for k in jwks["keys"] if k["kid"] == kid), None)
    if not key_data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Key ID")
    
    # 4. Verify & Decode
    try:
        # Supabase uses ES256. python-jose handles JWK dicts directly.
        alg = headers.get("alg", "RS256")
        
        payload = jwt.decode(
            token, 
            key_data, # Use the JWK dict directly
            algorithms=[alg],
            options={
                "verify_aud": False,
                "verify_sub": True,
                "verify_iat": True,
                "verify_exp": True
            } 
        )
        return payload, token
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has expired")
    except jwt.JWTClaimsError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token claims: {str(e)}")
    except Exception as e:
        # If it's a signature error, let's log the key info (safely)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token Verification Failed: {str(e)}")

async def get_current_user(request: Request):
    # Convenience wrapper returning just the payload
    payload, _ = await get_current_user_token(request)
    return payload
