"""Customer linking service — find-or-create dedup by email then phone."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().lower()
    return stripped or None


def _normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


async def _find_by_email(db: AsyncSession, tenant_id: uuid.UUID, email: str) -> Customer | None:
    result = await db.execute(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.email == email)
    )
    return result.scalar_one_or_none()


async def _find_by_phone(db: AsyncSession, tenant_id: uuid.UUID, phone: str) -> Customer | None:
    result = await db.execute(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.phone == phone)
    )
    return result.scalar_one_or_none()


async def find_or_create_customer(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str | None,
    phone: str | None,
    email: str | None,
) -> Customer | None:
    """Find an existing customer by email (then phone) within the tenant, or create one.

    Returns None when no contact info is provided — never creates contactless
    customers (prevents POS "Walk-in" duplicates). When email and phone match
    different customers, email wins (no merge, no update). Runs inside the
    caller's transaction: never commits, never rolls back the outer transaction.
    """
    norm_email = _normalize_email(email)
    norm_phone = _normalize_phone(phone)
    norm_name = (name or "").strip()

    if norm_email is None and norm_phone is None:
        return None

    if norm_email is not None:
        existing = await _find_by_email(db, tenant_id, norm_email)
        if existing is not None:
            return existing

    if norm_phone is not None:
        existing = await _find_by_phone(db, tenant_id, norm_phone)
        if existing is not None:
            return existing

    fallback_name = norm_name or norm_email or norm_phone or "Customer"

    try:
        async with db.begin_nested():
            customer = Customer(
                tenant_id=tenant_id,
                name=fallback_name,
                phone=norm_phone,
                email=norm_email,
            )
            db.add(customer)
            await db.flush()
        return customer
    except IntegrityError:
        # Concurrent insert won the race; the SAVEPOINT rolled back (outer tx intact).
        # Re-query by the same precedence and return the existing row.
        if norm_email is not None:
            existing = await _find_by_email(db, tenant_id, norm_email)
            if existing is not None:
                return existing
        if norm_phone is not None:
            existing = await _find_by_phone(db, tenant_id, norm_phone)
            if existing is not None:
                return existing
        raise
