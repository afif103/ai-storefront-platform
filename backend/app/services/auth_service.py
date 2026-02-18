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


def _mock_refresh(refresh_token: str) -> dict:
    """Generate a mock refresh response for local development."""
    from app.core.security import create_mock_access_token

    access_token = create_mock_access_token(
        sub="mock-user-sub",
        email="dev@example.com",
    )
    return {
        "access_token": access_token,
        "refresh_token": "mock-refresh-token-rotated",
    }
