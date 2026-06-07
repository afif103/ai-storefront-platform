# Backlog (V1 + V2)

V1 (MVP): ordered epics M1–M9. V2 (POS + Merchant-Ready): M10–M13 with two parallel tracks. All implementation is through Claude Code.

---

## M1 — Auth & Tenancy

| # | Task | Primary Implementor | DoD |
|---|------|-------|-----|
| 1.1 | Create Cognito User Pool (password policy, MFA, app client) | Claude | Pool exists, app client secret in Secrets Manager |
| 1.2 | Build custom Next.js auth pages (signup, login, forgot password, MFA setup) | Claude | Pages render, forms submit to Cognito, error handling works |
| 1.3 | Implement JWT verification middleware in FastAPI | Claude | Middleware verifies signature against JWKS, extracts `cognito_sub`, returns 401 on invalid/expired token |
| 1.4 | Create `users` and `tenants` tables + Alembic migration | Claude | Tables exist, indexes + constraints per `data-model.md` |
| 1.5 | Create `tenant_members` table with RLS policies | Claude | RLS enabled + forced, policies created, cross-tenant isolation test passes |
| 1.6 | Implement `cognito_sub` → user → tenant_id resolution in middleware | Claude | `SET LOCAL app.current_tenant` executes on every authenticated request |
| 1.7 | Implement tenant creation endpoint (`POST /tenants`) | Claude | Creates tenant + owner membership in one transaction, slug uniqueness enforced |
| 1.8 | Implement team invite flow (invite by email, accept invite) | Claude | Invite creates `tenant_members` row with status `invited`, accept flips to `active` |
| 1.9 | Implement token refresh endpoint (`POST /auth/refresh`) with hardening | Claude | Origin validation, Content-Type check, POST-only, httpOnly cookie handling per `security.md §1` |
| 1.10 | Write cross-tenant isolation integration tests | Claude | Tests prove Tenant A cannot read/write Tenant B's `tenant_members` data |
| 1.11 | Configure Cognito email verification + SES integration | Claude | Signup → verification email arrives, user can verify and log in |

---

## M2 — Storefront & Catalog

| # | Task | Primary Implementor | DoD |
|---|------|-------|-----|
| 2.1 | Create `storefront_config` table + RLS + migration | Claude | Table with `UNIQUE(tenant_id)`, RLS policies, isolation test |
| 2.2 | Create `catalog_items` table + RLS + migration | Claude | Table with type discriminator (`TEXT+CHECK`), metadata JSONB, indexes per `data-model.md` |
| 2.3 | Create `media_assets` table + RLS + migration | Claude | Polymorphic media table, `entity_type` + `entity_id`, S3 key column |
| 2.4 | Implement storefront config API (GET/PUT) | Claude | Admin can read/update branding; logo stored in S3 under `{tenant_id}/` |
| 2.5 | Implement catalog CRUD API | Claude | Create, read, update, delete catalog items. Type validation. Cursor pagination. |
| 2.6 | Implement presigned URL upload/download endpoints | Claude | PUT URL for upload (max 10 MB, content-type check), GET URL for download (15-min expiry), tenant prefix validated |
| 2.7 | Build public storefront page (Next.js) | Claude | Renders at `https://{slug}.yourdomain.com` with tenant branding + catalog |
| 2.8 | Implement UTM capture on storefront visit | Claude | `POST /storefront/{slug}/visit` stores UTM params, returns `visit_id` |
| 2.9 | Configure Vercel wildcard subdomain routing | Claude | `*.yourdomain.com` resolves to Vercel, slug extracted in Next.js middleware |
| 2.10 | Write catalog + storefront integration tests | Claude | CRUD works, presigned URLs valid, cross-tenant isolation holds |

---

## M3 — Structured Capture

| # | Task | Primary Implementor | DoD |
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

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 4.1 | Create `ai_conversations` + `ai_usage_log` tables + RLS + migrations | Claude | **DONE** | Tables per `data-model.md`, RLS policies, indexes |
| 4.2 | Implement AI gateway (`app/services/ai_gateway.py`) | Claude | **DONE** | Quota reserve → provider call → adjust/rollback → log. Two gateways: dashboard (`ai_gateway.py`, last 10 turns) + storefront (`storefront_ai_gateway.py`, last 6 turns). |
| 4.3 | Implement provider abstraction layer | Claude | **DONE** | `AIProvider` protocol + OpenAI (default) and Groq (fast/free). Configurable via `AI_PROVIDER` env. |
| 4.4 | Implement Redis quota check with reserve/rollback | Claude | **DONE** | INCRBY estimated → call → DECRBY on failure OR adjust delta on success. Integration test proves rollback. |
| 4.5 | Implement soft/hard limit logic + notification | Claude | Partial | Hard limit → 429. Soft limit notification not yet implemented. |
| 4.6 | Implement tenant system prompt builder | Claude | **DONE** | Builds prompt with tenant name + catalog summary. Dashboard: tenant-scoped ops summary. Storefront: product catalog (up to 50 items). |
| 4.7 | Build AI chat widget (Next.js storefront component) | Claude | **DONE** (M4.2) | Floating chat bubble on storefront pages. Session-based (`localStorage` key `session_id`, shared with `useVisit`). Rate limited: 10 msgs / 5 min per session. Read-only — no actions. |
| 4.8 | Implement conversation context management | Claude | **DONE** | Dashboard: last 10 turns from `ai_conversations.messages` JSONB. Storefront: last 6 turns from `storefront_ai_conversations.messages` JSONB. |
| 4.9 | Set up AI pricing config in SSM | Claude | | `/{env}/ai/pricing` populated with provider pricing. `/{env}/ai/provider` set. |
| 4.10 | Write AI gateway integration tests | Claude | **DONE** | Quota enforcement, rollback on failure, usage logging, rate limiting. 10 tests (5 dashboard + 5 storefront). |

---

## M5 — Attribution & Dashboard (Analytics/Funnel)

| # | Task | Primary Implementor | DoD |
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

| # | Task | Primary Implementor | DoD |
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

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 5c.1 | Create `stock_movements` table + RLS + migration | Claude | **DONE** | Table with tenant_id, product_id, delta_qty, reason (CHECK), note, order_id, actor_user_id. RLS policies. Unique partial index on (order_id, product_id) WHERE reason = 'order_cancel_restore'. |
| 5c.2 | Create `StockMovement` ORM model | Claude | **DONE** | Model registered in `__init__.py`. FK to products (RESTRICT), orders, users. |
| 5c.3 | Create inventory service (`record_stock_movement` + `restore_stock_for_cancelled_order`) | Claude | **DONE** | Single code path for all stock movements. Atomic INSERT + UPDATE in same transaction. Idempotent cancel restore (code check + DB unique index). |
| 5c.4 | Wire cancel restore into order status transitions | Claude | **DONE** | Only triggers on true transition into `cancelled` from a prior state. Passes actor_user_id. |
| 5c.5 | Integration tests for cancel restore + movement audit | Claude | **DONE** | 5 tests: tracked restore, untracked skip, no double-restore, movement rows correct, mixed order. |

