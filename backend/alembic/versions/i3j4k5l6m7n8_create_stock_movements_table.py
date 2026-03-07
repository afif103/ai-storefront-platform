"""create stock_movements table

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-03-07
"""

import sqlalchemy as sa

from alembic import op

revision: str = "i3j4k5l6m7n8"
down_revision: str | None = "h2i3j4k5l6m7"
branch_labels: str | None = None
depends_on: str | None = None

_NULLIF_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "stock_movements",
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
        sa.Column(
            "product_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("delta_qty", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "order_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("orders.id"),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "reason IN ('manual_restock', 'manual_adjustment', 'order_cancel_restore')",
            name="ck_stock_movements_reason",
        ),
    )

    # Indexes
    op.create_index(
        "ix_stock_movements_tenant_id",
        "stock_movements",
        ["tenant_id"],
    )
    op.create_index(
        "ix_stock_movements_product_id",
        "stock_movements",
        ["product_id"],
    )
    op.create_index(
        "ix_stock_movements_order_id",
        "stock_movements",
        ["order_id"],
    )

    # Unique partial index — prevents double-restore per order+product
    op.execute(
        "CREATE UNIQUE INDEX uq_stock_movements_cancel_restore "
        "ON stock_movements (order_id, product_id) "
        "WHERE reason = 'order_cancel_restore'"
    )

    # RLS
    op.execute("ALTER TABLE stock_movements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE stock_movements FORCE ROW LEVEL SECURITY")

    op.execute(
        f"CREATE POLICY stock_movements_select_tenant ON stock_movements "
        f"FOR SELECT "
        f"USING (tenant_id = {_NULLIF_TENANT})"
    )
    op.execute(
        f"CREATE POLICY stock_movements_insert_tenant ON stock_movements "
        f"FOR INSERT "
        f"WITH CHECK (tenant_id = {_NULLIF_TENANT})"
    )

    op.execute("GRANT SELECT, INSERT ON stock_movements TO app_user")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT ON stock_movements FROM app_user")
    op.execute("DROP POLICY IF EXISTS stock_movements_select_tenant ON stock_movements")
    op.execute("DROP POLICY IF EXISTS stock_movements_insert_tenant ON stock_movements")
    op.drop_table("stock_movements")
