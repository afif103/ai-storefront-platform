"""POS shift model — cashier open/close with cash reconciliation."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedBase

_CK_COUNTED_CASH = "counted_cash IS NULL OR counted_cash >= 0"
_CK_CLOSING_CASH = "closing_cash_sales IS NULL OR closing_cash_sales >= 0"


def _ts_column(**kwargs):
    """Timezone-aware timestamp column (keeps declarations on one line)."""
    return mapped_column(DateTime(timezone=True), **kwargs)


class PosShift(TenantScopedBase):
    __tablename__ = "pos_shifts"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'closed')", name="ck_pos_shifts_status"),
        CheckConstraint("starting_cash >= 0", name="ck_pos_shifts_starting_cash"),
        CheckConstraint(_CK_COUNTED_CASH, name="ck_pos_shifts_counted_cash"),
        CheckConstraint(_CK_CLOSING_CASH, name="ck_pos_shifts_closing_cash_sales"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    # tenant_id inherited from TenantScopedBase
    status: Mapped[str] = mapped_column(Text, nullable=False)
    starting_cash: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    closing_cash_sales: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    opened_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    opened_at: Mapped[datetime] = _ts_column(server_default=func.now())
    closed_at: Mapped[datetime | None] = _ts_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = _ts_column(onupdate=func.now())
