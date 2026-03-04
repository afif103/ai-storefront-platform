"""Storefront AI conversation — one per visitor session per tenant."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, UUID, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import TenantScopedBase


class StorefrontAIConversation(TenantScopedBase):
    __tablename__ = "storefront_ai_conversations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "session_id",
            name="uq_storefront_ai_conv_tenant_session",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
