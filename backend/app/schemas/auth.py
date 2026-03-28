"""Auth schemas."""

import uuid

from pydantic import BaseModel, EmailStr, model_validator


class LoginRequest(BaseModel):
    """Dual-mode login: real Cognito tokens or mock credentials.

    Real mode: access_token + id_token + refresh_token (all three required).
    Mock mode: email + password (both required).
    Mixing fields across modes or partial payloads are rejected.
    """

    # Real Cognito mode
    access_token: str | None = None
    id_token: str | None = None
    refresh_token: str | None = None
    # Mock mode
    email: EmailStr | None = None
    password: str | None = None

    @model_validator(mode="after")
    def _enforce_one_mode(self) -> "LoginRequest":
        token_fields = (self.access_token, self.id_token, self.refresh_token)
        mock_fields = (self.email, self.password)

        has_tokens = any(f is not None for f in token_fields)
        all_tokens = all(f is not None for f in token_fields)
        has_mock = any(f is not None for f in mock_fields)
        all_mock = all(f is not None for f in mock_fields)

        if has_tokens and has_mock:
            raise ValueError("Cannot mix token fields with email/password fields")
        if has_tokens and not all_tokens:
            raise ValueError("Real auth requires access_token, id_token, and refresh_token")
        if has_mock and not all_mock:
            raise ValueError("Mock auth requires both email and password")
        if not has_tokens and not has_mock:
            raise ValueError("Provide either Cognito tokens or email/password")
        return self


class BootstrapUser(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None


class BootstrapMembership(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    user: BootstrapUser
    memberships: list[BootstrapMembership]
    pending_invitations: int
    needs_onboarding: bool


class BootstrapResponse(BaseModel):
    user: BootstrapUser
    memberships: list[BootstrapMembership]
    pending_invitations: int
    needs_onboarding: bool


class RefreshResponse(BaseModel):
    access_token: str
