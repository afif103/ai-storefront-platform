"""Add invited_email condition to tenant_members SELECT policy

Pending invitations (user_id IS NULL) were invisible under RLS when only
app.current_user_id was set, because NULL != uuid always evaluates false.

This migration:
1. Adds a third OR condition to the SELECT policy so rows matching the
   caller's email via app.current_user_email GUC are visible.
2. Backfills existing invited_email values to LOWER(BTRIM(...)) for
   consistent case-insensitive matching.

Revision ID: p0q1r2s3t4u5
Revises: o9p0q1r2s3t4
Create Date: 2026-03-28

"""

from collections.abc import Sequence

from alembic import op

revision: str = "p0q1r2s3t4u5"
down_revision: str | None = "o9p0q1r2s3t4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"
_USER = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"
_EMAIL = "NULLIF(current_setting('app.current_user_email', true), '')"


def upgrade() -> None:
    # Backfill: normalize all existing invited_email values
    op.execute(
        """
        UPDATE tenant_members
        SET invited_email = LOWER(BTRIM(invited_email))
        WHERE invited_email IS NOT NULL
          AND invited_email != LOWER(BTRIM(invited_email))
        """
    )

    # Replace the SELECT policy with a three-condition version
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON tenant_members")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_select ON tenant_members
        FOR SELECT
        USING (
            tenant_id = {_TENANT}
            OR user_id = {_USER}
            OR invited_email = {_EMAIL}
        )
        """
    )


def downgrade() -> None:
    # Restore the two-condition SELECT policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON tenant_members")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_select ON tenant_members
        FOR SELECT
        USING (
            tenant_id = {_TENANT}
            OR user_id = {_USER}
        )
        """
    )
    # Note: the lowercase backfill is not reversed — lowercase is always correct
