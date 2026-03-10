"""Add is_platform_admin to users + platform admin RLS policy on tenant_members.

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "k5l6m7n8o9p0"
down_revision = "j4k5l6m7n8o9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Allow platform admins to SELECT all tenant_members rows (cross-tenant).
    # Requires app.current_user_id to be set to a user with is_platform_admin=true.
    # SELECT-only — no INSERT/UPDATE/DELETE bypass.
    op.execute(
        """
        CREATE POLICY tenant_members_platform_admin_select ON tenant_members
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE users.id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                  AND users.is_platform_admin = true
            )
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_members_platform_admin_select ON tenant_members"
    )
    op.drop_column("users", "is_platform_admin")
