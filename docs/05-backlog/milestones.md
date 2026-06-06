# Milestones

## Overview
V1 (MVP) is split into 9 milestones (M1–M9), ordered by dependency. V2 adds 4 milestones (M10–M13) covering POS / omnichannel and merchant-ready upgrades as two parallel tracks. See `backlog-v1.md` for detailed tasks within each milestone.

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

## V2 Milestone Map

V2 runs two parallel tracks: **POS / Omnichannel** (M10B → M11–M13 POS packets) and **Merchant-Ready Core** (M10A → M11–M13 core packets). Both tracks converge in M13 for unified reporting.

```
M10A Auth/Onboarding ───────────┐
  (real auth, self-serve         │
   onboarding)                   │
                                 ├──▶ M11 Selling & Payments MVP ──▶ M12 Operations ──▶ M13 Reporting
                                 │      (POS sell screen, cash,        & Variants          & Polish
M10B POS Foundation ────────────┘       receipts, inventory,
  (cashier role, pos_sales               payment config,
   domain)                               customers table)
```

Note: M10A and M10B start with planning-only packets (M10A.1, M10B.1) before any implementation. Both planning packets can run in parallel. `customers` table ships in M11 and does not block POS MVP.

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
| Order creation dispatches notification Celery task (fire-and-forget after commit) | P3 | **DONE** |
| Donation creation dispatches notification Celery task | P3 | **DONE** |
| Dispatch integration tests (verify task enqueued) | P3 | **DONE** |
| Donation receipt email to donor (when receipt_requested=true) | P4 | **DONE** |
| Donation receipt integration tests (template + task + dispatch + resilience) | P4 | **DONE** |
| Pledge due-soon periodic Telegram reminder (Celery Beat) | P5+ | |
| AI soft-limit notification wiring (ADR-0004) | P5+ | |
| Frontend notification preferences UI | P5+ | |
| SES sending identity + DKIM configured (Kimi) | P5+ | |

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

### M10A — Foundations: Auth & Onboarding
**Priority**: P0
**Dependencies**: V1 complete (M1–M9)

| Acceptance Criteria |
|---------------------|
| Real auth replaces mock mode (signup, login, email verification; MFA optional later) |
| Self-serve tenant onboarding: signup → create store → configure storefront |
| Role matrix covers owner / admin / member / cashier with clear permission boundaries |
| Existing dev/demo data migrated or test fixtures updated for real auth |

**Status**: User-facing M10A scope shipped; follow-up internal tasks remain.
- Shipped: login, signup, verify-email, forgot/reset-password, invitation accept, create-store onboarding
- Remaining: 10A.1c role matrix review, 10A.2b test fixture migration

---

### M10B — Foundations: POS Domain
**Priority**: P0
**Dependencies**: V1 complete (M1–M9)

| Acceptance Criteria |
|---------------------|
| Cashier role added to role system with scoped permissions (sell-only, no settings access) |
| `pos_sales` + `pos_sale_items` tables with RLS, separate from online `orders` |
| POS sales service layer (create sale, calculate totals) |
| POS domain does NOT depend on `order_items` normalization — online orders keep current JSONB storage |