### Packet 2 — Dashboard Restock + Movement History (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 5c.6 | `POST /tenants/me/products/{id}/restock` endpoint | Claude | **DONE** | Positive qty only, optional note, tracked-inventory products only. Reuses `record_stock_movement(reason="manual_restock")`. Returns updated product. |
| 5c.7 | `GET /tenants/me/products/{id}/stock-movements` endpoint | Claude | **DONE** | Cursor-paginated, newest-first. Returns delta_qty, reason, note, order_id, actor_user_id, created_at. |
| 5c.8 | Dashboard restock UI on product edit page | Claude | **DONE** | Qty + note form, green Restock button. Only shown when track_inventory=true. Updates stock display on success. |
| 5c.9 | Dashboard movement history UI on product edit page | Claude | **DONE** | Table showing last 20 movements with reason label, signed delta, note, timestamp. Refreshes after restock. |
| 5c.10 | Integration tests for restock + history | Claude | **DONE** | 4 tests: restock increases stock + creates movement, rejects untracked, rejects zero/negative qty, history returns correct rows. |

**Tech debt:** Direct `stock_qty` edit via `PATCH /products/{id}` still bypasses movement trail. Not addressed in this packet.

**Future cleanup — Inventory UX consolidation:**
- Product edit page currently shows both direct `Stock Qty` editing and the audited Restock form, which is confusing about which path to use.
- When `track_inventory = true`: make stock display read-only, rename label to "Current Stock", add helper text ("Use Restock below to add inventory").
- Route all stock changes through audited movement flows (`/restock`, future `/adjust`) instead of direct `stock_qty` PATCH.

### Packet 3 — Low-stock Alerts in Dashboard (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 5c.11 | Add `low_stock_threshold` column to products + migration | Claude | **DONE** | Nullable INT, server_default=5. Migration reversible. |
| 5c.12 | Add `low_stock_threshold` to Create/Update schemas + `is_low_stock` to Response | Claude | **DONE** | Computed: `track_inventory AND threshold > 0 AND 0 < stock_qty <= threshold`. Create default=5, Update optional. |
| 5c.13 | Compute `is_low_stock` in `_product_response()` | Claude | **DONE** | Out-of-stock (qty=0) is NOT low-stock. Untracked products never low-stock. Threshold 0/NULL = disabled. |
| 5c.14 | Dashboard products list: amber "Low stock" badge + filter toggle | Claude | **DONE** | Amber pill for low-stock items. "All" / "Low stock only" frontend filter buttons with count badge. |
| 5c.15 | Product create/edit UI: low-stock threshold input | Claude | **DONE** | Shown when track_inventory=true. Placeholder 5, label "(0 = disabled)". Included in create + edit submit body. |
| 5c.16 | Integration tests for `is_low_stock` computation | Claude | **DONE** | 7 tests: at threshold, below, above, out-of-stock, untracked, threshold=0, custom threshold. |

### Packet 4 — Analytics CSV Export (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 5c.17 | Frontend CSV export from analytics summary data | Claude | **DONE** | `buildCsv()` helper generates 3-section CSV: KPI summary, funnel with rates, daily series. No new backend endpoint. |
| 5c.18 | "Export CSV" button on analytics dashboard | Claude | **DONE** | In header next to range selector. Disabled while loading or when no data. Filename includes preset + date. |
| 5c.19 | Update docs for shipped Packet 4 | Claude | **DONE** | Backlog + milestones updated. |

---

## M6 — Admin Panel

### Packet 1 — Platform Admin Foundation + Tenant Suspension (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 6.1a | Add `is_platform_admin` to users table + migration | Claude | **DONE** | Boolean, non-null, default false. Manual DB assignment only. |
| 6.1b | Platform admin auth guard (`require_platform_admin`) | Claude | **DONE** | Dependency checks flag, returns 403 for non-admins. |
| 6.1c | Platform admin RLS policy on `tenant_members` | Claude | **DONE** | SELECT-only policy allows cross-tenant member counts when `app.current_user_id` is a platform admin. |
| 6.1d | `GET /api/v1/admin/tenants` — list all tenants | Claude | **DONE** | Returns id, name, slug, is_active, created_at, member_count. Limit/offset pagination. |
| 6.2 | `POST /admin/tenants/{id}/suspend` + `/reactivate` | Claude | **DONE** | Toggles `is_active`. Writes `tenant.suspended` / `tenant.reactivated` audit events. 409 on idempotent re-call. |
| 6.2b | Enforce suspended tenant 403 on authenticated API | Claude | **DONE** | `get_db_with_tenant` checks `tenant.is_active`; returns 403 "Tenant is suspended". Public storefront already checks `is_active` via `get_db_with_slug`. |
| 6.7a | Platform admin + suspension integration tests | Claude | **DONE** | 13 tests: 10 superuser + 3 RLS (app_user). Covers list, suspend, reactivate, audit events, 403 enforcement, idempotency, non-admin rejection. |

### Packet 2 — Role Change + CSV Export (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 6.3 | `PATCH /tenants/me/members/{id}` — change member role | Claude | **DONE** | Owner-only. Cannot change own role. Cannot demote last owner. 409 on same role. Writes `role_change` audit event. |
| 6.4 | CSV export endpoints (orders/donations/pledges) | Claude | **DONE** | `GET /tenants/me/{entity}/export` with optional date range. Admin+ role. UTF-8 BOM for Excel. Defense-in-depth tenant_id filter. |
| 6.4b | List endpoints add explicit tenant_id filter | Claude | **DONE** | Defense-in-depth: all list + export queries filter by tenant_id in addition to RLS. |
| 6.7b | Role change + CSV export integration tests | Claude | **DONE** | 13 tests: 7 role change (promote, demote, non-owner 403, self-change 400, last-owner 400, audit event, same-role 409) + 6 CSV export (orders/donations/pledges, empty, RLS isolation, member 403). |

### Packet 3 — Admin Tenant List Usage Summary (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 6.1e | Platform admin SELECT RLS policies on orders/donations/pledges | Claude | **DONE** | Migration adds SELECT-only policies (same pattern as tenant_members). Production-correct under app_user. |
| 6.1f | Extend `GET /admin/tenants` with usage summary | Claude | **DONE** | order_count, donation_count, pledge_count, last_activity_at. Correlated subqueries, bounded by LIMIT 50. |
| 6.7c | Usage summary integration tests (superuser + RLS) | Claude | **DONE** | 3 tests: with-data counts, empty-tenant zeros, RLS-validated counts under app_user. |

### Packet 4 — Super Admin Tenant List UI (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 6.5a | Super admin tenant list page (`/dashboard/admin/tenants`) | Claude | **DONE** | Table with name, slug, status badge, member/order/donation/pledge counts, last activity, created date. Suspend/reactivate buttons with confirm dialog. Inline success/error messages. |
| 6.5b | Dashboard home "Platform Admin" link card | Claude | **DONE** | Always-visible card linking to admin tenants page. Backend 403 is the real guard. |

### Packet 5+ — Remaining (not started)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 6.5c | Super admin UI refinements (search, pagination, detail view) | Claude | Not started | Search by name/slug, pagination controls, tenant detail page |
| 6.6 | Build tenant admin UI (Next.js) | Claude | Not started | Team management, storefront config, export buttons |

---

## M7 — Notifications

