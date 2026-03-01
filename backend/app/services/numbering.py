"""Tenant-scoped auto-numbering for orders, donations, and pledges.

Uses PostgreSQL advisory transaction locks to guarantee race-safe,
gap-free numbering per tenant per prefix.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_PREFIXES = {
    "ORD": ("orders", "order_number"),
    "DON": ("donations", "donation_number"),
    "PLG": ("pledges", "pledge_number"),
}


async def _next_number(
    db: AsyncSession,
    tenant_id: str,
    prefix: str,
) -> str:
    """Generate the next sequential number for a given prefix and tenant.

    Uses pg_advisory_xact_lock (transaction-scoped) so concurrent callers
    on the same tenant+prefix serialise safely.  The lock is released
    automatically when the surrounding transaction commits or rolls back.
    """
    table, column = _PREFIXES[prefix]

    # Acquire advisory lock scoped to this tenant+prefix combination.
    lock_key = f"{tenant_id}:{prefix}"
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": lock_key},
    )

    # Find the highest existing number for this tenant.
    # The column stores values like "ORD-00042", so we strip the prefix,
    # cast to integer, and take the max.
    row = await db.execute(
        text(
            f"SELECT MAX(CAST(SUBSTRING({column} FROM :pattern) AS INTEGER)) "
            f"FROM {table} "
            f"WHERE tenant_id = :tid"
        ),
        {"pattern": f"{prefix}-([0-9]+)", "tid": tenant_id},
    )
    current_max = row.scalar()
    next_seq = (current_max or 0) + 1
    return f"{prefix}-{next_seq:05d}"


async def get_next_order_number(db: AsyncSession, tenant_id: str) -> str:
    """Return the next order number, e.g. 'ORD-00001'."""
    return await _next_number(db, tenant_id, "ORD")


async def get_next_donation_number(db: AsyncSession, tenant_id: str) -> str:
    """Return the next donation number, e.g. 'DON-00001'."""
    return await _next_number(db, tenant_id, "DON")


async def get_next_pledge_number(db: AsyncSession, tenant_id: str) -> str:
    """Return the next pledge number, e.g. 'PLG-00001'."""
    return await _next_number(db, tenant_id, "PLG")
