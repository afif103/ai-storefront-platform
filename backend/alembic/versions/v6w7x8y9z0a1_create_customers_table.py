"""create customers table

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
Create Date: 2026-06-01
"""

import sqlalchemy as sa

from alembic import op

revision = "v6w7x8y9z0a1"
down_revision = "u5v6w7x8y9z0"
branch_labels = None
depends_on = None

_NULLIF_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "customers",
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
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_customers_tenant_id", "customers", ["tenant_id"])

    op.execute(
        "CREATE UNIQUE INDEX uq_customers_tenant_phone "
        "ON customers (tenant_id, phone) "
        "WHERE phone IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_customers_tenant_email "
        "ON customers (tenant_id, email) "
        "WHERE email IS NOT NULL"
    )

    # RLS
    op.execute("ALTER TABLE customers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE customers FORCE ROW LEVEL SECURITY")

    op.execute(
        f"CREATE POLICY customers_select_tenant ON customers "
        f"FOR SELECT "
        f"USING (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        f"CREATE POLICY customers_insert_tenant ON customers "
        f"FOR INSERT "
        f"WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        f"CREATE POLICY customers_update_tenant ON customers "
        f"FOR UPDATE "
        f"USING (tenant_id = {_NULLIF_TENANT}) "
        f"WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        f"CREATE POLICY customers_delete_tenant ON customers "
        f"FOR DELETE "
        f"USING (tenant_id = {_NULLIF_TENANT})"
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON customers TO app_user")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON customers FROM app_user")
    op.execute("DROP POLICY IF EXISTS customers_select_tenant ON customers")
    op.execute("DROP POLICY IF EXISTS customers_insert_tenant ON customers")
    op.execute("DROP POLICY IF EXISTS customers_update_tenant ON customers")
    op.execute("DROP POLICY IF EXISTS customers_delete_tenant ON customers")
    op.drop_table("customers")
