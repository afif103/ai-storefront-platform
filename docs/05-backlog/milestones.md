# Milestones

## Overview
MVP is split into 9 milestones (M1–M9), ordered by dependency. Each milestone has a target duration and dependency chain. See `backlog-v1.md` for detailed tasks within each milestone.

---

## Milestone Map

```
M1 Auth & Tenancy ──────┐
                         ├──▶ M2 Storefront ──┐
                         │                     ├──▶ M3 Structured Capture ──┐
                         │                     │                            │
                         │                     └──▶ M4 AI Assistant ────────┤
                         │                                                  │
                         └─────────────────────────────────────────────────▶│
                                                                            ▼
                                                           M5 Attribution & Dashboard
                                                                            │
                                                                            ▼
                                                                   M6 Admin Panel
                                                                            │
                                                                            ▼
                                                              M7 Notifications
                                                                            │
                                                                            ▼
                                                         M8 Infrastructure & DevOps
                                                                            │
                                                                            ▼
                                                       M9 Hardening & Launch Prep
```

Note: M8 (Infra) work starts in parallel with M1 (Docker Compose, CI skeleton). The dependency arrow means "must be feature-complete before the next milestone's features are testable end-to-end."

---

## Milestone Details

### M1 — Auth & Tenancy
**Priority**: P0 (everything depends on this)
**Target**: 2 weeks
**Dependencies**: None (first milestone)

| Acceptance Criteria |
|---------------------|
| User can sign up, verify email, log in via custom Next.js pages + Cognito |
| JWT access token verified in FastAPI middleware |
| `cognito_sub` → `users` → `tenant_members` → `tenant_id` chain works |
| `SET LOCAL app.current_tenant` executes on every authenticated request |
| RLS policies active on `tenant_members` and verified via cross-tenant test |
| Owner can invite members by email; invited user can accept and join |
| MFA setup flow works for Owner/Admin |

---

### M2 — Storefront & Catalog
**Priority**: P0
**Target**: 2 weeks
**Dependencies**: M1

| Acceptance Criteria |
|---------------------|
| Tenant can configure storefront (name, slug, logo, colours) |
| Public storefront loads at `https://{slug}.yourdomain.com` |
| Catalog items (product/service/project) CRUD works |
| Media upload via presigned URL (S3 `{tenant_id}/` prefix) |
| Multiple images per catalog item via `media_assets` |
| UTM params captured on storefront visit |

---

### M3 — Structured Capture
**Priority**: P0
**Target**: 2 weeks
**Dependencies**: M2

| Acceptance Criteria |
|---------------------|
| Public order submission → creates order with `pending` status |
| Public donation submission → creates donation with amount in KWD `NUMERIC(12,3)` |
| Public pledge submission → creates pledge with target date |
| Admin can transition order/donation/pledge through status workflow |
| Invalid status transitions rejected |
| Order numbers unique per tenant (auto-generated) |
| `visit_id` links to visit record for attribution |

---

### M4 — AI Assistant
**Priority**: P1
**Target**: 2 weeks
**Dependencies**: M2 (needs catalog for system prompt)

| Acceptance Criteria |
|---------------------|
| Chat widget on storefront sends messages to AI gateway |
| AI gateway checks Redis quota before provider call |
| Provider failure → Redis rollback, no usage logged |
| Successful call → usage logged to `ai_usage_log` with correct tokens and cost |
| Soft limit → notification to tenant owner (deduped per month) |
| Hard limit → 429 with user-friendly message |
| Per-session rate limit (10 messages / 5 min) enforced |
| System prompt includes tenant name + cached catalog summary |

---

### M5 — Attribution & Dashboard (Analytics/Funnel)
**Priority**: P1
**Target**: 2 weeks
**Dependencies**: M3 (needs orders/donations data), M4 (needs AI usage data + storefront chat events)

| Acceptance Criteria |
|---------------------|
| Tenant dashboard shows: orders/donations/pledges count + totals (KWD) |
| Conversion rate displayed (visits → orders) |
| Conversions broken down by UTM source/campaign |
| AI usage dashboard shows tokens used + cost (USD) per month |
| Data matches reality (manual DB count matches dashboard) |
| Event-based funnel analytics: storefront_view → product_view → add_to_cart → begin_checkout → submit_order/donation/pledge |
| Public batch ingest endpoint accepts storefront events (rate-limited, deduped) |
| Attribution via UTM params + referrer tracked per session |
| Dashboard analytics summary endpoint returns funnel conversion rates + daily series |
| Analytics page on dashboard consumes summary API (KPI cards + funnel chart) |
| RLS verified: public can insert analytics only (no reads); tenant can read own data only |
| Storefront instrumentation tracks view/product/cart/checkout/submit + chat open/message events |

