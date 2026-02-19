"""Create catalog tables (categories, products) and tenant default_currency

Revision ID: 002
Revises: 001
Create Date: 2026-02-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Add default_currency to tenants ---
    op.add_column(
        "tenants",
        sa.Column(
            "default_currency",
            sa.String(3),
            nullable=False,
            server_default="KWD",
        ),
    )
    op.execute("""
        ALTER TABLE tenants
        ADD CONSTRAINT ck_tenants_currency
        CHECK (default_currency ~ '^[A-Z]{3}$')
    """)

    # --- categories (tenant-scoped, RLS) ---
    op.create_table(
        "categories",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_categories_tenant_name"),
    )
    op.create_index("ix_categories_tenant_id", "categories", ["tenant_id"])
    op.create_index(
        "ix_categories_tenant_active",
        "categories",
        ["tenant_id", "is_active"],
    )

    # --- products (tenant-scoped, RLS) ---
    op.create_table(
        "products",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.UUID(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_amount", sa.Numeric(12, 3), nullable=False),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_products_tenant_name"),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'",
            name="ck_products_currency",
        ),
    )
    op.create_index("ix_products_tenant_id", "products", ["tenant_id"])
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index(
        "ix_products_tenant_active",
        "products",
        ["tenant_id", "is_active"],
    )

    # --- RLS on categories ---
    op.execute("ALTER TABLE categories ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE categories FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON categories
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON categories
        FOR INSERT
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON categories
        FOR UPDATE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON categories
        FOR DELETE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # --- RLS on products ---
    op.execute("ALTER TABLE products ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE products FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON products
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON products
        FOR INSERT
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON products
        FOR UPDATE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON products
        FOR DELETE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # --- Grant permissions to app_user ---
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON categories TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON products TO app_user")


def downgrade() -> None:
    # Drop RLS policies on products
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON products")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON products")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON products")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON products")
    op.execute("ALTER TABLE products DISABLE ROW LEVEL SECURITY")

    # Drop RLS policies on categories
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON categories")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON categories")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON categories")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON categories")
    op.execute("ALTER TABLE categories DISABLE ROW LEVEL SECURITY")

    # Revoke grants
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON products FROM app_user")
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON categories FROM app_user")

    # Drop tables (products first due to FK to categories)
    op.drop_table("products")
    op.drop_table("categories")

    # Remove default_currency from tenants
    op.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS ck_tenants_currency")
    op.drop_column("tenants", "default_currency")
