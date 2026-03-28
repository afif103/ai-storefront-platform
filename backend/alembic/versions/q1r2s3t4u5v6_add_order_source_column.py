"""Add source column to orders table

Distinguishes order origin: 'storefront' (public checkout) vs 'pos'
(point-of-sale cash register).  Existing rows default to 'storefront'.

Revision ID: q1r2s3t4u5v6
Revises: p0q1r2s3t4u5
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa

revision = "q1r2s3t4u5v6"
down_revision = "p0q1r2s3t4u5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'storefront'"),
        ),
    )
    op.create_check_constraint(
        "ck_orders_source",
        "orders",
        "source IN ('storefront', 'pos')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_orders_source", "orders", type_="check")
    op.drop_column("orders", "source")
