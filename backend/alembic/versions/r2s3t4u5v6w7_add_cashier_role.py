"""Add cashier to tenant_members role CHECK constraint.

Revision ID: r2s3t4u5v6w7
Revises: q1r2s3t4u5v6
Create Date: 2026-03-29
"""

from alembic import op

revision = "r2s3t4u5v6w7"
down_revision = "q1r2s3t4u5v6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_tenant_members_role", "tenant_members", type_="check")
    op.create_check_constraint(
        "ck_tenant_members_role",
        "tenant_members",
        "role IN ('owner', 'admin', 'member', 'cashier')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tenant_members_role", "tenant_members", type_="check")
    op.create_check_constraint(
        "ck_tenant_members_role",
        "tenant_members",
        "role IN ('owner', 'admin', 'member')",
    )
