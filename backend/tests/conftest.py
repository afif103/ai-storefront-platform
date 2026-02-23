"""Shared test fixtures."""

import asyncio
import os
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Windows: use SelectorEventLoopPolicy to avoid asyncpg + ProactorEventLoop conflicts
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Ensure mock mode is on for tests
os.environ.setdefault("COGNITO_MOCK", "true")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/saas_db"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import app.core.dependencies as deps_mod  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.security import create_mock_access_token  # noqa: E402
from app.db.session import engine as app_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.plan import Plan  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.tenant_member import TenantMember  # noqa: E402
from app.models.user import User  # noqa: E402


def _provision_app_user_role() -> None:
    """Create/update the app_user Postgres role (idempotent, sync via psycopg2)."""
    import psycopg2
    from sqlalchemy.engine import make_url

    url = make_url(settings.DATABASE_URL)
    conn = psycopg2.connect(
        host=url.host,
        port=url.port or 5432,
        dbname=url.database,
        user=url.username,
        password=url.password,
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user LOGIN PASSWORD 'app_user';
            END IF;
        END
        $$;
    """
    )
    cur.execute("ALTER ROLE app_user WITH PASSWORD 'app_user';")
    cur.execute("ALTER ROLE app_user WITH LOGIN;")
    cur.execute("GRANT USAGE ON SCHEMA public TO app_user;")
    cur.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE " "ON ALL TABLES IN SCHEMA public TO app_user;"
    )
    cur.execute("GRANT USAGE, SELECT, UPDATE " "ON ALL SEQUENCES IN SCHEMA public TO app_user;")
    cur.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;"
    )
    cur.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO app_user;"
    )
    cur.close()
    conn.close()


@pytest.fixture(scope="session")
def ensure_app_user_role():
    """Session-scoped wrapper around _provision_app_user_role."""
    _provision_app_user_role()


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Async DB session (superuser) with transaction rollback after each test."""
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def rls_db() -> AsyncGenerator[AsyncSession, None]:
    """Async DB session as app_user (RLS enforced) for isolation tests."""
    rls_url = settings.DATABASE_URL.replace("postgres:postgres", "app_user:app_user")
    engine = create_async_engine(rls_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client for the FastAPI app.

    Disposes the app's connection pool after each test to prevent leaked
    connections/transactions from interfering with subsequent tests.
    Note: data committed by the app persists across tests. Tests must use
    unique slugs/names and avoid asserting global empty state.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await app_engine.dispose()


@pytest.fixture
async def rls_client(ensure_app_user_role) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with RLS enforced (app_user DB role).

    Overrides the get_db dependency so all route handlers use the app_user
    connection where RLS policies are active.
    """
    _provision_app_user_role()

    from sqlalchemy.engine import make_url

    url = make_url(settings.DATABASE_URL)
    rls_url = url.set(username="app_user", password="app_user")
    rls_engine = create_async_engine(
        rls_url.render_as_string(hide_password=False), echo=settings.DEBUG
    )
    rls_factory = async_sessionmaker(rls_engine, class_=AsyncSession, expire_on_commit=False)

    original_get_db = deps_mod.get_db

    async def _rls_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with rls_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[original_get_db] = _rls_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(original_get_db, None)
        await rls_engine.dispose()


def make_token(sub: str = "test-sub", email: str = "test@example.com") -> str:
    """Generate a mock JWT for testing."""
    return create_mock_access_token(sub=sub, email=email)


def auth_headers(sub: str = "test-sub", email: str = "test@example.com") -> dict:
    """Return Authorization headers with a mock JWT."""
    token = make_token(sub=sub, email=email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_plan(db: AsyncSession) -> Plan:
    """Seed a free plan for tests."""
    plan = Plan(name="Free", ai_token_quota=10000, max_members=3)
    db.add(plan)
    await db.flush()
    return plan


@pytest.fixture
async def seed_user(db: AsyncSession) -> User:
    """Seed a test user."""
    user = User(
        cognito_sub=f"test-sub-{uuid.uuid4().hex[:8]}",
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Test User",
    )
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def seed_tenant_with_owner(
    db: AsyncSession, seed_plan: Plan, seed_user: User
) -> tuple[Tenant, User, TenantMember]:
    """Seed a tenant with an owner membership."""
    tenant = Tenant(
        name="Test Tenant",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        plan_id=seed_plan.id,
    )
    db.add(tenant)
    await db.flush()

    # Set tenant context for RLS
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant.id)},
    )

    member = TenantMember(
        tenant_id=tenant.id,
        user_id=seed_user.id,
        role="owner",
        status="active",
        joined_at=datetime.now(UTC),
    )
    db.add(member)
    await db.flush()

    return tenant, seed_user, member
