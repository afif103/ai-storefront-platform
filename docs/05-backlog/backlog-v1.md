# Backlog v1

Ordered epics M1–M9. Each task has a suggested owner:
- **Claude**: AI-assisted implementation (code generation, migrations, boilerplate, tests).
- **Kimi**: manual work (design decisions, config, cloud provisioning, manual testing, copy).
- **Both**: collaborative tasks requiring human review of AI output.

---

## M1 — Auth & Tenancy

| # | Task | Owner | DoD |
|---|------|-------|-----|
| 1.1 | Create Cognito User Pool in `me-south-1` (password policy, MFA, app client) | Kimi | Pool exists, app client secret in Secrets Manager |
| 1.2 | Build custom Next.js auth pages (signup, login, forgot password, MFA setup) | Claude | Pages render, forms submit to Cognito, error handling works |
| 1.3 | Implement JWT verification middleware in FastAPI | Claude | Middleware verifies signature against JWKS, extracts `cognito_sub`, returns 401 on invalid/expired token |
| 1.4 | Create `users` and `tenants` tables + Alembic migration | Claude | Tables exist, indexes + constraints per `data-model.md` |
| 1.5 | Create `tenant_members` table with RLS policies | Claude | RLS enabled + forced, policies created, cross-tenant isolation test passes |
| 1.6 | Implement `cognito_sub` → user → tenant_id resolution in middleware | Claude | `SET LOCAL app.current_tenant` executes on every authenticated request |
| 1.7 | Implement tenant creation endpoint (`POST /tenants`) | Claude | Creates tenant + owner membership in one transaction, slug uniqueness enforced |
| 1.8 | Implement team invite flow (invite by email, accept invite) | Claude | Invite creates `tenant_members` row with status `invited`, accept flips to `active` |
| 1.9 | Implement token refresh endpoint (`POST /auth/refresh`) with hardening | Claude | Origin validation, Content-Type check, POST-only, httpOnly cookie handling per `security.md §1` |
| 1.10 | Write cross-tenant isolation integration tests | Claude | Tests prove Tenant A cannot read/write Tenant B's `tenant_members` data |
| 1.11 | Configure Cognito email verification + SES integration | Kimi | Signup → verification email arrives, user can verify and log in |

---

## M2 — Storefront & Catalog

| # | Task | Owner | DoD |
|---|------|-------|-----|
| 2.1 | Create `storefront_config` table + RLS + migration | Claude | Table with `UNIQUE(tenant_id)`, RLS policies, isolation test |
| 2.2 | Create `catalog_items` table + RLS + migration | Claude | Table with type discriminator (`TEXT+CHECK`), metadata JSONB, indexes per `data-model.md` |
| 2.3 | Create `media_assets` table + RLS + migration | Claude | Polymorphic media table, `entity_type` + `entity_id`, S3 key column |
| 2.4 | Implement storefront config API (GET/PUT) | Claude | Admin can read/update branding; logo stored in S3 under `{tenant_id}/` |
| 2.5 | Implement catalog CRUD API | Claude | Create, read, update, delete catalog items. Type validation. Cursor pagination. |
| 2.6 | Implement presigned URL upload/download endpoints | Claude | PUT URL for upload (max 10 MB, content-type check), GET URL for download (15-min expiry), tenant prefix validated |
| 2.7 | Build public storefront page (Next.js) | Claude | Renders at `https://{slug}.yourdomain.com` with tenant branding + catalog |
| 2.8 | Implement UTM capture on storefront visit | Claude | `POST /storefront/{slug}/visit` stores UTM params, returns `visit_id` |
| 2.9 | Configure Vercel wildcard subdomain routing | Kimi | `*.yourdomain.com` resolves to Vercel, slug extracted in Next.js middleware |
| 2.10 | Write catalog + storefront integration tests | Claude | CRUD works, presigned URLs valid, cross-tenant isolation holds |

---

## M3 — Structured Capture