**Status**: M10B.7 POS order cancel for cashier shipped.
- M10B.1: POS planning memo accepted
- M10B.2: shared order service, `source` column, POS order endpoint, frontend cashier page
- M10B.3: cashier role at hierarchy level 0, backend allow/deny by hierarchy, invite/update schemas, frontend nav scoping + redirect. No new endpoint added — role sourced from existing bootstrap memberships.
- M10B.4: `customer_name` added to `OrderCreateResponse`. Frontend receipt with store name, order number, date/time, customer name, line items, total, print button. Dashboard shell print-specific layout tweaks. No new endpoints or tables.
- M10B.5: `GET /pos/orders` (cursor-paginated, `source='pos'`, tenant-scoped, cashier role) and `GET /pos/orders/{id}` (404 for non-POS/cross-tenant misses). Frontend POS history view with receipt reprint via existing receipt screen. No new tables or migrations.
- M10B.6: `pos_sale` reason added to `ck_stock_movements_reason` (reversible migration + model update). `record_stock_movement` extended with `prevent_negative_stock`. POS order creation writes `StockMovement(reason='pos_sale', delta_qty=-qty, order_id, actor_user_id)`. Storefront stock path unchanged. No new tables.
- M10B.7: `PATCH /pos/orders/{id}/cancel` (cashier role, `source='pos'`, `fulfilled→cancelled`, 409 guards, stock restore, audit event). Frontend cancel action on receipt with confirmation, cancelled badge, print preserved. No new tables or migrations.
- Deferred: POS Sales Domain (`pos_sales` + `pos_sale_items` tables, separate POS sales service/tests) moved to a later POS packet. Current POS orders use shared `orders` table with `source='pos'`.

---

### M11 — Selling & Payments MVP
**Priority**: P0
**Dependencies**: M10A + M10B

| Acceptance Criteria |
|---------------------|
| POS sell screen: product grid/search → cart → cash checkout (inside dashboard auth) |
| POS cash payment: tendered amount → change calculation |
| POS receipt: print-friendly HTML layout (thermal-friendly CSS) |
| POS inventory: sale decrements shared `stock_qty` via `record_stock_movement()` |
| Product catalog supports SKU/barcode field for POS lookup |
| Payment method config per tenant (cash, bank transfer, manual external, gateway placeholder) |
| Payment status tracking on online orders |
| Receipt generation for online orders (HTML, print button) |
| Shared customer records foundation across channels (does not block first POS MVP) |
| Customer linking on order/donation/POS sale create with dedup by phone/email |

**Status**: M11 complete. M11.8 customer linking shipped (orders + donations link/create customers via shared `find_or_create_customer`, email-first then phone dedup, POS no-op, `customer_id` exposed on order create/detail and donation create; pledges not linked); M11.7 customer records foundation shipped; M11.6b receipt generation shipped; M11.6a payment status deferred; M11.5 payment method config shipped; M11.4 SKU/barcode shipped; M11.1–M11.3 shipped via M10B. Dedicated SKU/barcode backend tests remain follow-up.

---

### M12 — Operations & Variants
**Priority**: P1
**Dependencies**: M11

| Acceptance Criteria |
|---------------------|
| Product variants (size/color) with per-variant stock tracking |
| Variant UI on dashboard product edit, storefront selector, POS variant picker |
| POS shift open/close with cash summary |
| POS void/cancel with stock restore via `record_stock_movement()` |
| Daily POS sales summary |
| Shipping/delivery module: methods, zones, fee calculation |
| Order fulfillment workflow: pack → ship → deliver status chain |
| Customer order history page |

