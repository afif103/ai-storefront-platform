import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TenantScopedBase


class TenantMember(TenantScopedBase):
    __tablename__ = "tenant_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_members_tenant_user"),
        CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_tenant_members_role"),
        CheckConstraint(
            "status IN ('active', 'invited', 'removed')", name="ck_tenant_members_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    # tenant_id inherited from TenantScopedBase
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invited")
    invited_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship(back_populates="members")  # noqa: F821
    user: Mapped["User | None"] = relationship()  # noqa: F821
