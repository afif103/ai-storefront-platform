"""add track_inventory + stock_qty to products

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-03-07
"""

import sqlalchemy as sa

from alembic import op

revision: str = "h2i3j4k5l6m7"
down_revision: str | None = "g1h2i3j4k5l6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("track_inventory", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "products",
        sa.Column("stock_qty", sa.Integer(), nullable=True, server_default="0"),
    )
    # Backfill existing rows that got NULL from the column add
    op.execute("UPDATE products SET stock_qty = 0 WHERE stock_qty IS NULL")
    op.create_check_constraint(
        "ck_products_stock_qty_non_negative",
        "products",
        "stock_qty >= 0",
    )
    op.create_index(
        "ix_products_tenant_inventory_stock",
        "products",
        ["tenant_id", "track_inventory", "stock_qty"],
    )


def downgrade() -> None:
    op.drop_index("ix_products_tenant_inventory_stock", table_name="products")
    op.drop_constraint("ck_products_stock_qty_non_negative", "products", type_="check")
    op.drop_column("products", "stock_qty")
    op.drop_column("products", "track_inventory")
