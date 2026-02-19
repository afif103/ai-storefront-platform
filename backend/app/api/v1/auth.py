"""Authentication endpoints."""

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.models.tenant_member import TenantMember
from app.models.user import User
from app.services.auth_service import refresh_cognito_token

router = APIRouter()

ALLOWED_REFRESH_ORIGINS = re.compile(r"^https://([a-z0-9-]+\.)?yourdomain\.com$")


@router.post("/refresh")
async def refresh_token(request: Request):
    """Refresh the access token using the httpOnly refresh cookie.

    Hardened per security.md section 1:
    - Origin validation (same-site allowlist)
    - Content-Type enforcement (application/json)
    - POST-only (enforced by router)
    """
    # 1. Origin validation
    origin = request.headers.get("origin", "")
    if settings.ENVIRONMENT == "development":
        # In dev, allow configured origins (or no origin for curl/tests)
        if origin and origin not in settings.allowed_origins_list:
            raise HTTPException(status_code=403, detail="Invalid origin")
    else:
        if not origin or not ALLOWED_REFRESH_ORIGINS.match(origin):
            raise HTTPException(status_code=403, detail="Invalid origin")

    # 2. Content-Type enforcement
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        raise HTTPException(status_code=415, detail="Unsupported media type")

    # 3. Extract refresh token from cookie
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="No refresh token")

    # 4. Call Cognito (or mock)
    try:
        new_tokens = await refresh_cognito_token(refresh_token_value)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Refresh token invalid or expired") from exc

    # 5. Build response with new refresh cookie
    response = JSONResponse(
        content={"access_token": new_tokens["access_token"]},
        status_code=200,
    )

    if "refresh_token" in new_tokens:
        response.set_cookie(
            key="refresh_token",
            value=new_tokens["refresh_token"],
            httponly=True,
            secure=settings.ENVIRONMENT != "development",
            samesite="strict",
            path="/api/v1/auth/refresh",
            max_age=2592000,  # 30 days
        )

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
    # Set user context so RLS allows the membership lookup by user_id
    await db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(user.id)},
    )

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
