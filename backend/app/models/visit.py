import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedBase


class Visit(TenantScopedBase):
    __tablename__ = "visits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    # tenant_id inherited from TenantScopedBase
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_term: Mapped[str | None] = mapped_column(Text, nullable=True)
    landed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
