"""Create auth and tenancy tables

Revision ID: 001
Revises:
Create Date: 2026-02-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- plans (global, no RLS) ---
    op.create_table(
        "plans",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("ai_token_quota", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "price_amount",
            sa.Numeric(12, 3),
            nullable=False,
            server_default="0.000",
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KWD"),
        sa.Column("max_members", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # --- tenants (global, no RLS) ---
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False, unique=True),
        sa.Column("plan_id", sa.UUID(), sa.ForeignKey("plans.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # --- users (global, no RLS) ---
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("cognito_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- tenant_members (RLS-protected) ---
    op.create_table(
        "tenant_members",
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
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("status", sa.String(20), nullable=False, server_default="invited"),
        sa.Column("invited_email", sa.String(320), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_members_tenant_user"),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member')", name="ck_tenant_members_role"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'invited', 'removed')", name="ck_tenant_members_status"
        ),
    )
    op.create_index("ix_tenant_members_tenant_id", "tenant_members", ["tenant_id"])
    op.create_index("ix_tenant_members_user_id", "tenant_members", ["user_id"])

    # --- RLS on tenant_members ---
    op.execute("ALTER TABLE tenant_members ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_members FORCE ROW LEVEL SECURITY")

    # SELECT policy: allow by tenant_id OR user_id (for middleware resolution)
    # current_setting(..., true) returns NULL instead of erroring when unset
    op.execute("""
        CREATE POLICY tenant_isolation_select ON tenant_members
        FOR SELECT
        USING (
            tenant_id = current_setting('app.current_tenant', true)::uuid
            OR user_id = current_setting('app.current_user_id', true)::uuid
        )
    """)

    # INSERT policy: strict tenant_id check
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON tenant_members
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.current_tenant')::uuid
        )
    """)

    # UPDATE policy: strict tenant_id check
    op.execute("""
        CREATE POLICY tenant_isolation_update ON tenant_members
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.current_tenant')::uuid
        )
    """)

    # DELETE policy: strict tenant_id check
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON tenant_members
        FOR DELETE
        USING (
            tenant_id = current_setting('app.current_tenant')::uuid
        )
    """)

    # --- Grant permissions to app_user ---
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user")

    # --- Seed default Free plan ---
    op.execute("""
        INSERT INTO plans (name, ai_token_quota, price_amount, currency, max_members)
        VALUES ('Free', 10000, 0.000, 'KWD', 3)
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON tenant_members")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON tenant_members")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON tenant_members")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON tenant_members")
    op.execute("ALTER TABLE tenant_members DISABLE ROW LEVEL SECURITY")

    # Revoke grants
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM app_user"
    )
    op.execute("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM app_user")

    # Drop tables in reverse dependency order
    op.drop_table("tenant_members")
    op.drop_table("users")
    op.drop_table("tenants")
    op.drop_table("plans")
