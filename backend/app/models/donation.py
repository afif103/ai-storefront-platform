import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedBase


class Donation(TenantScopedBase):
    __tablename__ = "donations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "donation_number",
            name="uq_donations_tenant_donation_number",
        ),
        CheckConstraint(
            "status IN ('pending', 'received', 'receipted', 'cancelled')",
            name="ck_donations_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    # tenant_id inherited from TenantScopedBase
    donation_number: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    donor_name: Mapped[str] = mapped_column(Text, nullable=False)
    donor_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    donor_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="'KWD'")
    campaign: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
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
