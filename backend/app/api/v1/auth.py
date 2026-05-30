"""Authentication endpoints."""

from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from jose import JWTError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db, set_user_context
from app.core.security import decode_access_token, decode_id_token
from app.models.tenant import Tenant
from app.models.tenant_member import TenantMember
from app.models.user import User
from app.schemas.auth import (
    BootstrapMembership,
    BootstrapResponse,
    BootstrapUser,
    LoginRequest,
    LoginResponse,
)
from app.services.auth_service import mock_login, refresh_cognito_token

router = APIRouter()

_EMAIL_CONFLICT_DETAIL = "Email already associated with a different account"


# ---------------------------------------------------------------------------
# Origin validation helpers
# ---------------------------------------------------------------------------

def _resolve_origin(request: Request) -> str | None:
    """Extract origin from Origin header, falling back to Referer."""
    origin = request.headers.get("origin")
    if origin:
        return origin

    referer = request.headers.get("referer")
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.hostname:
            port_suffix = f":{parsed.port}" if parsed.port else ""
            return f"{parsed.scheme}://{parsed.hostname}{port_suffix}"

    return None


def _validate_origin(request: Request) -> None:
    """Validate that the request origin is in ALLOWED_ORIGINS.

    In development, missing origin is allowed (for curl/tests).
    In production, missing origin is rejected.
    """
    origin = _resolve_origin(request)

    if origin and origin not in settings.allowed_origins_list:
        raise HTTPException(status_code=403, detail="Invalid origin")
    if not origin and settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=403, detail="Invalid origin")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _build_bootstrap(user: User, db: AsyncSession) -> dict:
    """Query memberships and pending invitations for bootstrap payload.

    Relies on app.current_user_id + app.current_user_email GUCs being set
    via set_user_context() before this call.
    """
    # Active memberships with tenant info
    result = await db.execute(
        select(TenantMember, Tenant)
        .join(Tenant, TenantMember.tenant_id == Tenant.id)
        .where(
            TenantMember.user_id == user.id,
            TenantMember.status == "active",
            Tenant.is_active.is_(True),
        )
        .order_by(TenantMember.joined_at.asc())
    )
    rows = result.all()

    memberships = [
        BootstrapMembership(
            tenant_id=tm.tenant_id,
            tenant_name=t.name,
            tenant_slug=t.slug,
            role=tm.role,
        )
        for tm, t in rows
    ]

    # Count pending invitations (visible via app.current_user_email RLS policy)
    inv_result = await db.execute(
        select(TenantMember).where(
            TenantMember.invited_email == user.email,
            TenantMember.status == "invited",
        )
    )
    pending_invitations = len(inv_result.scalars().all())

    return {
        "user": BootstrapUser(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
        ),
        "memberships": memberships,
        "pending_invitations": pending_invitations,
        "needs_onboarding": len(memberships) == 0 and pending_invitations == 0,
    }


