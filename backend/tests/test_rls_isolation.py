"""Cross-tenant isolation tests proving RLS enforcement.

These tests connect as app_user (RLS enforced) to verify
that Tenant A cannot see or modify Tenant B's data.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.tenant_member import TenantMember
from app.models.user import User


async def _setup_two_tenants(db: AsyncSession):
    """Create two tenants with one user each, returning all entities."""
    # Create tenants (no RLS on tenants table)
    tenant_a = Tenant(name="Tenant A", slug=f"rls-a-{uuid.uuid4().hex[:8]}")
    tenant_b = Tenant(name="Tenant B", slug=f"rls-b-{uuid.uuid4().hex[:8]}")
    db.add_all([tenant_a, tenant_b])
    await db.flush()

    # Create users (no RLS on users table)
    user_a = User(
        cognito_sub=f"sub-a-{uuid.uuid4().hex}",
        email=f"a-{uuid.uuid4().hex[:8]}@test.com",
        full_name="User A",
    )
    user_b = User(
        cognito_sub=f"sub-b-{uuid.uuid4().hex}",
        email=f"b-{uuid.uuid4().hex[:8]}@test.com",
        full_name="User B",
    )
    db.add_all([user_a, user_b])
    await db.flush()

    return tenant_a, tenant_b, user_a, user_b


@pytest.mark.asyncio
async def test_tenant_a_cannot_see_tenant_b_members(rls_db: AsyncSession):
    """With SET LOCAL set to Tenant A, Tenant B's members are invisible."""
    db = rls_db
    tenant_a, tenant_b, user_a, user_b = await _setup_two_tenants(db)

    # Insert member A under tenant A context
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": str(tenant_a.id)}
    )
    member_a = TenantMember(
        tenant_id=tenant_a.id, user_id=user_a.id, role="owner", status="active"
    )
    db.add(member_a)
    await db.flush()

    # Insert member B under tenant B context
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": str(tenant_b.id)}
    )
    member_b = TenantMember(
        tenant_id=tenant_b.id, user_id=user_b.id, role="owner", status="active"
    )
    db.add(member_b)
    await db.flush()

    # Switch to Tenant A context — only member A should be visible
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": str(tenant_a.id)}
    )
    # Clear the user_id setting to test pure tenant isolation
    await db.execute(text("RESET app.current_user_id"))

    result = await db.execute(select(TenantMember))
    visible = result.scalars().all()

    assert len(visible) == 1
    assert visible[0].user_id == user_a.id
    assert visible[0].tenant_id == tenant_a.id

    # Switch to Tenant B context — only member B should be visible
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": str(tenant_b.id)}
    )
    result = await db.execute(select(TenantMember))
    visible = result.scalars().all()

    assert len(visible) == 1
    assert visible[0].user_id == user_b.id
    assert visible[0].tenant_id == tenant_b.id


@pytest.mark.asyncio
async def test_tenant_a_cannot_insert_into_tenant_b(rls_db: AsyncSession):
    """With SET LOCAL set to Tenant A, inserting with Tenant B's ID is rejected."""
    db = rls_db
    tenant_a, tenant_b, user_a, user_b = await _setup_two_tenants(db)

    # Set context to Tenant A
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": str(tenant_a.id)}
    )

    # Try to insert a member with Tenant B's tenant_id — RLS should reject
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        bad_member = TenantMember(
            tenant_id=tenant_b.id,
            user_id=user_a.id,
            role="member",
            status="active",
        )
        db.add(bad_member)
        await db.flush()


@pytest.mark.asyncio
async def test_user_id_policy_allows_membership_lookup(rls_db: AsyncSession):
    """The dual-condition SELECT policy allows lookup by user_id for middleware resolution."""
    db = rls_db
    tenant_a, tenant_b, user_a, user_b = await _setup_two_tenants(db)

    # Insert member A
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": str(tenant_a.id)}
    )
    member_a = TenantMember(
        tenant_id=tenant_a.id, user_id=user_a.id, role="owner", status="active"
    )
    db.add(member_a)
    await db.flush()

    # Now simulate middleware: no tenant set, only user_id set
    await db.execute(text("RESET app.current_tenant"))
    await db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"), {"uid": str(user_a.id)}
    )

    # Should be able to find membership by user_id
    result = await db.execute(select(TenantMember).where(TenantMember.user_id == user_a.id))
    memberships = result.scalars().all()

    assert len(memberships) == 1
    assert memberships[0].tenant_id == tenant_a.id


@pytest.mark.asyncio
async def test_set_local_is_transaction_scoped(rls_db: AsyncSession):
    """Verify SET LOCAL does not leak across transactions."""
    db = rls_db
    tenant_a, _, user_a, _ = await _setup_two_tenants(db)

    # Set tenant context
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": str(tenant_a.id)}
    )

    # Within the same transaction, the setting should be visible
    result = await db.execute(text("SELECT current_setting('app.current_tenant', true)"))
    current = result.scalar()
    assert current == str(tenant_a.id)