---

### M5b — Inventory / Stock v1
**Priority**: P1
**Target**: 1 week
**Dependencies**: M3 (needs products + orders)

| Acceptance Criteria |
|---------------------|
| Products have `track_inventory` (bool) and `stock_qty` (int, CHECK >= 0) fields |
| Dashboard product create/edit supports setting inventory fields |
| Order submit atomically decrements stock (`UPDATE ... WHERE stock_qty >= :qty`) |
| Insufficient stock returns 409 Conflict (entire order rolled back) |
| Products with `track_inventory=false` skip stock checks (unlimited) |
| Public product list exposes `in_stock` boolean |
| Storefront disables "Add to Cart" when out of stock |
| Checkout shows clear error on 409 (out of stock) |
| Integration tests: buy→stock decrements, second buy on zero stock→409 |

---

### M5c — Inventory Movements & Stock Ops (Packet 1: Foundation + Cancel Restore)
**Priority**: P1
**Target**: 0.5 week
**Dependencies**: M5b

| Acceptance Criteria |
|---------------------|
| `stock_movements` table tracks all inventory changes (product_id, delta_qty, reason, note, order_id, actor_user_id) |
| Reason codes: `manual_restock`, `manual_adjustment`, `order_cancel_restore` |
| RLS policies on `stock_movements` (tenant-scoped SELECT + INSERT) |
| Unique partial index prevents double-restore per order+product |
| Order cancel restores stock for tracked-inventory items only |
| Cancel restore is idempotent (code check + DB unique index) |
| `record_stock_movement()` service inserts movement + atomically updates stock_qty |
| Integration tests: cancel restores tracked, skips untracked, no double-restore, mixed order, movement rows correct |
| **Packet 2:** `POST /products/{id}/restock` — positive qty, optional note, tracked-inventory only |
| **Packet 2:** `GET /products/{id}/stock-movements` — cursor-paginated history, newest-first |
| **Packet 2:** Dashboard restock form + movement history table on product edit page |
| **Packet 2:** Integration tests: restock happy path, rejects untracked, rejects bad qty, history correctness |
| **Packet 3:** Per-product `low_stock_threshold` column (default 5, 0/NULL = disabled) |
| **Packet 3:** Backend computed `is_low_stock` in product response (excludes out-of-stock and untracked) |
| **Packet 3:** Dashboard products list: amber low-stock badge + "All" / "Low stock only" frontend filter |
| **Packet 3:** Product create/edit UI: low-stock threshold input field |
| **Packet 3:** Integration tests: 7 tests covering threshold logic edge cases |
| **Packet 4:** Frontend-generated CSV export from analytics summary (KPI + funnel + daily series) |
| **Packet 4:** "Export CSV" button on analytics dashboard, disabled when loading/empty, filename includes preset + date |

---

### M6 — Admin Panel
**Priority**: P1
**Target**: 1.5 weeks
**Dependencies**: M5

| Acceptance Criteria | Packet | Status |
|---------------------|--------|--------|
| `is_platform_admin` flag on users table (manual DB assignment) | P1 | **DONE** |
| `require_platform_admin` auth guard returns 403 for non-admins | P1 | **DONE** |
| Platform admin can list all tenants with member count | P1 | **DONE** |
| Platform admin can suspend/reactivate a tenant (audit events written) | P1 | **DONE** |
| Suspended tenant: API returns 403 on all tenant-scoped routes | P1 | **DONE** |
| Suspended tenant: storefront returns 404 (existing `get_db_with_slug` behavior) | P1 | **DONE** |
| Platform admin RLS policy on tenant_members (SELECT-only, production-safe) | P1 | **DONE** |
| 13 integration tests (10 superuser + 3 RLS) all pass | P1 | **DONE** |
| Tenant admin can change member roles (owner only, last-owner protected, audit event) | P2 | **DONE** |
| Tenant admin can export orders/donations/pledges as CSV (date-filtered, RLS-isolated) | P2 | **DONE** |
| List + export queries use defense-in-depth tenant_id filter | P2 | **DONE** |
| 13 integration tests (7 role change + 6 CSV export) all pass | P2 | **DONE** |
| Platform admin SELECT RLS policies on orders/donations/pledges (production-correct) | P3 | **DONE** |
| Admin tenant list includes usage summary (order/donation/pledge counts, last_activity_at) | P3 | **DONE** |
| 3 integration tests (superuser with-data + empty, RLS-validated) all pass | P3 | **DONE** |
| Super admin tenant list page with usage summary, suspend/reactivate actions | P4 | **DONE** |
| Dashboard home link card to admin tenants page | P4 | **DONE** |
| Tenant admin UI (Next.js): team management, export buttons | P5+ | |