### Packet 1 — Notification Preferences Foundation (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 7.1a | Create `notification_preferences` table + migration | Claude | **DONE** | Table per `data-model.md`: `UNIQUE(tenant_id)`, `email_enabled`, `telegram_enabled`, `telegram_chat_id`, `telegram_bot_token_ref` (Secrets Manager key, nullable). Reversible migration. |
| 7.1b | `NotificationPreference` ORM model + RLS policies | Claude | **DONE** | Model extends `TenantScopedBase`. RLS: tenant-scoped SELECT + INSERT + UPDATE + DELETE. Cross-tenant isolation test. |
| 7.2a | `GET /api/v1/tenants/me/notification-preferences` | Claude | **DONE** | Returns current preferences. Auto-creates default row (both disabled) on first read. All authenticated roles can read. |
| 7.2b | `PUT /api/v1/tenants/me/notification-preferences` | Claude | **DONE** | Admin/owner only. Updates `email_enabled`, `telegram_enabled`, `telegram_chat_id`. `telegram_bot_token_ref` not exposed in PUT. Validates telegram_chat_id required when enabling Telegram. |
| 7.7a | Notification preferences integration tests | Claude | **DONE** | 9 tests: CRUD (auto-create, idempotent re-read, partial update), RLS isolation, role guard (member GET ok, member PUT 403, admin PUT ok), validation (telegram without chat_id 422). |

### Packet 2 — Notification Services + Celery Tasks (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 7.3 | Implement email notification service + Celery task | Claude | **DONE** | SES client (boto3) with dev-mode log fallback. Plain text templates. Skips safely when recipient email missing. |
| 7.4 | Implement Telegram notification service + Celery task | Claude | **DONE** | HTTP POST to Telegram Bot API via httpx. Skips safely when chat_id missing or bot_token empty. |
| 7.4b | Celery task wrappers (`send_order_notification`, `send_donation_notification`) | Claude | **DONE** | Sync entry points call `asyncio.run()` with async helper reusing existing async DB session. Core logic in testable `_process_*` functions accepting a session. |
| 7.7b | Notification services integration tests | Claude | **DONE** | 14 tests: templates (2), email sender dev/prod (2), telegram sender success/error/empty (4), task logic — both enabled, both disabled, email-only, telegram-no-chat-id, no-customer-email, no-donor-email (6). |

**Deferred from P2:** Secrets Manager fetch (env-var only for now), pledge notifications (periodic/Celery Beat), donor receipt email.

### Packet 3 — Dispatch Wiring (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 7.5a | Wire notification dispatch on order creation | Claude | **DONE** | Explicit `await db.commit()` in public order endpoint, then `send_order_notification.delay()`. Fire-and-forget, wrapped in try/except so dispatch failure never breaks the API response. |
| 7.5b | Wire notification dispatch on donation creation | Claude | **DONE** | Same pattern for donation endpoint (explicit commit, then .delay()). |
| 7.7c | Dispatch wiring integration tests | Claude | **DONE** | 4 tests: order dispatches .delay() with correct args, donation dispatches .delay() with correct args, order still 201 when .delay() raises, donation still 201 when .delay() raises. |

### Packet 4 — Donation Receipt Email (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 7.5c | Donation receipt email to donor | Claude | **DONE** | `format_donation_receipt()` template, `_process_donation_receipt()` task logic, `send_donation_receipt` Celery task. Dispatched when `receipt_requested=true` and `donor_email` present. Independent of tenant notification_preferences. Fire-and-forget with try/except. |
| 7.7d | Donation receipt integration tests | Claude | **DONE** | 7 tests: template (1), task logic — sent/skipped-not-requested/skipped-no-email (3), dispatch — called/not-called-false/not-called-no-email/resilience (4). |

### Packet 5+ — Remaining (not started)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 7.5d | Pledge due-soon periodic reminder | Claude | Not started | Celery Beat task: query pledges with `target_date` within 7 days + open status. Telegram to tenant. Redis dedup (once per pledge per day). |
| 7.5e | AI soft-limit notification | Claude | Not started | Wire into AI quota check (ADR-0004). Celery task on soft-limit breach. Dedup once per billing period. |
| 7.6 | Configure SES sending identity + DKIM | Claude | Not started | Domain verified, DKIM configured, test email sends successfully |
| 7.8 | Frontend notification preferences UI | Claude | Not started | Dashboard settings page with toggles for email/Telegram, chat ID input, save button. |

---

## M8 — Infrastructure & DevOps

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 8.1 | Create Docker Compose for local dev (Postgres, Redis) | Claude | **DONE** | `docker compose up -d` starts all deps, health checks pass |
| 8.2 | Create Dockerfile for backend (multi-stage, slim) | Claude | **DONE** | Builds successfully, runs backend and worker via different entrypoints |
| 8.3 | Set up GitHub Actions CI (test + lint + build) | Claude | **DONE** | PR and push to main: backend lint (ruff, black), backend test (pytest with Postgres + Redis), frontend check (eslint, build), Docker build validation. ECR push deferred to CD packet. |
| 8.4 | Provision VPC, subnets, security groups in `ap-southeast-1` | Claude | **DONE** | P1 script+template 80d4e04, P2 executed, fix a841cfa |
| 8.5 | Provision RDS PostgreSQL (encryption, `require_ssl`) | Claude | **DONE** | MVP temporary profile: Single-AZ `db.t4g.micro`, encrypted, `rds.force_ssl=1`. Planned upgrade to Multi-AZ `db.t4g.medium` when budget/usage justifies. Bootstrap task creates `app_migrator` (DDL+DML) + `app_user` (DML, RLS). SG repair: RDS ingress + ECS egress rules added during execution (missing from 8.4 P2). |
| 8.6 | Provision ElastiCache Redis (encryption in transit) | Claude | **DONE** | MVP temporary profile: Single-AZ `cache.t4g.micro`, Redis 7.1, in-transit + at-rest encryption, no AUTH token. Planned upgrade to Multi-AZ when budget/usage justifies. ECS connectivity proof passed (`rediss://` TLS from container). SG repair: Redis ingress rule added during execution (missing from 8.4 P2). |
| 8.7 | Provision S3 bucket (Block Public Access, versioning) | Claude | **DONE** | Bucket `saas-media-prod-701893741240` in `ap-southeast-1`. Block Public Access all ON, versioning enabled, SSE-S3 (AES256), lifecycle transition to STANDARD_IA after 90 days. S3 object policy attached to shared ECS task role (`S3MediaAccess`), backend task def updated with `S3_BUCKET` (rev 2). CORS applied: PUT from `https://ai-storefront-platform.vercel.app` with `Content-Type` header (enables presigned upload from Vercel frontend). |
| 8.8a | Create ECR repository + OIDC + CI image push | Claude | **DONE** | ECR repo exists in ap-southeast-1, GitHub OIDC role created, CI pushes image on push to main |
| 8.8b | Create ECS cluster + task definitions + deploy services | Claude | **DONE** | P1 repo contract (env-contract, task-def templates, runbook). P2 cluster/roles/secrets/logs provisioned. P3 task defs registered and backend + worker services running in `saas-cluster`. Worker fix: Celery requires `ssl_cert_reqs=required` in `rediss://` URL, so `/prod/redis-url` was updated. Backend HEALTHY, worker Celery ready. Image pinned to `ecece62`. Services are private-only; public reachability comes later in 8.9. |
| 8.9 | Set up ALB + CloudFront + WAF | Claude | In progress | P1: ALB foundation (internet-facing ALB, target group, public HTTP endpoint). P2: ACM cert + HTTPS listener for `api.ramitestapp.top`, HTTP :80→HTTPS redirect. P3a: origin hostname `origin-api.ramitestapp.top` live with SNI cert on ALB, viewer cert issued in us-east-1. P3b: WAF WebACL `saas-api-waf` created in us-east-1 (CLOUDFRONT scope, 4 rules, 1102 WCU). P3c: CloudFront distribution `EQPDDTZHFIMYE` (`d1zgvjjy4fkyou.cloudfront.net`) deployed with WAF attached, origin `origin-api.ramitestapp.top` over HTTPS, proxy verified. Note: `api.ramitestapp.top` still resolves to ALB today. Remaining: DNS cutover (P3d), ALB hardening (P3e), CORS/domain wiring (P4). Domain: `ramitestapp.top` on Namecheap BasicDNS. |
| 8.10 | Set up Vercel project with wildcard subdomain | Claude | In progress | Demo P1: Frontend deployed to Vercel at `https://ai-storefront-platform.vercel.app`. Backend CORS configured (`saas-backend:3`). Demo P2a: `COGNITO_MOCK=true` enabled on ECS (`saas-backend:4`), dev token login works, dashboard health widget verified. Frontend fix: dev-login token whitespace stripping committed. Demo P2b: Tenant `rami-demo-store` created (PHP currency), 2 categories, 3 products, storefront config set. Demo images: 3 product images uploaded via existing media pipeline (presigned PUT to S3), public storefront response verified with correct `image_url` per product, storefront image-fit polish (`object-contain`) committed and deployed. Groq AI chat: `/prod/ai-api-key` updated with real Groq key in Secrets Manager, `openai>=1.60,<2` added to backend dependencies, backend image rebuilt and pushed to ECR (tag `4642e4a`), task definition updated to `saas-backend:6` with `AI_PROVIDER=groq`, `AI_MODEL=llama-3.3-70b-versatile`, storefront AI chat endpoint verified returning real AI responses (Llama 3.3 70B via Groq), token usage logged. P4a-fix: RLS migration `n8o9p0q1r2s3` adds 3 tenant-only SELECT policies on `attribution_visitors`/`attribution_sessions`/`attribution_events` to unblock public ingest upserts (`ON CONFLICT DO UPDATE` requires implicit SELECT), committed `c06ff96`, deployed via `saas-migration:6` (image `:c06ff96`), DB head now `n8o9p0q1r2s3`. P4a: Analytics demo data seeded via ECS one-off task — 5 visitors, 7 sessions, 25 events across 5 days (Mar 15–19), dashboard analytics page populated. P4b1: Demo user `demo@rami.dev` set `is_platform_admin=true` via ECS one-off task, Admin → Tenants page unlocked. P4b2: 2 fake demo tenants seeded via ECS one-off task — Sunset Bakery (`sunset-bakery`, PHP) and Gulf Tech Solutions (`gulf-tech`, PHP), each with 1 owner user and 1 tenant_member; Admin → Tenants shows 3 tenants. P5 frontend polish: dashboard shell/sidebar rollout (all 10 dashboard pages wired), tenant name links to storefront, dashboard home redesign with nav card grid, mobile table overflow fix (`overflow-x-auto` on 5 table pages). P5-fix: S3 bucket CORS applied for presigned PUT upload from Vercel frontend (product image upload now works on live). Remaining: custom domain `app.ramitestapp.top` (Demo P3, optional). |
| 8.11 | Set up GitHub Actions CD (deploy to staging + production) | Claude | Not started | Staging auto-deploy on main. Production via manual workflow dispatch. |
| 8.12 | Set up CloudWatch log groups + alarms | Claude | Not started | Log groups for backend/worker/audit. Alarms: CPU, connections, 5xx. |
| 8.13 | Populate Secrets Manager with all secrets | Claude | Not started | All secrets per `security.md §3` table |