| # | Task | Owner | DoD |
|---|------|-------|-----|
| 3.1 | Create `orders` table + RLS + migration | Claude | Status `TEXT+CHECK`, JSONB items, `UNIQUE(tenant_id, order_number)`, indexes |
| 3.2 | Create `donations` table + RLS + migration | Claude | Amount `NUMERIC(12,3)`, campaign field, receipt flag |
| 3.3 | Create `pledges` table + RLS + migration | Claude | Target date, `fulfilled_amount`, status workflow |
| 3.4 | Create `utm_events` table + RLS + migration | Claude | Links visits to conversion events |
| 3.5 | Implement public order submission endpoint | Claude | Validates items against catalog, calculates total, auto-generates order number, links UTM visit |
| 3.6 | Implement public donation submission endpoint | Claude | Validates amount (KWD `NUMERIC(12,3)`), stores campaign, receipt flag |
| 3.7 | Implement public pledge submission endpoint | Claude | Validates target date (must be future), stores amount |
| 3.8 | Implement admin status transition endpoints | Claude | PATCH updates status. Invalid transitions rejected (e.g., `fulfilled` → `pending`). Audit event logged. |
| 3.9 | Implement order number auto-generation | Claude | Sequential per tenant: `ORD-00001`, `DON-00001`, `PLG-00001`. Tenant-scoped uniqueness. |
| 3.10 | Write structured capture integration tests | Claude | All CRUD works, status transitions valid, cross-tenant isolation, UTM attribution linked |

---

## M4 — AI Assistant

| # | Task | Owner | Status | DoD |
|---|------|-------|--------|-----|
| 4.1 | Create `ai_conversations` + `ai_usage_log` tables + RLS + migrations | Claude | **DONE** | Tables per `data-model.md`, RLS policies, indexes |
| 4.2 | Implement AI gateway (`app/services/ai_gateway.py`) | Claude | **DONE** | Quota reserve → provider call → adjust/rollback → log. Two gateways: dashboard (`ai_gateway.py`, last 10 turns) + storefront (`storefront_ai_gateway.py`, last 6 turns). |
| 4.3 | Implement provider abstraction layer | Claude | **DONE** | `AIProvider` protocol + OpenAI (default) and Groq (fast/free). Configurable via `AI_PROVIDER` env. |
| 4.4 | Implement Redis quota check with reserve/rollback | Claude | **DONE** | INCRBY estimated → call → DECRBY on failure OR adjust delta on success. Integration test proves rollback. |
| 4.5 | Implement soft/hard limit logic + notification | Claude | Partial | Hard limit → 429. Soft limit notification not yet implemented. |
| 4.6 | Implement tenant system prompt builder | Claude | **DONE** | Builds prompt with tenant name + catalog summary. Dashboard: tenant-scoped ops summary. Storefront: product catalog (up to 50 items). |
| 4.7 | Build AI chat widget (Next.js storefront component) | Claude | **DONE** (M4.2) | Floating chat bubble on storefront pages. Session-based (`localStorage` key `session_id`, shared with `useVisit`). Rate limited: 10 msgs / 5 min per session. Read-only — no actions. |
| 4.8 | Implement conversation context management | Claude | **DONE** | Dashboard: last 10 turns from `ai_conversations.messages` JSONB. Storefront: last 6 turns from `storefront_ai_conversations.messages` JSONB. |
| 4.9 | Set up AI pricing config in SSM | Kimi | | `/{env}/ai/pricing` populated with provider pricing. `/{env}/ai/provider` set. |
| 4.10 | Write AI gateway integration tests | Claude | **DONE** | Quota enforcement, rollback on failure, usage logging, rate limiting. 10 tests (5 dashboard + 5 storefront). |

---

## M5 — Attribution & Dashboard (Analytics/Funnel)

