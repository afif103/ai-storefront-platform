"""create ai_conversations + ai_usage_log tables

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-03-02
"""

import sqlalchemy as sa

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | None = None
depends_on: str | None = None

_NULLIF_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    # ---- ai_conversations ----
    op.create_table(
        "ai_conversations",
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
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_ai_conversations_tenant_user"),
    )

    op.execute(
        "CREATE INDEX ix_ai_conversations_tenant_updated_desc "
        "ON ai_conversations (tenant_id, updated_at DESC)"
    )

    # RLS for ai_conversations
    op.execute("ALTER TABLE ai_conversations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ai_conversations FORCE ROW LEVEL SECURITY")

    op.execute(
        "CREATE POLICY ai_conversations_select ON ai_conversations "
        f"FOR SELECT USING (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        "CREATE POLICY ai_conversations_insert ON ai_conversations "
        f"FOR INSERT WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        "CREATE POLICY ai_conversations_update ON ai_conversations "
        f"FOR UPDATE USING (tenant_id = {_NULLIF_TENANT}) "
        f"WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )

    op.execute("GRANT SELECT, INSERT, UPDATE ON ai_conversations TO app_user")

    # ---- ai_usage_log ----
    op.create_table(
        "ai_usage_log",
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
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("ai_conversations.id"),
            nullable=False,
        ),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column(
            "cost_usd",
            sa.Numeric(10, 6),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.execute(
        "CREATE INDEX ix_ai_usage_log_tenant_created_desc "
        "ON ai_usage_log (tenant_id, created_at DESC)"
    )

    # RLS for ai_usage_log
    op.execute("ALTER TABLE ai_usage_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ai_usage_log FORCE ROW LEVEL SECURITY")

    op.execute(
        "CREATE POLICY ai_usage_log_select ON ai_usage_log "
        f"FOR SELECT USING (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        "CREATE POLICY ai_usage_log_insert ON ai_usage_log "
        f"FOR INSERT WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )

    op.execute("GRANT SELECT, INSERT ON ai_usage_log TO app_user")


def downgrade() -> None:
    # ai_usage_log
    op.execute("REVOKE SELECT, INSERT ON ai_usage_log FROM app_user")
    op.execute("DROP POLICY IF EXISTS ai_usage_log_select ON ai_usage_log")
    op.execute("DROP POLICY IF EXISTS ai_usage_log_insert ON ai_usage_log")
    op.drop_table("ai_usage_log")

    # ai_conversations
    op.execute("REVOKE SELECT, INSERT, UPDATE ON ai_conversations FROM app_user")
    op.execute("DROP POLICY IF EXISTS ai_conversations_select ON ai_conversations")
    op.execute("DROP POLICY IF EXISTS ai_conversations_insert ON ai_conversations")
    op.execute("DROP POLICY IF EXISTS ai_conversations_update ON ai_conversations")
    op.drop_table("ai_conversations")
