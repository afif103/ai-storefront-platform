"""FastAPI dependency chain: JWT → User → Tenant → SET LOCAL."""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import async_session_factory
from app.models.tenant import Tenant
from app.models.tenant_member import TenantMember
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session. Commits on success, rolls back on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Extract and verify the Bearer token, returning JWT claims."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        claims = await decode_access_token(credentials.credentials)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e

    return claims


async def get_current_user(
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve cognito_sub from JWT claims to a User row.

    Auto-provisions the user if they exist in Cognito but not yet in our DB.
    """
    cognito_sub = claims.get("sub")
    if not cognito_sub:
        raise HTTPException(status_code=401, detail="Token missing sub claim")

    result = await db.execute(select(User).where(User.cognito_sub == cognito_sub))
    user = result.scalar_one_or_none()

    if user is None:
        # Auto-provision: create user from JWT claims
        email = claims.get("email", f"{cognito_sub}@placeholder.local")
        full_name = claims.get("name", claims.get("email", "Unknown"))
        user = User(
            cognito_sub=cognito_sub,
            email=email,
            full_name=full_name,
        )
        db.add(user)
        await db.flush()

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated")

    return user


async def get_db_with_tenant(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[AsyncSession, uuid.UUID]:
    """Full tenant resolution chain.

    1. SET LOCAL app.current_user_id (for RLS membership lookup)
    2. Query tenant_members for active membership
    3. SET LOCAL app.current_tenant
    4. Return (session, tenant_id)
    """
    # Step 1: set user context so RLS allows membership lookup by user_id
    await db.execute(
        text("SET LOCAL app.current_user_id = :uid"),
        {"uid": str(user.id)},
    )

    # Step 2: find active membership
    # Check for explicit tenant selection via header
    requested_tenant_id = request.headers.get("X-Tenant-Id")

    if requested_tenant_id:
        try:
            tid = uuid.UUID(requested_tenant_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid X-Tenant-Id header") from exc

        result = await db.execute(
            select(TenantMember).where(
                TenantMember.user_id == user.id,
                TenantMember.tenant_id == tid,
                TenantMember.status == "active",
            )
        )
    else:
        result = await db.execute(
            select(TenantMember)
            .where(
                TenantMember.user_id == user.id,
                TenantMember.status == "active",
            )
            .order_by(TenantMember.joined_at.asc())
        )

    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=403, detail="No active tenant membership")

    tenant_id = membership.tenant_id

    # Step 3: set tenant context for all subsequent queries in this transaction
    await db.execute(
        text("SET LOCAL app.current_tenant = :tid"),
        {"tid": str(tenant_id)},
    )

    return db, tenant_id


async def get_db_with_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> tuple[AsyncSession, Tenant]:
    """Resolve tenant slug → SET LOCAL app.current_tenant, return (db, tenant).

    Used by public /storefront/{slug} endpoints (no auth required).
    Slug lookup + SET LOCAL happen in the same DB session/transaction.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.slug == slug, Tenant.is_active.is_(True))
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Storefront not found")

    await db.execute(
        text("SET LOCAL app.current_tenant = :tid"),
        {"tid": str(tenant.id)},
    )
    return db, tenant


async def require_role(
    min_role: str,
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user: User,
) -> TenantMember:
    """Check the user has at least min_role in the current tenant.

    Call from route handlers after get_db_with_tenant.
    """
    role_hierarchy = {"owner": 3, "admin": 2, "member": 1}

    result = await db.execute(
        select(TenantMember).where(
            TenantMember.tenant_id == tenant_id,
            TenantMember.user_id == user.id,
            TenantMember.status == "active",
        )
    )
    membership = result.scalar_one_or_none()

    if membership is None or role_hierarchy.get(membership.role, 0) < role_hierarchy.get(
        min_role, 0
    ):
        raise HTTPException(status_code=403, detail=f"Requires {min_role} role or higher")

    return membership
