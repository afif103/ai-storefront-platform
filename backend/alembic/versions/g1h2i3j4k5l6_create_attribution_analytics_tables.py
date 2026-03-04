"""create attribution_visitors + attribution_sessions + attribution_events tables

Revision ID: g1h2i3j4k5l6
Revises: f7a8b9c0d1e2
Create Date: 2026-03-04
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "g1h2i3j4k5l6"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | None = None
depends_on: str | None = None

# Frozen allowlist — must match app.models.attribution_event.ALLOWED_EVENT_NAMES
_ALLOWED_EVENT_NAMES = (
    "storefront_view",
    "product_view",
    "add_to_cart",
    "begin_checkout",
    "submit_order",
    "submit_donation",
    "submit_pledge",
    "chat_open",
    "chat_message_sent",
)

_NULLIF_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"
_NULLIF_USER = "NULLIF(current_setting('app.current_user_id', true), '')"

# SELECT requires both tenant + authenticated user context (blocks public reads)
_SELECT_USING = f"tenant_id = {_NULLIF_TENANT} AND {_NULLIF_USER} IS NOT NULL"
# INSERT/UPDATE requires tenant context only (allows public ingest)
_WRITE_USING = f"tenant_id = {_NULLIF_TENANT}"


def upgrade() -> None:
    # ---- attribution_visitors ----
    op.create_table(
        "attribution_visitors",
        sa.Column(
            "visitor_id",
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
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id", "visitor_id", name="uq_attr_visitors_tenant_visitor"
        ),
    )

    op.create_index("ix_attr_visitors_tenant", "attribution_visitors", ["tenant_id"])
    op.execute(
        "CREATE INDEX ix_attr_visitors_tenant_last_seen "
        "ON attribution_visitors (tenant_id, last_seen_at)"
    )

    op.execute("ALTER TABLE attribution_visitors ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE attribution_visitors FORCE ROW LEVEL SECURITY")

    op.execute(
        f"CREATE POLICY attr_visitors_select ON attribution_visitors "
        f"FOR SELECT USING ({_SELECT_USING})"
    )
    op.execute(
        f"CREATE POLICY attr_visitors_insert ON attribution_visitors "
        f"FOR INSERT WITH CHECK ({_WRITE_USING})"
    )
    op.execute(
        f"CREATE POLICY attr_visitors_update ON attribution_visitors "
        f"FOR UPDATE USING ({_WRITE_USING}) WITH CHECK ({_WRITE_USING})"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON attribution_visitors TO app_user"
    )

    # ---- attribution_sessions ----
    op.create_table(
        "attribution_sessions",
        sa.Column(
            "session_id",
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
            "visitor_id",
            sa.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("utm_source", sa.Text(), nullable=True),
        sa.Column("utm_medium", sa.Text(), nullable=True),
        sa.Column("utm_campaign", sa.Text(), nullable=True),
        sa.Column("utm_content", sa.Text(), nullable=True),
        sa.Column("utm_term", sa.Text(), nullable=True),
        sa.Column("referrer", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id", "session_id", name="uq_attr_sessions_tenant_session"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "visitor_id"],
            ["attribution_visitors.tenant_id", "attribution_visitors.visitor_id"],
            name="fk_attr_sessions_tenant_visitor",
        ),
    )

    op.create_index("ix_attr_sessions_tenant", "attribution_sessions", ["tenant_id"])
    op.execute(
        "CREATE INDEX ix_attr_sessions_tenant_last_seen "
        "ON attribution_sessions (tenant_id, last_seen_at)"
    )

    op.execute("ALTER TABLE attribution_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE attribution_sessions FORCE ROW LEVEL SECURITY")

    op.execute(
        f"CREATE POLICY attr_sessions_select ON attribution_sessions "
        f"FOR SELECT USING ({_SELECT_USING})"
    )
    op.execute(
        f"CREATE POLICY attr_sessions_insert ON attribution_sessions "
        f"FOR INSERT WITH CHECK ({_WRITE_USING})"
    )
    op.execute(
        f"CREATE POLICY attr_sessions_update ON attribution_sessions "
        f"FOR UPDATE USING ({_WRITE_USING}) WITH CHECK ({_WRITE_USING})"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON attribution_sessions TO app_user"
    )

    # ---- attribution_events ----
    check_expr = (
        "event_name IN ("
        + ", ".join(f"'{n}'" for n in _ALLOWED_EVENT_NAMES)
        + ")"
    )

    op.create_table(
        "attribution_events",
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
            "session_id",
            sa.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("props", JSONB, nullable=True),
        sa.CheckConstraint(check_expr, name="ck_attribution_events_event_name"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["attribution_sessions.tenant_id", "attribution_sessions.session_id"],
            name="fk_attr_events_tenant_session",
        ),
    )

    # Composite indexes for dashboard queries (tenant_id covered by composites)
    op.execute(
        "CREATE INDEX ix_attr_events_tenant_occurred "
        "ON attribution_events (tenant_id, occurred_at)"
    )
    op.execute(
        "CREATE INDEX ix_attr_events_tenant_name_occurred "
        "ON attribution_events (tenant_id, event_name, occurred_at)"
    )
    # Session-scoped lookup
    op.execute(
        "CREATE INDEX ix_attr_events_session "
        "ON attribution_events (session_id)"
    )
    # Dedupe index for storefront_view within 10-min window
    op.execute(
        "CREATE INDEX ix_attr_events_dedupe "
        "ON attribution_events (session_id, event_name, occurred_at DESC)"
    )

    op.execute("ALTER TABLE attribution_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE attribution_events FORCE ROW LEVEL SECURITY")

    op.execute(
        f"CREATE POLICY attr_events_select ON attribution_events "
        f"FOR SELECT USING ({_SELECT_USING})"
    )
    op.execute(
        f"CREATE POLICY attr_events_insert ON attribution_events "
        f"FOR INSERT WITH CHECK ({_WRITE_USING})"
    )
    op.execute("GRANT SELECT, INSERT ON attribution_events TO app_user")


def downgrade() -> None:
    # ---- attribution_events ----
    op.execute("REVOKE SELECT, INSERT ON attribution_events FROM app_user")
    op.execute("DROP POLICY IF EXISTS attr_events_select ON attribution_events")
    op.execute("DROP POLICY IF EXISTS attr_events_insert ON attribution_events")
    op.drop_table("attribution_events")

    # ---- attribution_sessions ----
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE ON attribution_sessions FROM app_user"
    )
    op.execute(
        "DROP POLICY IF EXISTS attr_sessions_select ON attribution_sessions"
    )
    op.execute(
        "DROP POLICY IF EXISTS attr_sessions_insert ON attribution_sessions"
    )
    op.execute(
        "DROP POLICY IF EXISTS attr_sessions_update ON attribution_sessions"
    )
    op.drop_table("attribution_sessions")

    # ---- attribution_visitors ----
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE ON attribution_visitors FROM app_user"
    )
    op.execute(
        "DROP POLICY IF EXISTS attr_visitors_select ON attribution_visitors"
    )
    op.execute(
        "DROP POLICY IF EXISTS attr_visitors_insert ON attribution_visitors"
    )
    op.execute(
        "DROP POLICY IF EXISTS attr_visitors_update ON attribution_visitors"
    )
    op.drop_table("attribution_visitors")