---

### M7 — Notifications
**Priority**: P2
**Target**: 1 week
**Dependencies**: M3 (needs orders/donations to notify about)

| Acceptance Criteria | Packet | Status |
|---------------------|--------|--------|
| `notification_preferences` table with RLS (tenant-scoped, per data-model.md) | P1 | **DONE** |
| `GET /tenants/me/notification-preferences` returns preferences (auto-creates default row) | P1 | **DONE** |
| `PUT /tenants/me/notification-preferences` updates email/telegram toggles + chat ID (admin/owner only) | P1 | **DONE** |
| Member can GET but cannot PUT preferences (role guard) | P1 | **DONE** |
| Cross-tenant isolation test passes on notification_preferences | P1 | **DONE** |
| Integration tests for preferences CRUD + RLS + role guard | P1 | **DONE** |
| Email notification service (SES + dev-mode log fallback) | P2 | **DONE** |
| Telegram notification service (Bot API HTTP + env-var token) | P2 | **DONE** |
| Celery tasks for order + donation email/Telegram notifications | P2 | **DONE** |
| Integration tests for notification services (mocked providers) | P2 | **DONE** |
| Order creation dispatches notification Celery task (fire-and-forget after commit) | P3 | |
| Donation creation dispatches notification Celery task | P3 | |
| Dispatch integration tests (verify task enqueued) | P3 | |
| Donation receipt email to donor (when receipt_requested=true) | P4+ | |
| Pledge due-soon periodic Telegram reminder (Celery Beat) | P4+ | |
| AI soft-limit notification wiring (ADR-0004) | P4+ | |
| Frontend notification preferences UI | P4+ | |
| SES sending identity + DKIM configured (Kimi) | P4+ | |

---

### M8 — Infrastructure & DevOps
**Priority**: P0 (starts in parallel with M1)
**Target**: 2 weeks (spread across M1–M7)
**Dependencies**: None (runs in parallel)

| Acceptance Criteria |
|---------------------|
| Docker Compose works for full local dev stack |
| GitHub Actions CI: test → lint → build → push ECR |
| ECS Fargate services running in `me-south-1` (backend + worker) |
| RDS, ElastiCache, S3 provisioned with security settings per `aws-deployment.md` |
| Vercel deployment with wildcard subdomain |
| Alembic migrations run in CI before deploy |
| CloudWatch log groups and basic alarms configured |

---

### M9 — Hardening & Launch Prep
**Priority**: P1
**Target**: 1.5 weeks
**Dependencies**: M1–M8 complete

| Acceptance Criteria |
|---------------------|
| Rate limiting active (per-IP, per-tenant, auth endpoints) |
| QA checklist passed (see `qa-checklist.md`) |
| OWASP top-10 spot check passed (SQL injection, XSS, CSRF on refresh) |
| Structured JSON logging verified in CloudWatch |
| Health checks and alarms functional |
| Seed data script works for demo |
| Smoke test suite passes end-to-end |
| Runbook and incident response docs reviewed |

---

## Timeline Summary

| Milestone | Target Duration | Cumulative |
|-----------|----------------|------------|
| M1 Auth & Tenancy | 2 weeks | Week 2 |
| M2 Storefront | 2 weeks | Week 4 |
| M3 Structured Capture | 2 weeks | Week 6 |
| M4 AI Assistant | 2 weeks | Week 8 |
| M5 Attribution & Dashboard | 2 weeks | Week 10 |
| M5b Inventory / Stock v1 | 1 week | Week 11 |
| M5c Inv Movements (P1) | 0.5 week | Week 11.5 |
| M6 Admin Panel | 1.5 weeks | Week 13 |
| M7 Notifications | 1 week | Week 13.5 |
| M8 Infra (parallel) | — | — |
| M9 Hardening | 1.5 weeks | Week 15 |

**Estimated MVP delivery: ~15 weeks** (with M8 infra running in parallel throughout).