| # | Task | Owner | DoD |
|---|------|-------|-----|
| 5.1 | Analytics DB schema: `attribution_visitors` / `attribution_sessions` / `attribution_events` tables + indexes | Claude | Alembic migration runs clean, indexes on tenant_id + occurred_at + event_name, reversible downgrade |
| 5.2 | RLS policies: public INSERT-only; tenant/admin SELECT requires authenticated user context | Claude | Public can insert analytics events, public cannot read. Tenant can read own data only. Cross-tenant isolation test passes. |
| 5.3 | Public batch ingest endpoint: `POST /api/v1/storefront/{slug}/analytics/events` (rate-limited) | Claude | Accepts visitor_id + session_id + utm/referrer + events array. Rate-limited per session+IP. Upserts visitor/session, inserts events. |
| 5.4 | Dedupe/spam guard v1: `storefront_view` once per 10 min per session | Claude | Duplicate `storefront_view` within 10-min window is skipped. Index-backed query. |
| 5.5 | Dashboard analytics summary endpoint: `GET /api/v1/tenants/me/analytics/summary` | Claude | Returns visitors, sessions, event counts, funnel conversion rates, daily series. Date range validated (max 180 days). |
| 5.6 | Dashboard UI Analytics page (KPI cards + funnel + optional daily series) | Claude | Next.js page consuming summary API. Responsive. Date range picker. |
| 5.7 | Storefront instrumentation (view/product/cart/checkout/submit + chat open/message) | Claude | `lib/analytics.ts` with visitor_id localStorage, session_id rolling expiry, batch flush to ingest endpoint. |
| 5.8 | Dashboard integration tests (RLS + correctness vs DB counts) | Claude | Happy path ingest, dedupe, invalid event rejection, RLS isolation, summary correctness. |
| 5.9 | _(Optional)_ CSV export (bounded date range, admin-only) | Claude | Export analytics events as CSV. Date range capped. RLS ensures tenant isolation. |

---

## M5b — Inventory / Stock v1

| # | Task | Owner | DoD |
|---|------|-------|-----|
| 5b.1 | Add `track_inventory` + `stock_qty` fields to products table + migration | Claude | Alembic migration adds columns with CHECK(stock_qty >= 0), reversible downgrade |
| 5b.2 | Update product create/edit schemas to accept inventory fields | Claude | ProductCreate/ProductUpdate include track_inventory + stock_qty. Validation: if track_inventory=true, stock_qty required. |
| 5b.3 | Enforce stock on order submit (atomic decrement, 409 on insufficient) | Claude | UPDATE ... WHERE stock_qty >= :qty. Rowcount 0 → 409. Entire order rolled back on any item failure. |
| 5b.4 | Expose `in_stock` in public product list | Claude | PublicProductResponse includes `in_stock: bool`. Computed from track_inventory + stock_qty. |
| 5b.5 | Storefront UI: disable Add to Cart when out of stock + checkout 409 error | Claude | Button shows "Out of Stock" (disabled). Checkout error on 409 displayed clearly. |
| 5b.6 | Integration tests: stock decrement, zero stock → 409, track_inventory=false bypass | Claude | Tests cover happy path, out-of-stock, and unlimited (track_inventory=false) scenarios. |

---

## M5c — Inventory Movements & Stock Ops

### Packet 1 — Foundation + Cancel Restore (shipped)

| # | Task | Owner | Status | DoD |
|---|------|-------|--------|-----|
| 5c.1 | Create `stock_movements` table + RLS + migration | Claude | **DONE** | Table with tenant_id, product_id, delta_qty, reason (CHECK), note, order_id, actor_user_id. RLS policies. Unique partial index on (order_id, product_id) WHERE reason = 'order_cancel_restore'. |
| 5c.2 | Create `StockMovement` ORM model | Claude | **DONE** | Model registered in `__init__.py`. FK to products (RESTRICT), orders, users. |
| 5c.3 | Create inventory service (`record_stock_movement` + `restore_stock_for_cancelled_order`) | Claude | **DONE** | Single code path for all stock movements. Atomic INSERT + UPDATE in same transaction. Idempotent cancel restore (code check + DB unique index). |
| 5c.4 | Wire cancel restore into order status transitions | Claude | **DONE** | Only triggers on true transition into `cancelled` from a prior state. Passes actor_user_id. |
| 5c.5 | Integration tests for cancel restore + movement audit | Claude | **DONE** | 5 tests: tracked restore, untracked skip, no double-restore, movement rows correct, mixed order. |

