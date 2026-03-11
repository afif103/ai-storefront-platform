"""Notification preferences model — one row per tenant."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedBase


class NotificationPreference(TenantScopedBase):
    __tablename__ = "notification_preferences"
    __table_args__ = ()

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    # tenant_id inherited from TenantScopedBase (UNIQUE enforced in migration)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    telegram_chat_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_bot_token_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
