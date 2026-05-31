"""add payment method config fields

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
Create Date: 2026-05-31
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "u5v6w7x8y9z0"
down_revision = "t4u5v6w7x8y9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("payment_method", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_orders_payment_method",
        "orders",
        "payment_method IS NULL OR payment_method IN "
        "('cash', 'knet', 'bank_transfer', 'cod', 'manual')",
    )
    op.add_column(
        "storefront_config",
        sa.Column("payment_methods", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_constraint("ck_orders_payment_method", "orders", type_="check")
    op.drop_column("orders", "payment_method")
    op.drop_column("storefront_config", "payment_methods")
