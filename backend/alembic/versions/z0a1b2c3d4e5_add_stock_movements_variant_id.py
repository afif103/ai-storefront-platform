"""add stock_movements.variant_id foreign key

Revision ID: z0a1b2c3d4e5
Revises: y9z0a1b2c3d4
Create Date: 2026-06-02
"""

import sqlalchemy as sa

from alembic import op

revision = "z0a1b2c3d4e5"
down_revision = "y9z0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_movements",
        sa.Column(
            "variant_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_stock_movements_variant_id",
        "stock_movements",
        ["variant_id"],
    )

    # Rebuild the cancel-restore idempotency index to be variant-aware.
    # NULLS NOT DISTINCT keeps NULL variant_id rows mutually exclusive, so the
    # original (order_id, product_id) no-variant double-restore guard is preserved.
    op.execute("DROP INDEX uq_stock_movements_cancel_restore")
    op.execute(
        "CREATE UNIQUE INDEX uq_stock_movements_cancel_restore "
        "ON stock_movements (order_id, product_id, variant_id) "
        "NULLS NOT DISTINCT "
        "WHERE reason = 'order_cancel_restore'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX uq_stock_movements_cancel_restore")
    op.execute(
        "CREATE UNIQUE INDEX uq_stock_movements_cancel_restore "
        "ON stock_movements (order_id, product_id) "
        "WHERE reason = 'order_cancel_restore'"
    )
    op.drop_index("ix_stock_movements_variant_id", table_name="stock_movements")
    op.drop_column("stock_movements", "variant_id")
