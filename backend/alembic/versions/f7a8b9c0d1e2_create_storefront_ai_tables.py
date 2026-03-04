"""create storefront_ai_conversations + storefront_ai_usage_log tables

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-03-03
"""

import sqlalchemy as sa

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | None = None
depends_on: str | None = None

_NULLIF_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    # ---- storefront_ai_conversations ----
    op.create_table(
        "storefront_ai_conversations",
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
            index=True,
        ),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column(
            "messages",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "session_id",
            name="uq_storefront_ai_conv_tenant_session",
        ),
    )

    op.execute(
        "CREATE INDEX ix_sf_ai_conv_tenant_updated_desc "
        "ON storefront_ai_conversations (tenant_id, updated_at DESC)"
    )

    op.execute("ALTER TABLE storefront_ai_conversations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE storefront_ai_conversations FORCE ROW LEVEL SECURITY")

    op.execute(
        "CREATE POLICY sf_ai_conv_select ON storefront_ai_conversations "
        f"FOR SELECT USING (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        "CREATE POLICY sf_ai_conv_insert ON storefront_ai_conversations "
        f"FOR INSERT WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        "CREATE POLICY sf_ai_conv_update ON storefront_ai_conversations "
        f"FOR UPDATE USING (tenant_id = {_NULLIF_TENANT}) "
        f"WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON storefront_ai_conversations TO app_user")

    # ---- storefront_ai_usage_log ----
    op.create_table(
        "storefront_ai_usage_log",
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
            index=True,
        ),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column(
            "conversation_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("storefront_ai_conversations.id"),
            nullable=False,
        ),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.execute(
        "CREATE INDEX ix_sf_ai_usage_tenant_created_desc "
        "ON storefront_ai_usage_log (tenant_id, created_at DESC)"
    )

    op.execute("ALTER TABLE storefront_ai_usage_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE storefront_ai_usage_log FORCE ROW LEVEL SECURITY")

    op.execute(
        "CREATE POLICY sf_ai_usage_select ON storefront_ai_usage_log "
        f"FOR SELECT USING (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        "CREATE POLICY sf_ai_usage_insert ON storefront_ai_usage_log "
        f"FOR INSERT WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute("GRANT SELECT, INSERT ON storefront_ai_usage_log TO app_user")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT ON storefront_ai_usage_log FROM app_user")
    op.execute("DROP POLICY IF EXISTS sf_ai_usage_select ON storefront_ai_usage_log")
    op.execute("DROP POLICY IF EXISTS sf_ai_usage_insert ON storefront_ai_usage_log")
    op.drop_table("storefront_ai_usage_log")

    op.execute("REVOKE SELECT, INSERT, UPDATE ON storefront_ai_conversations FROM app_user")
    op.execute("DROP POLICY IF EXISTS sf_ai_conv_select ON storefront_ai_conversations")
    op.execute("DROP POLICY IF EXISTS sf_ai_conv_insert ON storefront_ai_conversations")
    op.execute("DROP POLICY IF EXISTS sf_ai_conv_update ON storefront_ai_conversations")
    op.drop_table("storefront_ai_conversations")
