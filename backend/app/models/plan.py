import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ai_token_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0.000"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="KWD")
    max_members: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
