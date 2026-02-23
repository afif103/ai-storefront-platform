"""make media_assets entity_type/entity_id nullable

Revision ID: a1b2c3d4e5f6
Revises: 6d8d3ca665cb
Create Date: 2026-02-22

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "6d8d3ca665cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("media_assets", "entity_type", nullable=True)
    op.alter_column("media_assets", "entity_id", nullable=True)


def downgrade() -> None:
    op.execute("UPDATE media_assets SET entity_type = 'unknown' WHERE entity_type IS NULL")
    op.execute("UPDATE media_assets SET entity_id = gen_random_uuid() WHERE entity_id IS NULL")
    op.alter_column("media_assets", "entity_type", nullable=False)
    op.alter_column("media_assets", "entity_id", nullable=False)