### Packet 2 — Dashboard Restock + Movement History (shipped)

| # | Task | Owner | Status | DoD |
|---|------|-------|--------|-----|
| 5c.6 | `POST /tenants/me/products/{id}/restock` endpoint | Claude | **DONE** | Positive qty only, optional note, tracked-inventory products only. Reuses `record_stock_movement(reason="manual_restock")`. Returns updated product. |
| 5c.7 | `GET /tenants/me/products/{id}/stock-movements` endpoint | Claude | **DONE** | Cursor-paginated, newest-first. Returns delta_qty, reason, note, order_id, actor_user_id, created_at. |
| 5c.8 | Dashboard restock UI on product edit page | Claude | **DONE** | Qty + note form, green Restock button. Only shown when track_inventory=true. Updates stock display on success. |
| 5c.9 | Dashboard movement history UI on product edit page | Claude | **DONE** | Table showing last 20 movements with reason label, signed delta, note, timestamp. Refreshes after restock. |
| 5c.10 | Integration tests for restock + history | Claude | **DONE** | 4 tests: restock increases stock + creates movement, rejects untracked, rejects zero/negative qty, history returns correct rows. |

**Tech debt:** Direct `stock_qty` edit via `PATCH /products/{id}` still bypasses movement trail. Not addressed in this packet.

---

## M6 — Admin Panel

| # | Task | Owner | DoD |
|---|------|-------|-----|
| 6.1 | Implement super admin tenant list endpoint | Claude | Lists all tenants with member count + usage summary. Limit/offset pagination. |
| 6.2 | Implement tenant suspend/reactivate endpoint | Claude | Sets `is_active` flag. Suspended tenant: storefront unavailable, API returns 403. Audit event. |
| 6.3 | Implement tenant team management endpoints | Claude | List members, change role (owner only), remove member (admin+). Cannot remove last owner. |
| 6.4 | Implement CSV export endpoint | Claude | Export orders/donations as CSV. RLS ensures tenant isolation. Streamed response for large datasets. |
| 6.5 | Build super admin UI (Next.js) | Claude | Tenant list, usage overview, suspend/reactivate actions |
| 6.6 | Build tenant admin UI (Next.js) | Claude | Team management, storefront config, export buttons |
| 6.7 | Write admin panel integration tests | Claude | Super admin CRUD, tenant admin CRUD, role enforcement, suspended tenant behaviour |

---

## M7 — Notifications

| # | Task | Owner | DoD |
|---|------|-------|-----|
| 7.1 | Create `notification_preferences` table + RLS + migration | Claude | `UNIQUE(tenant_id)`, `telegram_bot_token_ref` column (Secrets Manager key) |
| 7.2 | Implement notification preferences API (GET/PUT) | Claude | Admin can enable/disable email + Telegram. Bot token stored in Secrets Manager, not DB. |
| 7.3 | Implement email notification Celery tasks | Claude | Order confirmation, donation receipt, invite email via SES. Templated, tenant-branded. |
| 7.4 | Implement Telegram notification Celery tasks | Claude | Order received, donation received, pledge due soon. Bot token retrieved from Secrets Manager. |
| 7.5 | Implement notification dispatch on order/donation/pledge creation | Claude | After record created → dispatch Celery task if tenant has notifications enabled |
| 7.6 | Configure SES sending identity + DKIM | Kimi | Domain verified, DKIM configured, test email sends successfully |
| 7.7 | Write notification integration tests | Claude | Email sent when enabled, Telegram sent when enabled, nothing sent when disabled, async dispatch verified |

---

## M8 — Infrastructure & DevOps

