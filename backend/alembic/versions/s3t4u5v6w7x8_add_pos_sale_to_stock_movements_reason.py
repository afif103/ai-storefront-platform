"""Add pos_sale to stock_movements reason CHECK constraint.

Revision ID: s3t4u5v6w7x8
Revises: r2s3t4u5v6w7
Create Date: 2026-05-30
"""

from alembic import op

revision = "s3t4u5v6w7x8"
down_revision = "r2s3t4u5v6w7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_stock_movements_reason", "stock_movements", type_="check")
    op.create_check_constraint(
        "ck_stock_movements_reason",
        "stock_movements",
        "reason IN ('manual_restock', 'manual_adjustment', " "'order_cancel_restore', 'pos_sale')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_stock_movements_reason", "stock_movements", type_="check")
    op.create_check_constraint(
        "ck_stock_movements_reason",
        "stock_movements",
        "reason IN ('manual_restock', 'manual_adjustment', 'order_cancel_restore')",
    )
