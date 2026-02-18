# ADR-0002: Multi-Tenancy via Row-Level Security

**Status**: Accepted
**Date**: 2026-02-17
**Deciders**: Rami (product owner), ChatGPT (brain/reviewer), Claude (implementor)

## Context
We need tenant data isolation for a multi-tenant SaaS platform. Tenants include Kuwait SMBs and charity/masjid projects storing orders, donations, pledges, and customer data. A data leak between tenants is a non-negotiable zero-tolerance failure.

## Decision
**Shared database, shared schema with PostgreSQL Row-Level Security (RLS).**

- Every tenant-scoped table has `tenant_id UUID NOT NULL`.
- RLS policies enforce `tenant_id = current_setting('app.current_tenant')::uuid`.
- Middleware executes `SET LOCAL app.current_tenant = '<uuid>';` per transaction.
- `FORCE ROW LEVEL SECURITY` on all tenant-scoped tables (applies even to table owner).
- No RLS-bypass application role. Platform admin queries global tables or impersonates via `SET LOCAL`.
- Two DB roles only: `app_user` (RLS enforced) and `app_migrator` (migrations only, never in app).

See `docs/01-architecture/tenancy-rls.md` for full implementation details.

## Alternatives Considered

### Option A: Schema-per-tenant
| Pros | Cons |
|------|------|
| Strongest isolation (separate schemas) | Migration complexity: every schema change runs N times |
| Easy per-tenant backup/restore | Connection pooling is harder (one pool per schema or `SET search_path`) |
| | Doesn't scale past ~100 tenants without automation |
| | Operational overhead significantly higher for MVP |

### Option B: Database-per-tenant
| Pros | Cons |
|------|------|
| Strongest possible isolation | Extreme operational overhead (provisioning, migrations, monitoring per DB) |
| Per-tenant backup trivial | Cost: one RDS instance per tenant is not viable for SMB pricing |
| | Cross-tenant reporting impossible without federation |

### Option C: Application-level filtering (no RLS)
| Pros | Cons |
|------|------|
| Simplest to implement initially | Every query must include `WHERE tenant_id = :tid` — one miss = data leak |
| No Postgres-specific features needed | No database-level enforcement — bugs in app code bypass isolation |
| | Cannot guarantee isolation in code review alone |

## Why RLS (Option: Shared schema + RLS)
- **Database enforces isolation** — even buggy application code cannot leak data across tenants.
- **Single schema** — one Alembic migration runs once, applies to all tenants.
- **Connection pooling is straightforward** — all tenants share one pool; `SET LOCAL` is transaction-scoped and safe with poolers like PgBouncer (transaction mode).
- **Scales to thousands of tenants** with no operational change.
- **Tradeoff accepted**: slightly more complex initial setup (RLS policies per table, `FORCE ROW LEVEL SECURITY`, migration checklist). This is a one-time cost that pays off permanently.

## Consequences
- Every new tenant-scoped table requires the RLS checklist (see `tenancy-rls.md`).
- `SET LOCAL` must be used (not `SET`) to prevent leakage across pooled connections.
- Global tables (`users`, `tenants`, `plans`) have no RLS and must never be exposed to tenant endpoints without filtering through `tenant_members`.
- Integration tests must verify cross-tenant isolation for every tenant-scoped table.
- `SECURITY DEFINER` functions are banned without explicit ADR approval.
