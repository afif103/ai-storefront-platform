"""Attribution visitor model — deduplicated visitor registry."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedBase


class AttributionVisitor(TenantScopedBase):
    __tablename__ = "attribution_visitors"
    __table_args__ = (
        UniqueConstraint("tenant_id", "visitor_id", name="uq_attr_visitors_tenant_visitor"),
    )

    visitor_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    # tenant_id inherited from TenantScopedBase
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
