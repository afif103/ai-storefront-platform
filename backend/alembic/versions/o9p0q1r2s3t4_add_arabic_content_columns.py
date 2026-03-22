"""Add Arabic content columns to products and categories

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-03-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "o9p0q1r2s3t4"
down_revision: str | None = "n8o9p0q1r2s3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("name_ar", sa.String(255), nullable=True))
    op.add_column("categories", sa.Column("description_ar", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("name_ar", sa.String(255), nullable=True))
    op.add_column("products", sa.Column("description_ar", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "description_ar")
    op.drop_column("products", "name_ar")
    op.drop_column("categories", "description_ar")
    op.drop_column("categories", "name_ar")
