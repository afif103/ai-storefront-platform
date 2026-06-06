"""add orders.fulfillment_status

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-06
"""

import sqlalchemy as sa

from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None

_CK_NAME = "ck_orders_fulfillment_status"
_CK_SQL = "fulfillment_status IS NULL OR fulfillment_status IN ('packed', 'shipped', 'delivered')"


def upgrade() -> None:
    op.add_column("orders", sa.Column("fulfillment_status", sa.Text(), nullable=True))
    op.create_check_constraint(_CK_NAME, "orders", _CK_SQL)


def downgrade() -> None:
    op.drop_constraint(_CK_NAME, "orders", type_="check")
    op.drop_column("orders", "fulfillment_status")