---

## B — Bilingual / i18n (Arabic + English)

### Track A — Storefront Public Pages (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| A1 | Bilingual foundation: `next-intl`, cookie-based locale, `en.json` + `ar.json`, `LanguageSwitcher` component | Claude | **DONE** | `next-intl` configured with `NEXT_LOCALE` cookie. No URL-prefix routing. Storefront pages wrapped with `NextIntlClientProvider`. |
| A2 | Localize storefront shell + chat widget | Claude | **DONE** | Header, footer, chat bubble, chat panel, all storefront chrome strings in both locales. |
| A3 | Localize storefront checkout, donate, pledge flows | Claude | **DONE** | All form labels, validation messages, success/error states in both locales. |

### Track B — Dashboard UI Chrome (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| B1 | Auth pages: login, signup, forgot password + language switcher | Claude | **DONE** | All auth UI strings bilingual. Signup validation messages localized. |
| B2 | Dashboard shell + shared nav | Claude | **DONE** | Sidebar, header, nav links, tenant name — all bilingual. |
| B3 | Dashboard home page | Claude | **DONE** | Welcome text, nav cards, KPI labels bilingual. |
| B4 | Transaction pages (orders, donations, pledges) | Claude | **DONE** | Table headers, status badges, empty states, action buttons bilingual. |
| B5 | Assistant page | Claude | **DONE** | Chat UI, input placeholder, send button, quota warning bilingual. |
| B6 | Analytics page | Claude | **DONE** | KPI cards, funnel labels, date range, CSV export button bilingual. |
| B7 | Categories pages (list, new, edit) | Claude | **DONE** | Table headers, form labels, validation, empty states bilingual. |
| B8 | Products pages (list, new, edit, images, inventory) | Claude | **DONE** | All product form sections bilingual including restock/movement history UI. |
| B9 | Product edit images section | Claude | **DONE** | Upload, delete, alt text labels bilingual. |
| B10 | Storefront settings page | Claude | **DONE** | All branding config labels, upload controls, color pickers bilingual. |

### Track C — Product/Category Content Translation (shipped)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| C1 | Strategy: duplicate Arabic columns (`name_ar`, `description_ar`) on products + categories | Claude | **DONE** | Approved over JSONB or translations table for MVP simplicity. |
| C2 | DB migration: add `name_ar`, `description_ar` to products + categories | Claude | **DONE** | Alembic revision `o9p0q1r2s3t4`. 4 nullable columns added. Round-trip tested (upgrade → downgrade → upgrade). |
| C3 | Backend schemas/CRUD: expose Arabic fields on tenant endpoints | Claude | **DONE** | `CategoryCreate/Update/Response` + `ProductCreate/Update/Response` include `name_ar`, `description_ar`. `PublicProductResponse` and `public_storefront.py` intentionally unchanged in C3. |
| C4 | Dashboard category form authoring (new + edit) | Claude | **DONE** | Arabic name/description inputs below English counterparts. Optional fields, send `null` when empty. `formNameAr`/`formDescriptionAr` i18n keys. |
| C5 | Dashboard product form authoring (new + edit) | Claude | **DONE** | Same pattern as C4 for products. Restock/images/movement sections untouched. |
| C6 | Storefront Arabic content rendering + fallback | Claude | **DONE** | `PublicProductResponse` extended with `name_ar`/`description_ar`. 5 render points updated: category filter buttons, product image alt, product card title, product card description (resolved variable pattern), add-to-cart name snapshot. Fallback: `(locale === "ar" && arabic_value) ? arabic_value : primary_value`. Hero text + stock_display unchanged. |

### Track D — Remaining (not started)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| D1 | Admin panel pages bilingual | Claude | Not started | Super admin tenant list, suspend/reactivate dialogs. |
| D2 | Notification preferences page bilingual | Claude | Not started | Email/Telegram toggle labels, save button. |
| D3 | RTL layout support for Arabic locale | Claude | Not started | `dir="rtl"` on root when locale is `ar`. Tailwind RTL utilities. |
| D4 | Storefront hero text Arabic support | Claude | Not started | `hero_text_ar` on `storefront_config` + fallback rendering. |
| D5 | CSV/export content: keep English-only (documented decision) | Claude | Not started | Confirm exports use primary fields only. Document as intentional. |

---

