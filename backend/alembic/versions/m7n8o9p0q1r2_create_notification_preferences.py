"""Create notification_preferences table with RLS

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-03-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m7n8o9p0q1r2"
down_revision: Union[str, None] = "l6m7n8o9p0q1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
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
        sa.Column(
            "email_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "telegram_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("telegram_chat_id", sa.Text(), nullable=True),
        sa.Column("telegram_bot_token_ref", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- RLS ---
    op.execute("ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notification_preferences FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON notification_preferences
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON notification_preferences
        FOR INSERT
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON notification_preferences
        FOR UPDATE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON notification_preferences
        FOR DELETE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # --- Grant permissions to app_user ---
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON notification_preferences TO app_user"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON notification_preferences"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_insert ON notification_preferences"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_update ON notification_preferences"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_delete ON notification_preferences"
    )
    op.execute(
        "ALTER TABLE notification_preferences DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON notification_preferences FROM app_user"
    )
    op.drop_table("notification_preferences")
