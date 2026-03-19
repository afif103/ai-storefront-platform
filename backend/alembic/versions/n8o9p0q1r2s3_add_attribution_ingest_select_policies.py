"""add tenant-only SELECT policies for public analytics ingest

The existing SELECT policies on attribution_* tables require
app.current_user_id to be set, which blocks ON CONFLICT DO UPDATE
and dedupe SELECT in the public (unauthenticated) ingest endpoint.

These narrow policies allow SELECT with tenant context only,
unblocking upserts and deduplication without relaxing the
authenticated dashboard SELECT policies.

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-03-19
"""

from alembic import op

revision: str = "n8o9p0q1r2s3"
down_revision: str | None = "m7n8o9p0q1r2"
branch_labels: str | None = None
depends_on: str | None = None

_TENANT_ONLY = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    op.execute(
        f"CREATE POLICY attr_visitors_ingest_select ON attribution_visitors "
        f"FOR SELECT USING ({_TENANT_ONLY})"
    )
    op.execute(
        f"CREATE POLICY attr_sessions_ingest_select ON attribution_sessions "
        f"FOR SELECT USING ({_TENANT_ONLY})"
    )
    op.execute(
        f"CREATE POLICY attr_events_ingest_select ON attribution_events "
        f"FOR SELECT USING ({_TENANT_ONLY})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS attr_events_ingest_select ON attribution_events")
    op.execute("DROP POLICY IF EXISTS attr_sessions_ingest_select ON attribution_sessions")
    op.execute("DROP POLICY IF EXISTS attr_visitors_ingest_select ON attribution_visitors")