## M9 — Hardening & Launch Prep

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 9.1 | Implement rate limiting middleware (Redis-based) | Claude | Not started | Per-IP, per-tenant, per-auth, per-AI session limits per `security.md §6`. Returns 429 + Retry-After. |
| 9.2 | OWASP top-10 spot check | Claude | Not started | SQL injection, XSS, CORS, auth bypass — all tested and passing |
| 9.3 | Verify structured JSON logging in CloudWatch | Claude | Not started | All logs are JSON with `request_id`, `tenant_id`, `user_id`. No PII in logs. |
| 9.4 | Implement health check endpoint with DB + Redis checks | Claude | Not started | `GET /health` returns `{"status": "ok", "db": "ok", "redis": "ok"}` |
| 9.5 | Create seed data script for demo | Claude | Not started | Creates demo tenants, users, catalog, orders, donations. Idempotent. |
| 9.6 | Create smoke test suite | Claude | Not started | End-to-end: signup → create tenant → add catalog → place order → check dashboard. Runs in CI against staging. |
| 9.7 | Run full QA checklist on staging | Claude | Not started | All items in `qa-checklist.md` pass |
| 9.8 | Review and finalise runbook + incident response docs | Claude | Not started | Docs are accurate, commands work, team has reviewed |
| 9.9 | Performance baseline test | Claude | Not started | P95 API latency < 300ms, storefront LCP < 2s, AI response < 5s |
| 9.10 | Security review: grep for secrets, tokens, PII in logs | Claude | Not started | Zero occurrences of plaintext secrets or PII in logs/code |

---

## V2 — POS + Merchant-Ready

V2 runs two parallel tracks that converge in M13:
- **M10A / Merchant-Ready Core**: real auth, onboarding, roles/permissions
- **M10B / POS Omnichannel**: cashier role, POS order foundation, permission scoping

Key design decisions:
- POS uses the shared `orders` table with `source='pos'`. A separate POS Sales Domain (`pos_sales` + `pos_sale_items`) was originally planned but deferred — revisit only if future POS lifecycle needs (e.g., register sessions, split tenders) justify separate tables.
- Online orders keep current JSONB line item storage; `order_items` normalization is an optional follow-up, not a POS prerequisite
- Shared customer records ship in M11 and do NOT block first POS MVP
- Both tracks share products table, inventory, and reporting

---

## M10A — Foundations: Auth & Onboarding

### M10A.1 — Auth + Onboarding Planning

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 10A.1a | Auth planning: auth provider config, signup flow, email verification, mock retirement plan | Claude | **Done** | Planning completed inline through approved implementation packets. |
| 10A.1b | Onboarding planning: signup → create store → configure storefront journey (screen-by-screen) | Claude | **Done** | Planning completed inline through approved implementation packets. |
| 10A.1c | Role matrix review: owner / admin / member / cashier — permissions and access boundaries | Claude | Not started | Role matrix table with per-role access rules. |

### M10A.2 — Real Auth Implementation

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 10A.2a | Real auth implementation (Cognito signup/login/verify flows; mock mode retained for local dev) | Claude | **Done** | Cognito wired (signup, login, verify-email, forgot/reset-password). Mock mode retained for local dev. |
| 10A.2b | Test fixture migration for real auth | Claude | Not started | Existing integration tests pass without mock mode. Dev seed data updated. |

### M10A.3 — Self-Serve Onboarding

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 10A.3a | Onboarding flow: signup → invitation accept / create tenant → dashboard | Claude | **Done** | Onboarding page: accept invitations, create-store form with slug/currency, redirects to dashboard. |

---

## M10B — Foundations: POS Domain

### M10B.1 — POS Planning (complete)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 10B.1a | POS domain planning: `pos_sales` + `pos_sale_items` schema design, screen wireframes, cashier role boundaries, inventory integration design | Claude | **DONE** | Planning memo accepted. Schema and screen flows documented in planning memo. |

### M10B.2 — POS Order Foundation (complete)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 10B.2a | Extract shared order service from storefront + add `source` column with migration | Claude | **DONE** | `order_create.py` shared service. `source` column (storefront\|pos) with CHECK + migration. Storefront refactored to use shared service. |
| 10B.2b | POS order endpoint (`POST /api/v1/tenants/me/pos/orders`) | Claude | **DONE** | Authenticated endpoint creates fulfilled orders with source=pos. Walk-in default for customer_name. |
| 10B.2c | POS order integration tests | Claude | **DONE** | 5 tests: happy path, insufficient stock, inactive product, cross-tenant, source persists. |
| 10B.2d | Frontend POS cashier page with bilingual strings | Claude | **DONE** | `/dashboard/pos` page with product catalog, cart, stock clamping, checkout. Nav entry + en/ar translations. |

> **Resolved**: The cashier role + permission scoping deferred from M10B.2 was shipped in M10B.3 below.

### M10B.3 — Cashier Role + Permission Scoping (complete)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 10B.3a | Add `cashier` to role CHECK constraint + migration, hierarchy level 0, invite/update schema patterns | Claude | **DONE** | Migration reversible. `role_hierarchy` updated. `MemberInvite` and `MemberUpdate` accept cashier. |
| 10B.3b | Scope endpoint access: cashier allowed on product list + POS order; denied on all member+ endpoints by hierarchy | Claude | **DONE** | `require_role("cashier")` on product list and POS endpoint. All other endpoints deny cashier automatically. No new endpoints added. |
| 10B.3c | Cashier permission boundary tests | Claude | **DONE** | 9 tests: allow POS + product list, deny product detail/CRUD/orders/categories/members, role update to cashier, owner regression. |
| 10B.3d | Frontend dashboard scoping for cashier role | Claude | **DONE** | Role derived from `bootstrap.memberships`. Cashier nav shows POS only. Centralized redirect to `/dashboard/pos`. |

### M10B.4 — POS Sale Receipt (complete)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 10B.4a | Add `customer_name` to `OrderCreateResponse` schema | Claude | **DONE** | Additive field, `from_attributes=True` reads from existing model column. All POS + cashier tests pass. |
| 10B.4b | Frontend POS receipt view with print support | Claude | **DONE** | Success screen renders store name (from bootstrap), order number, date/time, customer name (fallback to "Walk-in"), line items from JSONB snapshot, total. Print button calls `window.print()`. Dashboard shell hides sidebar/top bar and removes margin offset on print. en/ar receipt strings added. |

> **Architecture**: No new endpoints or tables. Shared orders with `source='pos'` continue. Receipt data comes entirely from `OrderCreateResponse` + existing bootstrap membership.

### M10B.5 — POS Order History + Receipt Reprint (complete)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 10B.5a | Backend: POS order list + detail endpoints | Claude | **DONE** | `GET /api/v1/tenants/me/pos/orders` (cursor-paginated, `source='pos'` filter, tenant-scoped, `require_role("cashier")`). `GET /api/v1/tenants/me/pos/orders/{id}` (tenant-scoped, returns 404 for non-POS orders and cross-tenant misses). Tests: list, source filter, detail happy path, storefront 404. |
| 10B.5b | Frontend: POS order history view + receipt reprint | Claude | **DONE** | "Order History" button on POS page header. History table shows order #, customer, total, date. Clicking "View" fetches order detail and reuses existing M10B.4 receipt screen — no receipt markup duplicated. "New Sale" clears history state. en/ar strings added. |

> **Architecture**: No new tables or migrations. Shared orders with `source='pos'` continue. History endpoints reuse `OrderListItem` and `OrderCreateResponse` schemas.

