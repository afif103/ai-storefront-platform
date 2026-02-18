import uuid

from sqlalchemy import UUID, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TenantScopedBase(Base):
    """Abstract base for all tenant-scoped tables. Adds tenant_id FK + index."""

    __abstract__ = True

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
