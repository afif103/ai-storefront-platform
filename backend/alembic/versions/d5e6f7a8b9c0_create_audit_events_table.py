"""create audit_events table

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-02
"""

import sqlalchemy as sa

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
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
            "actor_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("entity_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=True),
        sa.Column("metadata_", sa.JSON(), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Indexes
    op.create_index(
        "ix_audit_events_tenant_entity",
        "audit_events",
        ["tenant_id", "entity_type", "entity_id"],
    )
    op.execute(
        "CREATE INDEX ix_audit_events_tenant_created_desc "
        "ON audit_events (tenant_id, created_at DESC)"
    )

    # RLS
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")

    op.execute(
        "CREATE POLICY audit_events_select_tenant ON audit_events "
        "FOR SELECT "
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)"
    )
    op.execute(
        "CREATE POLICY audit_events_insert_tenant ON audit_events "
        "FOR INSERT "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)"
    )

    op.execute("GRANT SELECT, INSERT ON audit_events TO app_user")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT ON audit_events FROM app_user")
    op.execute("DROP POLICY IF EXISTS audit_events_select_tenant ON audit_events")
    op.execute("DROP POLICY IF EXISTS audit_events_insert_tenant ON audit_events")
    op.drop_table("audit_events")
