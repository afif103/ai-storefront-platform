# Tenancy & Row-Level Security (RLS)

## Overview
Every tenant's data is isolated at the PostgreSQL level using Row-Level Security. There is no application-level filtering — the database enforces isolation so even a bug in application code cannot leak data across tenants.

## How It Works

### 1. Tenant ID Propagation

```
Request → Cognito JWT → Backend middleware → resolve user → resolve tenant_id
  → DB session: SET LOCAL app.current_tenant = '<tenant-uuid>';
  → All queries in this transaction are RLS-filtered
  → Transaction commits → setting is gone (SET LOCAL is transaction-scoped)
```

The middleware (`app/core/middleware/tenant.py`) runs on every authenticated request:

```python
# Pseudocode — actual implementation in app/core/middleware/tenant.py
async def tenant_middleware(request, call_next):
    user = await get_current_user(request)          # from Cognito JWT sub
    tenant_id = await resolve_tenant(user)           # from tenant_members table

    async with db.session() as session:
        await session.execute(
            text("SET LOCAL app.current_tenant = :tid"),
            {"tid": str(tenant_id)}
        )
        request.state.db = session
        request.state.tenant_id = tenant_id
        response = await call_next(request)

    return response
```

### 2. RLS Policy Pattern

Applied to every tenant-scoped table:

```sql
-- Enable RLS on the table
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owner (prevents bypass)
ALTER TABLE orders FORCE ROW LEVEL SECURITY;

-- Policy: rows visible only when tenant_id matches session variable
CREATE POLICY tenant_isolation ON orders
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Separate INSERT policy to ensure new rows get correct tenant_id
CREATE POLICY tenant_insert ON orders
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);
```

### 3. Database Roles

| Role | Purpose | RLS applies? |
|------|---------|-------------|
| `app_user` | Used by FastAPI backend for all queries (tenant-scoped and platform admin) | Yes |
| `app_migrator` | Used by Alembic for schema migrations only. Never exposed to the application. | No (superuser) |

There is **no RLS-bypass application role**. Platform admin endpoints work in two ways:

- **Global tables** (`tenants`, `plans`, `users`): these tables have no RLS policies, so `app_user` can query them directly. Access is gated by role check in middleware (super-admin only).
- **Viewing a specific tenant's data**: the admin endpoint sets `SET LOCAL app.current_tenant = '<selected-tenant-uuid>'` to impersonate the tenant. RLS still enforces isolation — the admin sees exactly one tenant at a time, never all tenants in a single query.

This eliminates the risk of an RLS-bypass role being accidentally used in tenant-facing code paths.

### 4. Tenant-Scoped Tables

Every table holding tenant data MUST have:

```sql
tenant_id UUID NOT NULL REFERENCES tenants(id),
```

Tables that are tenant-scoped (non-exhaustive):
- `tenant_members`, `products`, `orders`, `order_items`
- `donations`, `pledges`, `campaigns`
- `storefront_config`, `notification_preferences`
- `ai_conversations`, `ai_usage_log`
- `visits`, `utm_events`

Tables that are global (no `tenant_id`, no RLS):
- `tenants` (the tenants table itself)
- `users` (a user can belong to multiple tenants via `tenant_members`)
- `plans` / `subscription_tiers` (global config)

### 5. SQLAlchemy Base Model

```python
class TenantScopedBase(Base):
    __abstract__ = True

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("tenants.id"), nullable=False, index=True
    )
```

All tenant-scoped models inherit from `TenantScopedBase` instead of `Base`.

## Safety Rules

1. **Never use `SECURITY DEFINER` functions** without an explicit ADR approval.
2. **No RLS-bypass application role.** Platform admin queries global tables directly or impersonates a tenant via `SET LOCAL`. There is no role that silently skips RLS.
3. **Always use `SET LOCAL`** (transaction-scoped), never `SET` (session-scoped) — prevents leakage if connection pooling reuses sessions.
4. **Always use `FORCE ROW LEVEL SECURITY`** — ensures RLS applies even if the connecting role owns the table.
5. **Global tables (e.g., `users`) must never be exposed to tenant-facing endpoints** unless joined through `tenant_members` filtered by the current tenant. A tenant must never see users outside their organisation.
6. **Test isolation explicitly**: integration tests must verify that Tenant A cannot see Tenant B's data even when querying the same table.

## Migration Checklist

When adding a new tenant-scoped table:

- [ ] Add `tenant_id UUID NOT NULL REFERENCES tenants(id)` column.
- [ ] Add index on `tenant_id`.
- [ ] `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;`
- [ ] `ALTER TABLE ... FORCE ROW LEVEL SECURITY;`
- [ ] Create `tenant_isolation` USING policy.
- [ ] Create `tenant_insert` WITH CHECK policy.
- [ ] Inherit from `TenantScopedBase` in the SQLAlchemy model.
- [ ] Add cross-tenant isolation test.
