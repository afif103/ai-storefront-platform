"""alter storefront_config custom_css to jsonb

Revision ID: 15e696ca6d7d
Revises: 003
Create Date: 2026-02-22 09:17:30.597587

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15e696ca6d7d"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE storefront_config
        ALTER COLUMN custom_css TYPE jsonb
        USING custom_css::jsonb
    """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE storefront_config
        ALTER COLUMN custom_css TYPE json
        USING custom_css::json
    """
    )
