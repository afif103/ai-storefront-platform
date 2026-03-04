"""Attribution event model — individual analytics events."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedBase

ALLOWED_EVENT_NAMES = (
    "storefront_view",
    "product_view",
    "add_to_cart",
    "begin_checkout",
    "submit_order",
    "submit_donation",
    "submit_pledge",
    "chat_open",
    "chat_message_sent",
)


class AttributionEvent(TenantScopedBase):
    __tablename__ = "attribution_events"
    __table_args__ = (
        CheckConstraint(
            "event_name IN (" + ", ".join(f"'{n}'" for n in ALLOWED_EVENT_NAMES) + ")",
            name="ck_attribution_events_event_name",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["attribution_sessions.tenant_id", "attribution_sessions.session_id"],
            name="fk_attr_events_tenant_session",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    # tenant_id inherited from TenantScopedBase
    session_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    props: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
