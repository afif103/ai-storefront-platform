"""add low_stock_threshold to products

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-03-08
"""

import sqlalchemy as sa

from alembic import op

revision: str = "j4k5l6m7n8o9"
down_revision: str | None = "i3j4k5l6m7n8"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "low_stock_threshold",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("5"),
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "low_stock_threshold")
