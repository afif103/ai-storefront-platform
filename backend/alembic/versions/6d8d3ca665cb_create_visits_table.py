"""create visits table

Revision ID: 6d8d3ca665cb
Revises: 9513201a399e
Create Date: 2026-02-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6d8d3ca665cb"
down_revision: Union[str, None] = "9513201a399e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visits",
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
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("ip_hash", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("utm_source", sa.Text(), nullable=True),
        sa.Column("utm_medium", sa.Text(), nullable=True),
        sa.Column("utm_campaign", sa.Text(), nullable=True),
        sa.Column("utm_content", sa.Text(), nullable=True),
        sa.Column("utm_term", sa.Text(), nullable=True),
        sa.Column(
            "landed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_visits_tenant_landed",
        "visits",
        ["tenant_id", sa.text("landed_at DESC")],
    )

    # --- RLS ---
    op.execute("ALTER TABLE visits ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE visits FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON visits
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON visits
        FOR INSERT
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON visits
        FOR UPDATE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON visits
        FOR DELETE
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # --- Grant permissions to app_user ---
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON visits TO app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON visits")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON visits")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON visits")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON visits")
    op.execute("ALTER TABLE visits DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON visits FROM app_user")
    op.drop_table("visits")
