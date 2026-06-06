"""add shipping config and order delivery fee

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-06
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("storefront_config", sa.Column("shipping", postgresql.JSONB(), nullable=True))
    op.add_column("orders", sa.Column("shipping_fee", sa.Numeric(12, 3), nullable=True))
    op.add_column("orders", sa.Column("shipping_method", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "shipping_method")
    op.drop_column("orders", "shipping_fee")
    op.drop_column("storefront_config", "shipping")
