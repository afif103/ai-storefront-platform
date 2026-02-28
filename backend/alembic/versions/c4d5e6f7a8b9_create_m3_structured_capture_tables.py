"""create orders, donations, pledges, utm_events tables (M3)

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-02-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Safe cast expression (NULLIF guard against empty-string GUC)
_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"

_TABLES = ["orders", "donations", "pledges", "utm_events"]


def _enable_rls_and_grant(table: str) -> None:
    """Enable + force RLS, create 4 policies, grant to app_user."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

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

    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user"
    )


def _drop_rls_and_revoke(table: str) -> None:
    """Drop RLS policies, disable RLS, revoke grants."""
    for action in ("select", "insert", "update", "delete"):
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation_{action} ON {table}"
        )
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute(
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM app_user"
    )


def upgrade() -> None:
    # =====================================================================
    # 1) orders
    # =====================================================================
    op.create_table(
        "orders",
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
        sa.Column("order_number", sa.Text(), nullable=False),
        sa.Column(
            "product_id",
            sa.UUID(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("customer_name", sa.Text(), nullable=False),
        sa.Column("customer_phone", sa.Text(), nullable=True),
        sa.Column("customer_email", sa.Text(), nullable=True),
        sa.Column("items", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "total_amount",
            sa.Numeric(12, 3),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'KWD'"),
        ),
        sa.Column("payment_link", sa.Text(), nullable=True),
        sa.Column("payment_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "visit_id",
            sa.UUID(),
            sa.ForeignKey("visits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'fulfilled', 'cancelled')",
            name="ck_orders_status",
        ),
        sa.UniqueConstraint(
            "tenant_id", "order_number", name="uq_orders_tenant_order_number"
        ),
    )

    op.execute(
        "CREATE INDEX ix_orders_tenant_created ON orders (tenant_id, created_at DESC)"
    )
    op.create_index(
        "ix_orders_tenant_status",
        "orders",
        ["tenant_id", "status"],
    )

    _enable_rls_and_grant("orders")

    # =====================================================================
    # 2) donations
    # =====================================================================
    op.create_table(
        "donations",
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
        sa.Column("donation_number", sa.Text(), nullable=False),
        sa.Column(
            "product_id",
            sa.UUID(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("donor_name", sa.Text(), nullable=False),
        sa.Column("donor_phone", sa.Text(), nullable=True),
        sa.Column("donor_email", sa.Text(), nullable=True),
        sa.Column(
            "amount",
            sa.Numeric(12, 3),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'KWD'"),
        ),
        sa.Column("campaign", sa.Text(), nullable=True),
        sa.Column(
            "receipt_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("payment_link", sa.Text(), nullable=True),
        sa.Column("payment_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "visit_id",
            sa.UUID(),
            sa.ForeignKey("visits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'received', 'receipted', 'cancelled')",
            name="ck_donations_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "donation_number",
            name="uq_donations_tenant_donation_number",
        ),
    )

    op.execute(
        "CREATE INDEX ix_donations_tenant_created ON donations (tenant_id, created_at DESC)"
    )
    op.create_index(
        "ix_donations_tenant_campaign",
        "donations",
        ["tenant_id", "campaign"],
    )

    _enable_rls_and_grant("donations")

    # =====================================================================
    # 3) pledges
    # =====================================================================
    op.create_table(
        "pledges",
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
        sa.Column("pledge_number", sa.Text(), nullable=False),
        sa.Column(
            "product_id",
            sa.UUID(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("pledgor_name", sa.Text(), nullable=False),
        sa.Column("pledgor_phone", sa.Text(), nullable=True),
        sa.Column("pledgor_email", sa.Text(), nullable=True),
        sa.Column(
            "amount",
            sa.Numeric(12, 3),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'KWD'"),
        ),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column(
            "fulfilled_amount",
            sa.Numeric(12, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("payment_link", sa.Text(), nullable=True),
        sa.Column("payment_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "visit_id",
            sa.UUID(),
            sa.ForeignKey("visits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pledged', 'partially_fulfilled', 'fulfilled', 'lapsed')",
            name="ck_pledges_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "pledge_number",
            name="uq_pledges_tenant_pledge_number",
        ),
    )

    op.create_index(
        "ix_pledges_tenant_status_target",
        "pledges",
        ["tenant_id", "status", "target_date"],
    )

    _enable_rls_and_grant("pledges")

    # =====================================================================
    # 4) utm_events
    # =====================================================================
    op.create_table(
        "utm_events",
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
            "visit_id",
            sa.UUID(),
            sa.ForeignKey("visits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_ref_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "event_type IN ('page_view', 'order', 'donation', 'pledge')",
            name="ck_utm_events_event_type",
        ),
    )

    op.create_index(
        "ix_utm_events_tenant_visit",
        "utm_events",
        ["tenant_id", "visit_id"],
    )
    op.create_index(
        "ix_utm_events_tenant_event_type",
        "utm_events",
        ["tenant_id", "event_type"],
    )

    _enable_rls_and_grant("utm_events")


def downgrade() -> None:
    # Reverse order: utm_events, pledges, donations, orders
    for table in reversed(_TABLES):
        _drop_rls_and_revoke(table)
        op.drop_table(table)
