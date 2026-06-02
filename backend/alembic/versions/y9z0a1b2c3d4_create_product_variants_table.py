"""create product_variants table

Revision ID: y9z0a1b2c3d4
Revises: x8y9z0a1b2c3
Create Date: 2026-06-02
"""

import sqlalchemy as sa

from alembic import op

revision = "y9z0a1b2c3d4"
down_revision = "x8y9z0a1b2c3"
branch_labels = None
depends_on = None

_NULLIF_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "product_variants",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("size", sa.Text(), nullable=True),
        sa.Column("color", sa.Text(), nullable=True),
        sa.Column("sku", sa.String(64), nullable=True),
        sa.Column("barcode", sa.String(64), nullable=True),
        sa.Column("price_amount", sa.Numeric(12, 3), nullable=True),
        sa.Column("stock_qty", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_product_variants_tenant_id", "product_variants", ["tenant_id"])
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"])

    op.execute(
        "CREATE UNIQUE INDEX uq_product_variants_tenant_sku "
        "ON product_variants (tenant_id, sku) "
        "WHERE sku IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_product_variants_tenant_barcode "
        "ON product_variants (tenant_id, barcode) "
        "WHERE barcode IS NOT NULL"
    )

    # RLS
    op.execute("ALTER TABLE product_variants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE product_variants FORCE ROW LEVEL SECURITY")

    op.execute(
        f"CREATE POLICY product_variants_select_tenant ON product_variants "
        f"FOR SELECT "
        f"USING (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        f"CREATE POLICY product_variants_insert_tenant ON product_variants "
        f"FOR INSERT "
        f"WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        f"CREATE POLICY product_variants_update_tenant ON product_variants "
        f"FOR UPDATE "
        f"USING (tenant_id = {_NULLIF_TENANT}) "
        f"WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        f"CREATE POLICY product_variants_delete_tenant ON product_variants "
        f"FOR DELETE "
        f"USING (tenant_id = {_NULLIF_TENANT})"
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON product_variants TO app_user")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON product_variants FROM app_user")
    op.execute("DROP POLICY IF EXISTS product_variants_select_tenant ON product_variants")
    op.execute("DROP POLICY IF EXISTS product_variants_insert_tenant ON product_variants")
    op.execute("DROP POLICY IF EXISTS product_variants_update_tenant ON product_variants")
    op.execute("DROP POLICY IF EXISTS product_variants_delete_tenant ON product_variants")
    op.drop_table("product_variants")