| # | Task | Owner | DoD |
|---|------|-------|-----|
| 8.1 | Create Docker Compose for local dev (Postgres, Redis) | Claude | `docker compose up -d` starts all deps, health checks pass |
| 8.2 | Create Dockerfile for backend (multi-stage, slim) | Claude | Builds successfully, runs backend and worker via different entrypoints |
| 8.3 | Set up GitHub Actions CI (test + lint + build) | Claude | PR checks: pytest, ruff, black. Main branch: build + push ECR. |
| 8.4 | Provision VPC, subnets, security groups in `me-south-1` | Kimi | Per `aws-deployment.md` networking section |
| 8.5 | Provision RDS PostgreSQL (Multi-AZ, encryption, `require_ssl`) | Kimi | DB accessible from ECS tasks only, `app_user` + `app_migrator` roles created |
| 8.6 | Provision ElastiCache Redis (Multi-AZ, encryption in transit) | Kimi | Redis accessible from ECS tasks only |
| 8.7 | Provision S3 bucket (Block Public Access, versioning) | Kimi | Bucket exists with correct policy, lifecycle rules |
| 8.8 | Create ECR repository + ECS cluster + task definitions | Kimi | Backend + worker services running with correct task roles |
| 8.9 | Set up ALB + CloudFront + WAF | Kimi | HTTPS, health checks, WAF rules per `security.md §8` |
| 8.10 | Set up Vercel project with wildcard subdomain | Kimi | Frontend deploys on push, `*.yourdomain.com` resolves |
| 8.11 | Set up GitHub Actions CD (deploy to staging + production) | Claude | Staging auto-deploy on main. Production via manual workflow dispatch. |
| 8.12 | Set up CloudWatch log groups + alarms | Kimi | Log groups for backend/worker/audit. Alarms: CPU, connections, 5xx. |
| 8.13 | Populate Secrets Manager with all secrets | Kimi | All secrets per `security.md §3` table |

---

## M9 — Hardening & Launch Prep

| # | Task | Owner | DoD |
|---|------|-------|-----|
| 9.1 | Implement rate limiting middleware (Redis-based) | Claude | Per-IP, per-tenant, per-auth, per-AI session limits per `security.md §6`. Returns 429 + Retry-After. |
| 9.2 | OWASP top-10 spot check | Both | SQL injection, XSS, CORS, auth bypass — all tested and passing |
| 9.3 | Verify structured JSON logging in CloudWatch | Claude | All logs are JSON with `request_id`, `tenant_id`, `user_id`. No PII in logs. |
| 9.4 | Implement health check endpoint with DB + Redis checks | Claude | `GET /health` returns `{"status": "ok", "db": "ok", "redis": "ok"}` |
| 9.5 | Create seed data script for demo | Claude | Creates demo tenants, users, catalog, orders, donations. Idempotent. |
| 9.6 | Create smoke test suite | Claude | End-to-end: signup → create tenant → add catalog → place order → check dashboard. Runs in CI against staging. |
| 9.7 | Run full QA checklist on staging | Kimi | All items in `qa-checklist.md` pass |
| 9.8 | Review and finalise runbook + incident response docs | Both | Docs are accurate, commands work, team has reviewed |
| 9.9 | Performance baseline test | Both | P95 API latency < 300ms, storefront LCP < 2s, AI response < 5s |
| 9.10 | Security review: grep for secrets, tokens, PII in logs | Claude | Zero occurrences of plaintext secrets or PII in logs/code |

---

## Summary

| Milestone | Tasks | Claude | Kimi | Both |
|-----------|-------|--------|------|------|
| M1 Auth & Tenancy | 11 | 9 | 2 | 0 |
| M2 Storefront | 10 | 8 | 2 | 0 |
| M3 Structured Capture | 10 | 10 | 0 | 0 |
| M4 AI Assistant | 10 | 9 | 1 | 0 |
| M5 Attribution & Dashboard | 9 | 9 | 0 | 0 |
| M5b Inventory / Stock v1 | 6 | 6 | 0 | 0 |
| M6 Admin Panel | 7 | 7 | 0 | 0 |
| M7 Notifications | 7 | 6 | 1 | 0 |
| M8 Infra & DevOps | 13 | 4 | 9 | 0 |
| M9 Hardening | 10 | 6 | 1 | 3 |
| **Total** | **93** | **74** | **16** | **3** |
