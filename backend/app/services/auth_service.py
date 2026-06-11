"""Cognito authentication service (real + mock modes)."""

from app.core.config import settings


async def refresh_cognito_token(refresh_token: str) -> dict:
    """Call Cognito REFRESH_TOKEN_AUTH flow.

    In mock mode, returns a fresh mock access token.
    """
    if settings.COGNITO_MOCK:
        return _mock_refresh(refresh_token)

    return await _real_cognito_refresh(refresh_token)


async def _real_cognito_refresh(refresh_token: str) -> dict:
    """Call real Cognito to refresh tokens."""
    import boto3

    client = boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)

    response = client.initiate_auth(
        ClientId=settings.COGNITO_CLIENT_ID,
        AuthFlow="REFRESH_TOKEN_AUTH",
        AuthParameters={"REFRESH_TOKEN": refresh_token},
    )

    result = response["AuthenticationResult"]
    tokens: dict[str, str] = {"access_token": result["AccessToken"]}

    # Cognito may or may not return a new refresh token (rotation)
    if "RefreshToken" in result:
        tokens["refresh_token"] = result["RefreshToken"]

    return tokens


_MOCK_REFRESH_PREFIX = "mock-refresh-"


def _mock_refresh(refresh_token: str) -> dict:
    """Mint a fresh mock access token for the SAME identity encoded in the cookie.

    mock_login() issues refresh cookies of the form 'mock-refresh-<sub>' where
    <sub> starts with 'mock-'. Anything else (legacy rotated values, garbage)
    is rejected — the /auth/refresh handler converts the error into a 401 so
    the frontend falls back to a clean re-login. The cookie is identity-bearing
    and stable, so no rotated refresh_token is returned (the cookie stays).
    """
    from app.core.security import create_mock_access_token

    if not refresh_token.startswith(_MOCK_REFRESH_PREFIX):
        raise ValueError("Invalid mock refresh token")
    sub = refresh_token[len(_MOCK_REFRESH_PREFIX) :]
    if not sub.startswith("mock-"):
        raise ValueError("Invalid mock refresh token")

    # The email claim only matters when the sub is unknown (auto-provision after
    # a DB reset); a sub-derived placeholder keeps that path collision-free.
    access_token = create_mock_access_token(sub=sub, email=f"{sub}@mock.local")
    return {"access_token": access_token}


def mock_login(email: str) -> dict[str, str]:
    """Generate mock access + id + refresh tokens for local dev login.

    Normalizes email and derives a deterministic sub so that repeated
    logins with the same email resolve to the same user.
    """
    import hashlib

    from app.core.security import create_mock_access_token, create_mock_id_token

    email = email.strip().lower()
    sub = f"mock-{hashlib.sha256(email.encode()).hexdigest()[:16]}"
    return {
        "access_token": create_mock_access_token(sub=sub, email=email),
        "id_token": create_mock_id_token(sub=sub, email=email, name=email.split("@")[0]),
        "refresh_token": f"mock-refresh-{sub}",
    }
