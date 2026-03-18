# Backlog v1

Ordered epics M1–M9. All implementation is through Claude Code.

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
| 8.7 | Provision S3 bucket (Block Public Access, versioning) | Claude | **DONE** | Bucket `saas-media-prod-701893741240` in `ap-southeast-1`. Block Public Access all ON, versioning enabled, SSE-S3 (AES256), lifecycle transition to STANDARD_IA after 90 days. S3 object policy attached to shared ECS task role (`S3MediaAccess`), backend task def updated with `S3_BUCKET` (rev 2). CORS deferred until frontend domain is known. |
| 8.8a | Create ECR repository + OIDC + CI image push | Claude | **DONE** | ECR repo exists in ap-southeast-1, GitHub OIDC role created, CI pushes image on push to main |
| 8.8b | Create ECS cluster + task definitions + deploy services | Claude | **DONE** | P1 repo contract (env-contract, task-def templates, runbook). P2 cluster/roles/secrets/logs provisioned. P3 task defs registered and backend + worker services running in `saas-cluster`. Worker fix: Celery requires `ssl_cert_reqs=required` in `rediss://` URL, so `/prod/redis-url` was updated. Backend HEALTHY, worker Celery ready. Image pinned to `ecece62`. Services are private-only; public reachability comes later in 8.9. |
| 8.9 | Set up ALB + CloudFront + WAF | Claude | In progress | P1: ALB foundation (internet-facing ALB, target group, public HTTP endpoint). P2: ACM cert + HTTPS listener for `api.ramitestapp.top`, HTTP :80→HTTPS redirect. P3a: origin hostname `origin-api.ramitestapp.top` live with SNI cert on ALB, viewer cert issued in us-east-1. P3b: WAF WebACL `saas-api-waf` created in us-east-1 (CLOUDFRONT scope, 4 rules, 1102 WCU). P3c: CloudFront distribution `EQPDDTZHFIMYE` (`d1zgvjjy4fkyou.cloudfront.net`) deployed with WAF attached, origin `origin-api.ramitestapp.top` over HTTPS, proxy verified. Note: `api.ramitestapp.top` still resolves to ALB today. Remaining: DNS cutover (P3d), ALB hardening (P3e), CORS/domain wiring (P4). Domain: `ramitestapp.top` on Namecheap BasicDNS. |
| 8.10 | Set up Vercel project with wildcard subdomain | Claude | In progress | Demo P1: Frontend deployed to Vercel at `https://ai-storefront-platform.vercel.app`. Backend CORS configured (`saas-backend:3`). Demo P2a: `COGNITO_MOCK=true` enabled on ECS (`saas-backend:4`), dev token login works, dashboard health widget verified. Frontend fix: dev-login token whitespace stripping committed. Demo P2b: Tenant `rami-demo-store` created (PHP currency), 2 categories, 3 products, storefront config set. Demo images: 3 product images uploaded via existing media pipeline (presigned PUT to S3), public storefront response verified with correct `image_url` per product, storefront image-fit polish (`object-contain`) committed and deployed. Groq AI chat: `/prod/ai-api-key` updated with real Groq key in Secrets Manager, `openai>=1.60,<2` added to backend dependencies, backend image rebuilt and pushed to ECR (tag `4642e4a`), task definition updated to `saas-backend:6` with `AI_PROVIDER=groq`, `AI_MODEL=llama-3.3-70b-versatile`, storefront AI chat endpoint verified returning real AI responses (Llama 3.3 70B via Groq), token usage logged. Remaining: custom domain `app.ramitestapp.top` (Demo P3, optional). |
| 8.11 | Set up GitHub Actions CD (deploy to staging + production) | Claude | Not started | Staging auto-deploy on main. Production via manual workflow dispatch. |
| 8.12 | Set up CloudWatch log groups + alarms | Claude | Not started | Log groups for backend/worker/audit. Alarms: CPU, connections, 5xx. |
| 8.13 | Populate Secrets Manager with all secrets | Claude | Not started | All secrets per `security.md §3` table |

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

## Summary

| Milestone | Tasks | Claude |
|-----------|-------|--------|
| M1 Auth & Tenancy | 11 | 11 |
| M2 Storefront | 10 | 10 |
| M3 Structured Capture | 10 | 10 |
| M4 AI Assistant | 10 | 10 |
| M5 Attribution & Dashboard | 9 | 9 |
| M5b Inventory / Stock v1 | 6 | 6 |
| M6 Admin Panel | 7 | 7 |
| M7 Notifications | 7 | 7 |
| M8 Infra & DevOps | 14 | 14 |
| M9 Hardening | 10 | 10 |
| **Total** | **94** | **94** |