### M10B.6 — POS Inventory via `record_stock_movement` (complete)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 10B.6a | Migration + model: add `pos_sale` to `ck_stock_movements_reason` | Claude | **DONE** | Reversible Alembic migration drops and recreates CHECK constraint with `pos_sale` added. `StockMovement` model updated to match. |
| 10B.6b | POS order creation records auditable stock movement | Claude | **DONE** | `record_stock_movement` extended with `prevent_negative_stock` and `insufficient_stock_detail` params. POS path creates `StockMovement(reason='pos_sale', delta_qty=-qty, order_id=order.id, actor_user_id=...)` after order flush. Atomic guard still prevents negative stock. Storefront stock path unchanged. No frontend changes. No new tables. |
| 10B.6c | Backend test: POS order creates stock movement row | Claude | **DONE** | `test_pos_order_records_stock_movement` in `test_pos.py`: verifies `reason`, `delta_qty`, `order_id`, and `actor_user_id` on the committed movement row. |

> **Architecture**: No new tables. `stock_movements` table already existed. POS orders now generate an auditable stock movement row alongside the existing atomic stock decrement guard. Storefront order stock behavior unchanged.

### M10B.7 — POS Order Cancel for Cashier (complete)

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 10B.7a | Backend: POS cancel endpoint with stock restore | Claude | **DONE** | `PATCH /api/v1/tenants/me/pos/orders/{id}/cancel`. Cashier-accessible, tenant + `source='pos'` scoped. `fulfilled → cancelled` only; 409 for already-cancelled or invalid status. Calls `restore_stock_for_cancelled_order`. Writes `AuditEvent(action='status_transition')`. No new tables or migrations. |
| 10B.7b | Backend tests: POS cancel coverage | Claude | **DONE** | 6 tests in `test_pos.py`: cashier cancel, stock restore, `order_cancel_restore` movement row, double-cancel 409, storefront 404, cross-tenant 404. |
| 10B.7c | Frontend: Cancel Order action from receipt screen | Claude | **DONE** | Cancel button on receipt re-view (hidden when already cancelled). `window.confirm` before call. On success: `lastOrder` updated, history row badge updated. Cancelled badge on receipt and history list. Print remains available for cancelled orders. en/ar strings added. |

> **Architecture**: No new tables or migrations. POS cancel reuses `restore_stock_for_cancelled_order` from M5c inventory service. `ORDER_TRANSITIONS` (storefront) unchanged.

> **Deferred**: POS Sales Domain (`pos_sales` + `pos_sale_items` tables, POS sales service layer, separate integration tests) remains deferred to a later POS packet. Current POS orders use the shared `orders` table with `source='pos'`.

---

## M11 — Selling & Payments MVP

### M11.1 — POS Sell Screen

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 11.1a | POS sell screen UI: product grid/search → cart → cash checkout | Claude | **Shipped in M10B.2** | `/dashboard/pos` page shipped with product search, cart, stock clamping, checkout. Further enhancements (barcode, hold/resume) are M11 scope. |

### M11.2 — POS Inventory Integration

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 11.2a | POS sale decrements shared stock via `record_stock_movement(reason="pos_sale")` | Claude | **Shipped in M10B.6** | POS order creation now calls `record_stock_movement(reason="pos_sale")` with atomic guard, `order_id`, and `actor_user_id`. Storefront stock path unchanged. |

### M11.3 — POS Receipt

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 11.3a | POS receipt: print-friendly HTML layout, thermal-friendly CSS | Claude | **Shipped in M10B.4** | Browser-print receipt shipped in M10B.4. Thermal printer integration remains M11 scope if needed. |

### M11.4 — Product SKU/Barcode

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 11.4a | SKU/barcode field on products (optional text field) | Claude | **Shipped** | `products.sku` and `products.barcode` nullable String(64), tenant-scoped partial unique indexes. `ProductCreate`/`ProductUpdate`/`ProductResponse` include both fields; empty strings normalize to null; 409 on name/SKU/barcode uniqueness conflicts. Public storefront unchanged. Dashboard product new/edit forms include SKU/barcode inputs. POS search matches name, SKU, or barcode — barcode scanner works as keyboard input into existing POS search box. Dedicated backend SKU/barcode tests remain a follow-up (Write preview corruption prevented test file creation). |

### M11.5 — Payment Method Config

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 11.5a | Payment method config per tenant (cash, bank transfer, manual external, gateway placeholder) | Claude | **Shipped** | Catalog: `cash`, `knet`, `bank_transfer`, `cod`, `manual`. Config stored in `storefront_config.payment_methods` JSONB as `{"pos": [], "online": []}`. `orders.payment_method` nullable TEXT with DB CHECK. Dashboard storefront settings page: checkbox groups to configure POS and Online methods (saved via existing config PUT). `GET /pos/payment-methods` endpoint (cashier role, fallback `["cash"]`). Public storefront config exposes online methods only — POS methods are never exposed publicly. POS and public checkout pickers both send `payment_method` on order create. 11 backend integration tests added and passing. No real payment gateway, payment capture, or payment status tracking. |

### M11.6 — Online Order Payment + Receipts

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 11.6a | Payment status tracking on online orders | Claude | **Deferred** | Intentionally deferred — no `payment_status` column, no payment capture, no gateway. `orders.payment_method` records the selected method (shipped in M11.5). Full payment status lifecycle deferred until a real gateway integration is planned. |
| 11.6b | Receipt generation for online orders (HTML, print button) | Claude | **Shipped** | Public checkout success screen replaced with printable receipt: order number, date/time, customer name, line items (name/qty/unit price/subtotal), total, payment method (localized). Dashboard order detail endpoint `GET /api/v1/tenants/me/orders/{id}` (member+ role, tenant-scoped, 404 on missing/cross-tenant); returns full order incl. items JSONB, customer contact, payment_method, payment_notes, notes. Dashboard orders page: per-row View action fetches and renders printable receipt/detail view with print button. `window.print()` on both surfaces; dashboard chrome hidden via existing `print:hidden` shell layout. 5 backend tests added. No payment gateway, no payment capture, no payment_status. |

### M11.7 — Customer Records Foundation

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 11.7a | Shared customer records table + RLS + model + CRUD service + tests | Claude | **Shipped** | `customers` table (tenant_id, name, phone, email, notes, timestamps) with RLS (SELECT/INSERT/UPDATE/DELETE tenant-isolation policies) and tenant-scoped partial unique indexes on phone and email (`WHERE … IS NOT NULL`). `Customer` ORM model. `CustomerCreate`/`CustomerUpdate`/`CustomerResponse` schemas (lenient email normalize, name trimmed, `tenant_id` excluded from responses). CRUD API `GET/POST/GET{id}/PATCH{id}/DELETE{id}` under `/api/v1/tenants/me/customers` — list/get require member, create/update/delete require admin. Duplicate phone/email within a tenant → 409; same values across tenants allowed; cross-tenant access → 404. 13 backend tests passing. CRUD logic inline in route handlers (no separate service layer), matching the products pattern. **Customer linking is NOT included** — order/POS/storefront/donation linking and `orders.customer_id` remain M11.8. |

