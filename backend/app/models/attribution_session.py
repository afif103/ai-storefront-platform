"""Attribution session model — one row per unique session per tenant."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedBase


class AttributionSession(TenantScopedBase):
    __tablename__ = "attribution_sessions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "session_id", name="uq_attr_sessions_tenant_session"),
        ForeignKeyConstraint(
            ["tenant_id", "visitor_id"],
            ["attribution_visitors.tenant_id", "attribution_visitors.visitor_id"],
            name="fk_attr_sessions_tenant_visitor",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    # tenant_id inherited from TenantScopedBase
    visitor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    utm_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_term: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrer: Mapped[str | None] = mapped_column(Text, nullable=True)
