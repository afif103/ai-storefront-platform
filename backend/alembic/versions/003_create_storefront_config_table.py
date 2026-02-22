"""Create storefront_config table with RLS

Revision ID: 003
Revises: 002
Create Date: 2026-02-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "storefront_config",
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
            unique=True,
        ),
        sa.Column("logo_s3_key", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=True),
        sa.Column("secondary_color", sa.String(7), nullable=True),
        sa.Column("hero_text", sa.Text(), nullable=True),
        sa.Column("custom_css", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- RLS ---
    op.execute("ALTER TABLE storefront_config ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE storefront_config FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON storefront_config
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON storefront_config
        FOR INSERT
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON storefront_config
        FOR UPDATE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON storefront_config
        FOR DELETE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # --- Grant permissions to app_user ---
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON storefront_config TO app_user"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON storefront_config")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON storefront_config")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON storefront_config")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON storefront_config")
    op.execute("ALTER TABLE storefront_config DISABLE ROW LEVEL SECURITY")
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON storefront_config FROM app_user"
    )
    op.drop_table("storefront_config")
