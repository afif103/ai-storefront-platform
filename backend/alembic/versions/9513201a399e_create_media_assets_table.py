"""create media_assets table

Revision ID: 9513201a399e
Revises: 15e696ca6d7d
Create Date: 2026-02-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9513201a399e"
down_revision: Union[str, None] = "15e696ca6d7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
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
            "product_id",
            sa.UUID(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Indexes ---
    op.create_index(
        "ix_media_assets_tenant_entity",
        "media_assets",
        ["tenant_id", "entity_type", "entity_id"],
    )
    op.create_index(
        "ix_media_assets_product_id",
        "media_assets",
        ["product_id"],
    )

    # --- RLS ---
    op.execute("ALTER TABLE media_assets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE media_assets FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON media_assets
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON media_assets
        FOR INSERT
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON media_assets
        FOR UPDATE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON media_assets
        FOR DELETE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # --- Grant permissions to app_user ---
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON media_assets TO app_user"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON media_assets")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON media_assets")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON media_assets")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON media_assets")
    op.execute("ALTER TABLE media_assets DISABLE ROW LEVEL SECURITY")
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON media_assets FROM app_user"
    )
    op.drop_table("media_assets")
