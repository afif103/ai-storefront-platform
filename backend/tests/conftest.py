"""Shared test fixtures."""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure mock mode is on for tests
os.environ.setdefault("COGNITO_MOCK", "true")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/saas_db"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.core.config import settings  # noqa: E402
from app.core.security import create_mock_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.plan import Plan  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.tenant_member import TenantMember  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create engine connecting as postgres (superuser) for test setup."""
    engine = create_async_engine(settings.DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def rls_engine():
    """Create engine connecting as app_user (RLS enforced) for isolation tests."""
    rls_url = settings.DATABASE_URL.replace("postgres:postgres", "app_user:app_user")
    engine = create_async_engine(rls_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Async DB session (superuser) with transaction rollback after each test."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def rls_db(rls_engine) -> AsyncGenerator[AsyncSession, None]:
    """Async DB session as app_user (RLS enforced) for isolation tests."""
    factory = async_sessionmaker(rls_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


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
        text("SET LOCAL app.current_tenant = :tid"),
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