**Status**: In progress. M12.1 product variants backend shipped — `product_variants` table + RLS + model, variant CRUD API, cross-table SKU/barcode uniqueness, `OrderItemRequest.variant_id` validation and snapshot, variant `price_amount` override (else inherit product price), variant stock decrement on storefront + POS, POS `StockMovement.variant_id`, and variant-aware cancel/restore; backend tests across all of it. M12.2 variant UI shipped (dashboard variant management, POS picker, public storefront selector, Arabic i18n); M12.2.1 POS variant visibility fix shipped. M12.3 POS shift management shipped (backend `cb6a3c0` + frontend `0f3c057`): `pos_shifts` table + RLS + one-open-shift-per-tenant partial-unique index, `orders.shift_id` FK/index, cashier-gated `GET /pos/shifts/current` / `POST /pos/shifts/open` / `POST /pos/shifts/close`, a hard backend gate requiring an open shift before a POS sale (else `409`) with the order associated via `shift_id`, a cash summary over this-shift `payment_method='cash'` and `status!='cancelled'` orders snapshotted into `closing_cash_sales` at close, and the POS shift banner/open-close forms/close summary/checkout gate (21 i18n keys; Arabic uses English fallback). M12.4 POS cancel reason shipped (backend `78654d8` + frontend `8d6d42a`): optional reason on the existing full-order cancel — nullable `orders.cancel_reason`, optional `{ reason }` body (trim/empty→null, no-body back-compat), mirrored into `AuditEvent.metadata_` and surfaced in the POS receipt/history, with an inline cancel-reason form on the receipt; stock-restore + shift cash-summary unchanged; partial line-item void/refund out of scope. M12.5a storefront delivery address foundation shipped (backend `90cfda1` + frontend `d2d4fc4`): nullable `orders.shipping_address`, optional/normalized request field, `OrderDetailResponse` exposure, `submit_order` threading, delivery notes via the existing `notes` field; checkout delivery address + notes textareas and dashboard order-detail display; POS/donations/pledges untouched. M12.5b shipping methods/fees shipped (backend `190a72c` + frontend `e0bcfbf`): `storefront_config.shipping` JSONB flat methods, active-only public exposure, server-resolved `shipping_method_id` (`422` on unknown/inactive/no-config), `total_amount = items_subtotal + shipping_fee`, persisted to `orders.shipping_fee` / `orders.shipping_method` with client fee never trusted, dashboard editor + checkout selector/fee/grand-total preview + receipt/order-detail display, 13 backend tests + 13 i18n keys. M12.6–M12.7 not started.

---

### M13 — Omnichannel Reporting & Polish
**Priority**: P1
**Dependencies**: M12

| Acceptance Criteria |
|---------------------|
| Unified sales reporting: online orders + POS sales in combined views |
| Revenue analytics by channel, product, time period |
| POS dashboard widgets: today's sales, top products |
| Customer repeat-purchase tracking |

---

## V1 Residue (tracked separately from V2)

The following V1 items are not started or partially complete. They are NOT success criteria for any V2 milestone and are tracked independently.

| Item | Source |
|------|--------|
| M6 P5+ — tenant admin team management UI | backlog-v1.md M6 |
| M7 P5+ — pledge reminders, AI soft-limit notification, notification prefs UI, SES DKIM | backlog-v1.md M7 |
| M8.9–8.13 — ALB/CF completion, CD pipeline, CloudWatch, Secrets Manager | backlog-v1.md M8 |
| M9 — hardening & launch prep | backlog-v1.md M9 |
| Bilingual Track D — admin pages, RTL, hero text Arabic | backlog-v1.md B Track D |
| Inventory UX consolidation (direct stock_qty edit bypass) | backlog-v1.md M5c tech debt |

---

## Timeline Summary

### V1 (MVP)

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

### V2 (POS + Merchant-Ready)

| Milestone | Track | Status |
|-----------|-------|--------|
| M10A — Foundations: Auth & Onboarding | Merchant-Ready Core | M10A.1 Planning next |
| M10B — Foundations: POS Domain | POS / Omnichannel | M10B.7 POS order cancel shipped |
| M11 — Selling & Payments MVP | Both tracks | Complete — M11.8 customer linking shipped; M11.7 customer records foundation shipped; M11.6b receipt generation shipped; M11.5 payment method config shipped; M11.4 SKU/barcode shipped; M11.1–M11.3 shipped via M10B; M11.6a deferred |
| M12 — Operations & Variants | Both tracks | In progress — M12.1 product variants backend shipped (schema/CRUD/order + inventory wiring, backend only); M12.2 variant UI (dashboard/POS/storefront + Arabic i18n) + M12.2.1 POS visibility fix shipped; M12.3 POS shift management shipped (backend + frontend); M12.4 POS cancel reason shipped (backend + frontend); M12.5a delivery address foundation shipped (backend + frontend); M12.5b shipping methods/fees shipped (backend + frontend); M12.6–M12.7 not started |
| M13 — Omnichannel Reporting & Polish | Both tracks (convergence) | Not started |

M10A and M10B can run in parallel. Both start with planning-only packets before implementation.
