"""JWT verification with dual-mode support (real Cognito JWKS + mock HS256)."""

import time

import httpx
from jose import JWTError, jwt

from app.core.config import settings

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
JWKS_REFRESH_INTERVAL = 3600  # 1 hour


async def _fetch_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    url = (
        f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com"
        f"/{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    _jwks_cache = resp.json()
    _jwks_fetched_at = time.time()
    return _jwks_cache


async def _get_jwks() -> dict:
    if _jwks_cache is None or (time.time() - _jwks_fetched_at) > JWKS_REFRESH_INTERVAL:
        return await _fetch_jwks()
    return _jwks_cache


async def decode_access_token(token: str) -> dict:
    """Decode and verify an access token. Returns the claims dict."""
    if settings.COGNITO_MOCK:
        return _decode_mock_token(token)
    return await _decode_cognito_token(token)


async def _decode_cognito_token(token: str) -> dict:
    """Verify a real Cognito JWT using JWKS."""
    jwks_data = await _get_jwks()

    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    key = None
    for k in jwks_data.get("keys", []):
        if k.get("kid") == kid:
            key = k
            break
    if key is None:
        raise JWTError("Key not found in JWKS")

    issuer = (
        f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com"
        f"/{settings.COGNITO_USER_POOL_ID}"
    )

    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=settings.COGNITO_CLIENT_ID,
        issuer=issuer,
        options={"verify_at_hash": False},
    )

    if claims.get("token_use") != "access":
        raise JWTError("Not an access token")

    return claims


def _decode_mock_token(token: str) -> dict:
    """Decode a mock JWT signed with SECRET_KEY (for local dev/testing)."""
    claims = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=["HS256"],
        options={"verify_aud": False, "verify_iss": False},
    )
    return claims


def create_mock_access_token(
    sub: str,
    email: str = "test@example.com",
    expires_in: int = 900,
) -> str:
    """Create a mock JWT for testing. Only usable when COGNITO_MOCK=true."""
    payload = {
        "sub": sub,
        "email": email,
        "token_use": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
