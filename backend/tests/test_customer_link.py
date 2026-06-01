"""M11.8 find_or_create_customer service tests."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.tenant import Tenant
from app.services.customer_link import find_or_create_customer


async def _make_tenant(db: AsyncSession) -> uuid.UUID:
    tenant = Tenant(name="T", slug=f"link-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.flush()
    return tenant.id


async def _count_customers(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(Customer).where(Customer.tenant_id == tenant_id)
    )
    return result.scalar_one()


async def test_email_match_returns_existing(db: AsyncSession):
    tenant_id = await _make_tenant(db)
    first = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone=None, email="alice@example.com"
    )
    assert first is not None

    again = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Different", phone=None, email="alice@example.com"
    )
    assert again is not None
    assert again.id == first.id


async def test_phone_match_returns_existing(db: AsyncSession):
    tenant_id = await _make_tenant(db)
    first = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone="12345678", email=None
    )
    assert first is not None

    again = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Different", phone="12345678", email=None
    )
    assert again is not None
    assert again.id == first.id


async def test_both_match_same_customer_returns_that_customer(db: AsyncSession):
    tenant_id = await _make_tenant(db)
    first = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone="12345678", email="alice@example.com"
    )
    assert first is not None

    again = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone="12345678", email="alice@example.com"
    )
    assert again is not None
    assert again.id == first.id


async def test_email_and_phone_match_different_customers_email_wins(db: AsyncSession):
    tenant_id = await _make_tenant(db)
    by_email = await find_or_create_customer(
        db, tenant_id=tenant_id, name="EmailCust", phone=None, email="match@example.com"
    )
    by_phone = await find_or_create_customer(
        db, tenant_id=tenant_id, name="PhoneCust", phone="99998888", email=None
    )
    assert by_email is not None
    assert by_phone is not None
    assert by_email.id != by_phone.id

    # email points to by_email, phone points to by_phone -> email wins
    result = await find_or_create_customer(
        db, tenant_id=tenant_id, name="X", phone="99998888", email="match@example.com"
    )
    assert result is not None
    assert result.id == by_email.id


async def test_name_only_returns_none_and_creates_nothing(db: AsyncSession):
    tenant_id = await _make_tenant(db)
    before = await _count_customers(db, tenant_id)

    result = await find_or_create_customer(
        db, tenant_id=tenant_id, name="NoContact", phone=None, email=None
    )
    assert result is None

    after = await _count_customers(db, tenant_id)
    assert after == before


async def test_no_match_creates_customer(db: AsyncSession):
    tenant_id = await _make_tenant(db)
    before = await _count_customers(db, tenant_id)

    result = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone=None, email="new@example.com"
    )
    assert result is not None
    assert result.email == "new@example.com"

    after = await _count_customers(db, tenant_id)
    assert after == before + 1


async def test_same_contact_across_tenants_distinct(db: AsyncSession):
    tenant_a = await _make_tenant(db)
    tenant_b = await _make_tenant(db)

    cust_a = await find_or_create_customer(
        db, tenant_id=tenant_a, name="Alice", phone="12345678", email="shared@example.com"
    )
    cust_b = await find_or_create_customer(
        db, tenant_id=tenant_b, name="Alice", phone="12345678", email="shared@example.com"
    )
    assert cust_a is not None
    assert cust_b is not None
    assert cust_a.id != cust_b.id
    assert cust_a.tenant_id == tenant_a
    assert cust_b.tenant_id == tenant_b


async def test_idempotent_second_call_no_duplicate(db: AsyncSession):
    tenant_id = await _make_tenant(db)

    first = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone=None, email="dup@example.com"
    )
    count_after_first = await _count_customers(db, tenant_id)

    second = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone=None, email="dup@example.com"
    )
    count_after_second = await _count_customers(db, tenant_id)

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert count_after_first == count_after_second


async def test_email_normalization_matches_case_insensitively(db: AsyncSession):
    tenant_id = await _make_tenant(db)
    first = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone=None, email="alice@example.com"
    )
    assert first is not None

    again = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone=None, email="ALICE@EXAMPLE.COM"
    )
    assert again is not None
    assert again.id == first.id
    assert again.email == "alice@example.com"


async def test_phone_trim_normalization(db: AsyncSession):
    tenant_id = await _make_tenant(db)
    first = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone="12345678", email=None
    )
    assert first is not None

    again = await find_or_create_customer(
        db, tenant_id=tenant_id, name="Alice", phone="  12345678  ", email=None
    )
    assert again is not None
    assert again.id == first.id
