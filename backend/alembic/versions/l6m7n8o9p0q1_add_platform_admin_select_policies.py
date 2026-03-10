"""Add platform admin SELECT-only RLS policies on orders, donations, pledges.

Allows platform admins to read cross-tenant counts for the admin tenant list.
Same pattern as tenant_members_platform_admin_select from M6 P1.

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2026-03-10
"""

from alembic import op

revision = "l6m7n8o9p0q1"
down_revision = "k5l6m7n8o9p0"
branch_labels = None
depends_on = None

_TABLES = ["orders", "donations", "pledges"]

_POLICY_SQL = """
    CREATE POLICY {table}_platform_admin_select ON {table}
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM users
            WHERE users.id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
              AND users.is_platform_admin = true
        )
    )
"""


def upgrade() -> None:
    for table in _TABLES:
        op.execute(_POLICY_SQL.format(table=table))


def downgrade() -> None:
    for table in _TABLES:
        op.execute(
            f"DROP POLICY IF EXISTS {table}_platform_admin_select ON {table}"
        )
