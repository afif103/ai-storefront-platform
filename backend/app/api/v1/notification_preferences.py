"""Notification preferences endpoints (GET / PUT)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.notification_preference import NotificationPreference
from app.models.user import User
from app.schemas.notification_preference import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)

router = APIRouter()


@router.get("", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
):
    """Get notification preferences for the current tenant.

    Auto-creates a default row (both disabled) on first read.
    Any authenticated tenant member can read.
    """
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.tenant_id == tenant_id)
    )
    prefs = result.scalar_one_or_none()

    if prefs is None:
        prefs = NotificationPreference(tenant_id=tenant_id)
        db.add(prefs)
        await db.flush()
        await db.refresh(prefs)

    return prefs


@router.put("", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    body: NotificationPreferencesUpdate,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
):
    """Update notification preferences for the current tenant.

    Admin or owner only. Partial update — only provided fields are changed.
    """
    db, tenant_id = db_tenant
    await require_role("admin", db, tenant_id, user)

    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.tenant_id == tenant_id)
    )
    prefs = result.scalar_one_or_none()

    updates = body.model_dump(exclude_unset=True)

    # Validate: if telegram_enabled is being left as-is (not in updates),
    # but the existing row already has telegram_enabled=True and
    # telegram_chat_id is being cleared, reject.
    if prefs is not None and "telegram_enabled" not in updates:
        new_chat_id = updates.get("telegram_chat_id", prefs.telegram_chat_id)
        if prefs.telegram_enabled and not new_chat_id:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail="telegram_chat_id is required while Telegram notifications are enabled",
            )

    if prefs is None:
        prefs = NotificationPreference(tenant_id=tenant_id, **updates)
        db.add(prefs)
    else:
        for key, value in updates.items():
            setattr(prefs, key, value)
        prefs.updated_at = datetime.now(UTC)

    await db.flush()
    await db.refresh(prefs)
    return prefs
