import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedBase


class Pledge(TenantScopedBase):
    __tablename__ = "pledges"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "pledge_number",
            name="uq_pledges_tenant_pledge_number",
        ),
        CheckConstraint(
            "status IN ('pledged', 'partially_fulfilled', 'fulfilled', 'lapsed')",
            name="ck_pledges_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    # tenant_id inherited from TenantScopedBase
    pledge_number: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    pledgor_name: Mapped[str] = mapped_column(Text, nullable=False)
    pledgor_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    pledgor_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="'KWD'")
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    fulfilled_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    payment_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    visit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