### M11.8 — Customer Linking

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 11.8a | Customer linking on order/donation/POS sale create (dedup by phone/email) | Claude | **Shipped** | `orders.customer_id` and `donations.customer_id` nullable UUID FKs to `customers(id)` (`ON DELETE SET NULL`, indexed). Shared `find_or_create_customer` service dedups by email first then phone, scoped per tenant; returns None for contactless input so no Walk-in/contactless customer rows are created. Storefront order create links/creates by `customer_email`/`customer_phone`; donation create links/creates by `donor_email`/`donor_phone`; POS verified no-op (no phone/email → no link). Order/donation snapshot contact fields preserved. `customer_id` exposed in `OrderCreateResponse`, `OrderDetailResponse`, and `DonationCreateResponse`. Tenant-scoped dedup and cross-tenant isolation covered by backend tests (order + donation linking + response exposure). Pledge linking intentionally excluded (M11.8 backlog names order/donation/POS only). No frontend customer UI and no backfill of historical records. |

---

## M12 — Operations & Variants

### M12.1 — Product Variants Schema

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 12.1a | Product variants table + per-variant stock tracking + migration | Claude | **Shipped** | `product_variants` table (tenant-scoped, RLS-enforced) + `ProductVariant` model: per-variant `stock_qty`, `sku`, `barcode`, optional `price_amount` override, size/color. Variant CRUD API under `/tenants/me/products/{id}/variants` (list cashier, get member, write admin) with `tenant_id` defense-in-depth. SKU/barcode unique across the combined product + variant namespace per tenant (cross-table check). Optional `OrderItemRequest.variant_id` validated (exists, active, belongs to the product, same tenant) and snapshotted with `variant_name` into `order.items`. Variant orders apply the variant `price_amount` override (else inherit product price) and decrement variant stock atomically on storefront + POS (product stock untouched); insufficient or NULL variant stock returns 409. POS `stock_movements` record `StockMovement.variant_id` (reason `pos_sale`); order cancel restores variant stock (reason `order_cancel_restore`) via a variant-aware idempotency index (`order_id, product_id, variant_id` NULLS NOT DISTINCT). Backend only, with comprehensive backend tests (CRUD, validation, price, stock, cancel/restore). Frontend variant UI (dashboard edit, storefront selector, POS picker) shipped in M12.2. |

### M12.2 — Variant UI

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 12.2a | Variant UI: dashboard product edit, storefront selector, POS variant picker | Claude | **Shipped** | Dashboard variant management (`aa441b0`), POS picker (`c866cc6`), public active-variant exposure (`db083cf`), storefront selector + checkout `variant_id` (`5db91ea`), Arabic i18n (`42090e8`). All three surfaces select/display variants and emit `variant_id`. |

### M12.2.1 — POS Variant Visibility Fix

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 12.2.1a | POS shows stock-tracked variant products when parent `stock_qty` is 0 | Claude | **Shipped** | Authed product list adds `has_variants` (batched, tenant-scoped, active-only) and an explicit `Product.tenant_id` defense-in-depth filter; POS `canSell()` lets `has_variants` products through and parent stock no longer disables them; per-variant stock still enforced in the picker. Backend tests: `has_variants` true / none / inactive-only / cross-tenant. No migration; storefront + order-creation logic unchanged. |

### M12.3 — POS Shift Management

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 12.3a | POS shift open/close with cash summary | Claude | **Shipped** | Backend `cb6a3c0` + frontend `0f3c057`. `pos_shifts` table (tenant-scoped, RLS-enforced) with a one-open-shift-per-tenant partial-unique index; `orders.shift_id` FK + index. Cashier-gated `GET /pos/shifts/current`, `POST /pos/shifts/open` (starting cash), and `POST /pos/shifts/close` (counted cash + optional notes → reconciliation summary). **Hard backend gate**: a POS sale requires an open shift, otherwise `409`; the order is associated to the open shift via `shift_id`. Cash summary counts only this-shift POS orders with `payment_method='cash'` and `status!='cancelled'`; `expected_cash = starting_cash + cash_sales`, `variance = counted_cash - expected_cash`, with cash sales snapshotted into `closing_cash_sales` at close. Backend tests cover open/close/current, the gate, cash-only and cancelled exclusion, one-open-per-tenant, and cross-tenant isolation. Frontend adds the POS shift banner (loading / open with live cash summary / closed summary / no open shift), inline open and close forms, the close summary, and a checkout gate that disables Complete Sale until a shift is open; 21 POS i18n keys added (Arabic currently uses English fallback — Arabic translation an optional follow-up). |

### M12.4 — POS Void/Cancel

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 12.4a | POS void/cancel with stock restore via `record_stock_movement()` | Claude | **Shipped** | Shipped as an **optional cancel reason on the existing full-order POS cancel** (backend `78654d8` + frontend `8d6d42a`) — **not** partial line-item void/refund. The M10B.7 full-order cancel + stock restore (`order_cancel_restore` via `record_stock_movement()`, idempotent) remains the base and is unchanged. Backend `78654d8`: nullable `orders.cancel_reason` (migration `c3d4e5f6a7b8`); the cancel endpoint accepts an optional body `{ reason }` (trimmed, empty→null, max 2000) and stays back-compat with no-body calls; reason stored on the order and mirrored into `AuditEvent.metadata_` (as `{ "reason": … }`) when present; `cancel_reason` exposed in the POS receipt/detail (`OrderCreateResponse`) and history (`OrderListItem`); stock-restore and shift cash-summary paths unchanged. Frontend `8d6d42a`: an inline optional cancel-reason form on the receipt (replaces `window.confirm`) — blank sends no body, non-empty sends `{ reason }`; the reason shows on the cancelled receipt (print-visible) and the history row; 4 POS i18n keys (Arabic uses English fallback). **Out of scope / future:** partial completed-order line-item void & refunds. |

### M12.5 — Shipping Module

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 12.5a | Storefront delivery address foundation | Claude | **Shipped** | Optional delivery address captured at storefront checkout and surfaced to the merchant (backend `90cfda1` + frontend `d2d4fc4`) — the smallest shipping foundation, **not** methods/zones/fees. Backend `90cfda1`: nullable `orders.shipping_address` (migration `d4e5f6a7b8c9`); optional `shipping_address` on `OrderCreateRequest` (trim, empty→null, max 2000); `create_order(..., shipping_address=None)` threading; public storefront `submit_order` passes `body.shipping_address`; exposed in `OrderDetailResponse`; delivery notes reuse the existing `notes` field; POS/donations/pledges untouched. Frontend `d2d4fc4`: optional delivery address + delivery notes textareas at checkout (blank values omitted; sends `shipping_address` and existing `notes`), and the dashboard order detail shows the shipping address when present; 3 i18n keys (Arabic uses English fallback). **Deferred:** shipping methods, zones, and fee calculation → M12.5b; fulfillment status chain → M12.6. |
| 12.5b | Shipping/delivery: methods, zones, fee calculation | Claude | **Shipped** | Tenant-configured flat shipping methods + server-resolved delivery fee (backend `190a72c` + frontend `e0bcfbf`). Backend `190a72c`: new `storefront_config.shipping` JSONB flat list of methods (`id`, `name`, `fee`, `active`) typed by `ShippingConfig` / `ShippingMethod`; migration `e5f6a7b8c9d0` also adds nullable `orders.shipping_fee` and `orders.shipping_method`; active-only methods exposed via public `GET /storefront/{slug}/config`; `OrderCreateRequest.shipping_method_id` resolves server-side (unknown/inactive/no-config → `422`); `total_amount = items_subtotal + shipping_fee`; fee/method persisted and surfaced on `OrderCreateResponse` and `OrderDetailResponse`; client-sent fee is never trusted; POS/donations/pledges untouched; 13 backend tests. Frontend `e0bcfbf`: dashboard delivery-methods editor (name + fee + active, stable client-generated ids, blank-name guard), checkout method selector + delivery-fee line + display-only grand-total preview submitting only `shipping_method_id`, server `shipping_fee` / `shipping_method` on success receipt + dashboard order detail, and 13 i18n keys (Arabic uses English fallback). **Deferred:** fulfillment status chain → M12.6. |

