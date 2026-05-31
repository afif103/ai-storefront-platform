"""add sku + barcode to products

Revision ID: t4u5v6w7x8y9
Revises: s3t4u5v6w7x8
Create Date: 2026-05-30
"""

import sqlalchemy as sa

from alembic import op

revision = "t4u5v6w7x8y9"
down_revision = "s3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("sku", sa.String(length=64), nullable=True))
    op.add_column("products", sa.Column("barcode", sa.String(length=64), nullable=True))
    op.create_index(
        "uq_products_tenant_sku",
        "products",
        ["tenant_id", "sku"],
        unique=True,
        postgresql_where=sa.text("sku IS NOT NULL"),
    )
    op.create_index(
        "uq_products_tenant_barcode",
        "products",
        ["tenant_id", "barcode"],
        unique=True,
        postgresql_where=sa.text("barcode IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_products_tenant_barcode", table_name="products")
    op.drop_index("uq_products_tenant_sku", table_name="products")
    op.drop_column("products", "barcode")
    op.drop_column("products", "sku")