def _set_refresh_cookie(response: JSONResponse, refresh_token: str) -> None:
    """Set the refresh_token httpOnly cookie on a response."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="strict",
        path="/api/v1/auth/refresh",
        max_age=2592000,  # 30 days
    )


async def _provision_or_update_user(
    db: AsyncSession,
    *,
    sub: str,
    email: str,
    name: str,
) -> User:
    """Find user by cognito_sub, or create. Update email/name if changed.

    Lookup order:
    1. cognito_sub match → update email/name, return
    2. normalized email match with different sub → 409 Conflict
    3. neither match → insert new user
    4. IntegrityError race → re-fetch by sub, fallback to 409
    """
    # 1. Lookup by cognito_sub
    result = await db.execute(select(User).where(User.cognito_sub == sub))
    user = result.scalar_one_or_none()

    if user is not None:
        changed = False
        if user.email != email:
            user.email = email
            changed = True
        if user.full_name != name:
            user.full_name = name
            changed = True
        if changed:
            try:
                await db.flush()
            except IntegrityError:
                # Email update collided with another user's email
                await db.rollback()
                raise HTTPException(status_code=409, detail=_EMAIL_CONFLICT_DETAIL) from None

        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is deactivated")
        return user

    # 2. Check for existing user with same email but different sub
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(status_code=409, detail=_EMAIL_CONFLICT_DETAIL)

    # 3. True new user
    user = User(cognito_sub=sub, email=email, full_name=name)
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        # 4. Concurrent insert race — re-fetch by sub first
        await db.rollback()
        result = await db.execute(select(User).where(User.cognito_sub == sub))
        user = result.scalar_one_or_none()
        if user is not None:
            if not user.is_active:
                raise HTTPException(
                    status_code=403, detail="User account is deactivated"
                ) from None
            return user
        # Not found by sub — the collision was on email
        raise HTTPException(status_code=409, detail=_EMAIL_CONFLICT_DETAIL) from None

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated")
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Token exchange + bootstrap.

    Real mode: validate Cognito access_token + id_token, provision user,
    set refresh cookie, return bootstrap payload.

    Mock mode: generate mock tokens from email/password, same flow.
    """
    _validate_origin(request)

    if settings.COGNITO_MOCK:
        # Mock mode: email + password required (enforced by schema validator)
        if body.email is None:
            raise HTTPException(status_code=400, detail="Mock mode requires email/password")

        tokens = mock_login(body.email)
        access_token = tokens["access_token"]
        email = body.email.strip().lower()
        name = email.split("@")[0]
        sub = (await decode_access_token(access_token))["sub"]
        refresh_token_value = tokens["refresh_token"]
    else:
        # Real mode: all three tokens required (enforced by schema validator)
        if body.access_token is None:
            raise HTTPException(status_code=400, detail="Real mode requires tokens")

        try:
            access_claims = await decode_access_token(body.access_token)
            id_claims = await decode_id_token(body.id_token)  # type: ignore[arg-type]
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e

        # Ensure both tokens belong to the same user
        if access_claims["sub"] != id_claims["sub"]:
            raise HTTPException(status_code=401, detail="Token sub mismatch")

        access_token = body.access_token
        sub = access_claims["sub"]
        email = id_claims.get("email", "").strip().lower()
        name = id_claims.get("name", email.split("@")[0])
        refresh_token_value = body.refresh_token  # type: ignore[assignment]

    if not email:
        raise HTTPException(status_code=401, detail="ID token missing email claim")

    # Provision or update user (email already normalized above)
    user = await _provision_or_update_user(db, sub=sub, email=email, name=name)

    # Set RLS context for bootstrap queries
    await set_user_context(db, user)

    # Build bootstrap payload
    bootstrap = await _build_bootstrap(user, db)

    response = JSONResponse(
        content=LoginResponse(
            access_token=access_token,
            **bootstrap,
        ).model_dump(mode="json"),
    )

    _set_refresh_cookie(response, refresh_token_value)

    return response


@router.post("/bootstrap", response_model=BootstrapResponse)
async def bootstrap(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return bootstrap payload for an already-authenticated user.

    Used on page refresh when the access token is already in memory.
    Uses Bearer auth via get_current_user — no id_token or refresh_token needed.
    """
    await set_user_context(db, user)
    payload = await _build_bootstrap(user, db)
    return BootstrapResponse(**payload)


@router.post("/refresh")
async def refresh_token(request: Request):
    """Refresh the access token using the httpOnly refresh cookie.

    Hardened:
    - Origin validation (ALLOWED_ORIGINS allowlist, Origin→Referer fallback)
    - Content-Type enforcement (application/json)
    - POST-only (enforced by router)
    """
    _validate_origin(request)

    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        raise HTTPException(status_code=415, detail="Unsupported media type")

    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        new_tokens = await refresh_cognito_token(refresh_token_value)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Refresh token invalid or expired") from exc

    response = JSONResponse(
        content={"access_token": new_tokens["access_token"]},
        status_code=200,
    )

    if "refresh_token" in new_tokens:
        _set_refresh_cookie(response, new_tokens["refresh_token"])

    return response


@router.post("/accept-invite")
async def accept_invite(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept pending invitations for the current user.

    Pre-tenant endpoint: matches invited_email to user.email
    and flips matching invitations from 'invited' to 'active'.
    """
    await set_user_context(db, user)

    # Find pending invitations matching user's email
    result = await db.execute(
        select(TenantMember).where(
            TenantMember.invited_email == user.email,
            TenantMember.status == "invited",
        )
    )
    invitations = result.scalars().all()

    if not invitations:
        raise HTTPException(status_code=404, detail="No pending invitations found")

    accepted = []
    for invitation in invitations:
        # Set tenant context for the UPDATE
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(invitation.tenant_id)},
        )
        invitation.user_id = user.id
        invitation.status = "active"
        invitation.joined_at = datetime.now(UTC)
        accepted.append(
            {
                "tenant_id": str(invitation.tenant_id),
                "role": invitation.role,
                "status": "active",
            }
        )

    await db.flush()

    return {"accepted": accepted}
