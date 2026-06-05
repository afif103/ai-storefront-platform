"""create pos_shifts table + orders.shift_id

Revision ID: b2c3d4e5f6a7
Revises: z0a1b2c3d4e5
Create Date: 2026-06-04
"""

import sqlalchemy as sa

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "z0a1b2c3d4e5"
branch_labels = None
depends_on = None

_NULLIF_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"
_TENANT_MATCH = f"tenant_id = {_NULLIF_TENANT}"

# (policy-name suffix, command, using/check clause) — one CREATE POLICY per row.
_SHIFT_POLICIES = (
    ("select_tenant", "FOR SELECT", f"USING ({_TENANT_MATCH})"),
    ("insert_tenant", "FOR INSERT", f"WITH CHECK ({_TENANT_MATCH})"),
    ("update_tenant", "FOR UPDATE", f"USING ({_TENANT_MATCH}) WITH CHECK ({_TENANT_MATCH})"),
    ("delete_tenant", "FOR DELETE", f"USING ({_TENANT_MATCH})"),
)


def upgrade() -> None:
    op.create_table(
        "pos_shifts",
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
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("starting_cash", sa.Numeric(12, 3), nullable=False),
        sa.Column("counted_cash", sa.Numeric(12, 3), nullable=True),
        sa.Column("closing_cash_sales", sa.Numeric(12, 3), nullable=True),
        sa.Column(
            "opened_by",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "closed_by",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_pos_shifts_status"),
        sa.CheckConstraint("starting_cash >= 0", name="ck_pos_shifts_starting_cash"),
        sa.CheckConstraint(
            "counted_cash IS NULL OR counted_cash >= 0",
            name="ck_pos_shifts_counted_cash",
        ),
        sa.CheckConstraint(
            "closing_cash_sales IS NULL OR closing_cash_sales >= 0",
            name="ck_pos_shifts_closing_cash_sales",
        ),
    )

    op.create_index("ix_pos_shifts_tenant_id", "pos_shifts", ["tenant_id"])
    op.create_index(
        "uq_pos_shifts_one_open_per_tenant",
        "pos_shifts",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    # RLS: tenant-scoped CRUD, mirroring existing tenant tables.
    op.execute("ALTER TABLE pos_shifts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE pos_shifts FORCE ROW LEVEL SECURITY")
    for suffix, command, clause in _SHIFT_POLICIES:
        op.execute(f"CREATE POLICY pos_shifts_{suffix} ON pos_shifts {command} {clause}")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON pos_shifts TO app_user")

    # orders.shift_id — links a POS sale to the shift it was rung up in.
    op.add_column("orders", sa.Column("shift_id", sa.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_orders_shift_id",
        "orders",
        "pos_shifts",
        ["shift_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_orders_shift_id", "orders", ["shift_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_shift_id", table_name="orders")
    op.drop_constraint("fk_orders_shift_id", "orders", type_="foreignkey")
    op.drop_column("orders", "shift_id")

    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON pos_shifts FROM app_user")
    for suffix in ("select_tenant", "insert_tenant", "update_tenant", "delete_tenant"):
        op.execute(f"DROP POLICY IF EXISTS pos_shifts_{suffix} ON pos_shifts")
    op.execute("DROP INDEX IF EXISTS uq_pos_shifts_one_open_per_tenant")
    op.drop_table("pos_shifts")
