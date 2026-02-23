"""Storefront config endpoints (GET / PUT)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.storefront_config import StorefrontConfig
from app.models.user import User
from app.schemas.storefront_config import StorefrontConfigResponse, StorefrontConfigUpdate

router = APIRouter()


@router.get("", response_model=StorefrontConfigResponse | None)
async def get_storefront_config(
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
):
    """Get storefront config for the current tenant. Returns null if not configured yet."""
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    result = await db.execute(
        select(StorefrontConfig).where(StorefrontConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()
    return config


@router.put("", response_model=StorefrontConfigResponse)
async def upsert_storefront_config(
    body: StorefrontConfigUpdate,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
):
    """Create or update storefront config for the current tenant."""
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    result = await db.execute(
        select(StorefrontConfig).where(StorefrontConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()

    updates = body.model_dump(exclude_unset=True)

    if config is None:
        config = StorefrontConfig(tenant_id=tenant_id, **updates)
        db.add(config)
    else:
        for key, value in updates.items():
            setattr(config, key, value)

    await db.flush()
    await db.refresh(config)
    return config