### M12.6 — Order Fulfillment Workflow

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 12.6a | Order fulfillment: pack → ship → deliver status chain | Claude | **Shipped** | Orthogonal storefront-order fulfillment chain (backend `b7ff3c8` + frontend `1defc24`). Backend `b7ff3c8`: nullable `orders.fulfillment_status` (migration `f6a7b8c9d0e1`; CHECK allows `NULL`, `packed`, `shipped`, `delivered`) separate from the existing `Order.status` machine; forward-only `NULL → packed → shipped → delivered` via admin `PATCH /tenants/me/orders/{id}/fulfillment` using dedicated `OrderFulfillmentTransitionRequest` / `OrderFulfillmentResponse`; gates (`422`) for non-storefront/POS, cancelled, `status` not in `pending`/`confirmed`, and skip/backward/terminal transitions; writes only `fulfillment_status`; logs `AuditEvent(action="fulfillment_transition")`; surfaced on `OrderListItem` and `OrderDetailResponse`; 13 backend tests. Frontend `1defc24`: storefront-only fulfillment badge in the order list + `Fulfillment` line and next-step "Mark as …" button in the detail; sends only `fulfillment_status`; hidden for POS/cancelled/non-pending-or-confirmed/delivered orders; updates detail + list row on success; 7 i18n keys (Arabic uses English fallback). **Deferred:** carrier/tracking, per-stage timestamps, partial refunds/returns, POS fulfillment. |

### M12.7 — Customer Order History

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 12.7a | Customer order history page | Claude | Not started | Dashboard page showing per-customer activity across online orders and POS sales. |

---

## M13 — Omnichannel Reporting & Polish

### M13.1 — Unified Reporting

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 13.1a | Unified sales reporting: online orders + POS sales in combined views | Claude | Not started | Single reporting view covering both channels. |

### M13.2 — Revenue Analytics

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 13.2a | Revenue analytics by channel, product, time period | Claude | Not started | Dashboard analytics extended with channel and product breakdowns. |

### M13.3 — POS Dashboard Widgets

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 13.3a | POS dashboard widgets: today's sales, top products | Claude | Not started | Dashboard home shows POS-specific KPI widgets. |

### M13.4 — Customer Repeat-Purchase Tracking

| # | Task | Primary Implementor | Status | DoD |
|---|------|-------|--------|-----|
| 13.4a | Customer repeat-purchase tracking | Claude | Not started | Analytics shows repeat vs new customer metrics. |

---

## V2 Optional Follow-Up (post-V2)

These items are explicitly out of scope for V2 and tracked here for future consideration.

| Item | Category |
|------|----------|
| `order_items` normalization (JSONB → relational) | Data cleanup |
| Discount/promo codes | Feature extension |
| Hold/park POS sale | POS power feature |
| POS offline queue | POS power feature |
| Terminal/register identity | POS power feature (multi-register) |
| Bulk product import/export (CSV) | Convenience |
| Subscription tier enforcement | Business/billing track |
| Customer lifetime value tracking | Analytics extension |
| Storefront SEO improvements | Marketing extension |
| POS multi-register support | Scale feature |

---

## V1 Residue (tracked separately from V2)

The following V1 items are not started or partially complete. They are NOT success criteria for any V2 milestone.

| Item | Source |
|------|--------|
| M6 P5+ — tenant admin team management UI | M6 Packet 5+ |
| M7 P5+ — pledge reminders, AI soft-limit notification, notification prefs UI, SES DKIM | M7 Packet 5+ |
| M8.9–8.13 — ALB/CF completion, CD pipeline, CloudWatch, Secrets Manager | M8 |
| M9 — hardening & launch prep (all tasks) | M9 |
| Bilingual Track D — admin pages, RTL, hero text Arabic | B Track D |
| Inventory UX consolidation (direct stock_qty edit bypass) | M5c tech debt |

---

## Summary

### V1

| Milestone | Tasks | Claude | Status |
|-----------|-------|--------|--------|
| M1 Auth & Tenancy | 11 | 11 | Complete |
| M2 Storefront | 10 | 10 | Complete |
| M3 Structured Capture | 10 | 10 | Complete |
| M4 AI Assistant | 10 | 10 | Complete |
| M5 Attribution & Dashboard | 9 | 9 | Complete |
| M5b Inventory / Stock v1 | 6 | 6 | Complete |
| M5c Inventory Movements | 19 | 19 | Complete |
| M6 Admin Panel | 7+ | 7+ | P1–P4 Complete |
| M7 Notifications | 7+ | 7+ | P1–P4 Complete |
| M8 Infra & DevOps | 14 | 14 | 8.1–8.8b Complete, 8.9–8.10 In Progress |
| M9 Hardening | 10 | 10 | Not Started |
| B — Bilingual / i18n | 24 | 24 | Tracks A–C Complete, Track D Not Started |
| **V1 Total** | **137+** | **137+** | |

### V2

| Milestone | Packets | Status |
|-----------|---------|--------|
| M10A — Foundations: Auth & Onboarding | 3 packets (M10A.1–A.3) | Core auth/onboarding shipped; role matrix + test fixture follow-ups remain |
| M10B — Foundations: POS Domain | 7 shipped + POS Sales Domain deferred | M10B.7 POS order cancel shipped |
| M11 — Selling & Payments MVP | 8 packets (M11.1–M11.8) | Complete — M11.1–M11.8 shipped (M11.6a payment status deferred) |
| M12 — Operations & Variants | 7 packets (M12.1–M12.7) | In progress — M12.1 product variants backend shipped (schema/RLS/CRUD, cross-table SKU/barcode uniqueness, order + POS variant price/stock, variant-aware cancel/restore); M12.2 variant UI + M12.2.1 POS visibility fix shipped; M12.3 POS shift management shipped (backend `cb6a3c0` + frontend `0f3c057`: `pos_shifts` table/RLS + one-open-shift-per-tenant index, `orders.shift_id`, cashier-gated current/open/close endpoints, hard open-shift gate on POS sales, cash-only reconciliation summary, and the POS shift banner/open-close forms/checkout gate); M12.4 POS cancel reason shipped (backend `78654d8` + frontend `8d6d42a`: optional `{ reason }` on the full-order cancel, `orders.cancel_reason`, audit metadata, receipt/history display — full-order cancel only, not line-item void); M12.5a storefront delivery address foundation shipped (backend `90cfda1` + frontend `d2d4fc4`: `orders.shipping_address`, optional request field + `OrderDetailResponse`, checkout address/notes fields, dashboard display); M12.5b shipping methods/fees shipped (backend `190a72c` + frontend `e0bcfbf`: `storefront_config.shipping` JSONB methods, server-resolved fee on `orders.shipping_fee` / `orders.shipping_method`, dashboard editor + checkout selector); M12.6 order fulfillment status chain shipped (backend `b7ff3c8` + frontend `1defc24`: orthogonal `orders.fulfillment_status` `NULL → packed → shipped → delivered`, admin fulfillment endpoint, list badge + detail next-step control); M12.7 not started |
| M13 — Omnichannel Reporting & Polish | 4 packets (M13.1–M13.4) | Not started |
| **V2 Total** | Packet count evolves as work ships and scope adjusts | |
