"""add donations.customer_id foreign key

Revision ID: x8y9z0a1b2c3
Revises: w7x8y9z0a1b2
Create Date: 2026-06-02
"""

import sqlalchemy as sa

from alembic import op

revision = "x8y9z0a1b2c3"
down_revision = "w7x8y9z0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "donations",
        sa.Column(
            "customer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_donations_customer_id", "donations", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_donations_customer_id", table_name="donations")
    op.drop_column("donations", "customer_id")
