"""AI conversation model — one conversation per user per tenant."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, UUID, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import TenantScopedBase


class AIConversation(TenantScopedBase):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_ai_conversations_tenant_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    messages: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
