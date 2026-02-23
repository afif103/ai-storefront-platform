"""Fix RLS policies: NULLIF guard against empty-string GUC casts

Empty GUC values ('' from current_setting) cause 'invalid input syntax
for type uuid' when cast directly.  Wrap with NULLIF(..., '') so the
cast receives NULL instead.

Also adds the missing `true` (missing_ok) flag to tenant_members
INSERT / UPDATE / DELETE policies that currently call
current_setting('app.current_tenant') without it.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-02-23

"""

from typing import Sequence, Union

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Helper: safe cast expression
_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"
_USER = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"

# Old (broken) cast expressions — used in downgrade to restore originals
_OLD_TENANT_TRUE = "current_setting('app.current_tenant', true)::uuid"
_OLD_TENANT_BARE = "current_setting('app.current_tenant')::uuid"
_OLD_USER = "current_setting('app.current_user_id', true)::uuid"

# ---- Tables with standard 4-policy pattern (SELECT/INSERT/UPDATE/DELETE) ----
_STANDARD_TABLES = ["categories", "products", "storefront_config", "media_assets", "visits"]


def _drop_standard_policies(table: str) -> None:
    for action in ("select", "insert", "update", "delete"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{action} ON {table}")


def _create_standard_policies_fixed(table: str) -> None:
    op.execute(f"""
        CREATE POLICY tenant_isolation_select ON {table}
        FOR SELECT
        USING (tenant_id = {_TENANT})
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_insert ON {table}
        FOR INSERT
        WITH CHECK (tenant_id = {_TENANT})
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_update ON {table}
        FOR UPDATE
        USING (tenant_id = {_TENANT})
        WITH CHECK (tenant_id = {_TENANT})
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_delete ON {table}
        FOR DELETE
        USING (tenant_id = {_TENANT})
    """)


def _create_standard_policies_old(table: str) -> None:
    """Restore original policies (downgrade)."""
    op.execute(f"""
        CREATE POLICY tenant_isolation_select ON {table}
        FOR SELECT
        USING (tenant_id = {_OLD_TENANT_TRUE})
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_insert ON {table}
        FOR INSERT
        WITH CHECK (tenant_id = {_OLD_TENANT_TRUE})
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_update ON {table}
        FOR UPDATE
        USING (tenant_id = {_OLD_TENANT_TRUE})
        WITH CHECK (tenant_id = {_OLD_TENANT_TRUE})
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_delete ON {table}
        FOR DELETE
        USING (tenant_id = {_OLD_TENANT_TRUE})
    """)


def upgrade() -> None:
    # ---- Standard tables ----
    for table in _STANDARD_TABLES:
        _drop_standard_policies(table)
        _create_standard_policies_fixed(table)

    # ---- tenant_members (special: SELECT has dual condition + INSERT/UPDATE/DELETE
    #       were missing the `true` missing_ok flag) ----
    for action in ("select", "insert", "update", "delete"):
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation_{action} ON tenant_members"
        )

    op.execute(f"""
        CREATE POLICY tenant_isolation_select ON tenant_members
        FOR SELECT
        USING (
            tenant_id = {_TENANT}
            OR user_id = {_USER}
        )
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_insert ON tenant_members
        FOR INSERT
        WITH CHECK (tenant_id = {_TENANT})
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_update ON tenant_members
        FOR UPDATE
        USING (tenant_id = {_TENANT})
        WITH CHECK (tenant_id = {_TENANT})
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_delete ON tenant_members
        FOR DELETE
        USING (tenant_id = {_TENANT})
    """)


def downgrade() -> None:
    # ---- Standard tables — restore original policies ----
    for table in _STANDARD_TABLES:
        _drop_standard_policies(table)
        _create_standard_policies_old(table)

    # ---- tenant_members — restore original (with bare current_setting for IUD) ----
    for action in ("select", "insert", "update", "delete"):
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation_{action} ON tenant_members"
        )

    op.execute(f"""
        CREATE POLICY tenant_isolation_select ON tenant_members
        FOR SELECT
        USING (
            tenant_id = {_OLD_TENANT_TRUE}
            OR user_id = {_OLD_USER}
        )
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_insert ON tenant_members
        FOR INSERT
        WITH CHECK (tenant_id = {_OLD_TENANT_BARE})
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_update ON tenant_members
        FOR UPDATE
        USING (tenant_id = {_OLD_TENANT_BARE})
        WITH CHECK (tenant_id = {_OLD_TENANT_BARE})
    """)
    op.execute(f"""
        CREATE POLICY tenant_isolation_delete ON tenant_members
        FOR DELETE
        USING (tenant_id = {_OLD_TENANT_BARE})
    """)
