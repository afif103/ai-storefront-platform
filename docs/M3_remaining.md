# Remaining M3 — Structured Capture

## Status: COMPLETE

See [M3_orders_donations_pledges.md](M3_orders_donations_pledges.md) for full docs.

## Docs Sources

- `docs/05-backlog/backlog-v1.md` (tasks 3.1–3.10)
- `docs/05-backlog/milestones.md` (M3 acceptance criteria)
- `docs/01-architecture/data-model.md` (ERD + column conventions + status workflows)

## Dependencies

- M2 Storefront & Catalog: **Complete**
- Products table exists with `category_id`, `price_amount`, `currency` columns
- `visits` table exists (M2 task 2.8) — needed for UTM attribution linking

## Acceptance Criteria (from milestones.md)

- [x] Public order submission creates order with `pending` status
- [x] Public donation submission creates donation with amount in KWD `NUMERIC(12,3)`
- [x] Public pledge submission creates pledge with target date
- [x] Admin can transition order/donation/pledge through status workflow
- [x] Invalid status transitions rejected
- [x] Order numbers unique per tenant (auto-generated)
- [x] `visit_id` links to visit record for attribution

## Task Checklist

### Database Layer

- [x] **3.1 — `orders` table + RLS + migration**
  - Columns: `id` (UUID PK), `tenant_id` (FK), `order_number` (TEXT), `product_id` (FK → products, nullable), `customer_name` (TEXT), `customer_phone` (TEXT), `customer_email` (TEXT), `items` (JSONB), `total_amount` (NUMERIC(12,3)), `currency` (TEXT, default `'KWD'`), `payment_link` (TEXT), `payment_notes` (TEXT), `status` (TEXT + CHECK), `notes` (TEXT), `visit_id` (FK → visits, nullable), `created_at`, `updated_at`
  - Status values: `pending`, `confirmed`, `fulfilled`, `cancelled`
  - Constraint: `UNIQUE(tenant_id, order_number)`
  - Indexes: `(tenant_id, created_at DESC)`, `(tenant_id, status)`, `(tenant_id, order_number)` UNIQUE
  - RLS: ENABLE + FORCE, SELECT/INSERT/UPDATE/DELETE policies on `current_setting('app.current_tenant', true)::uuid`
  - GRANT SELECT, INSERT, UPDATE, DELETE TO `app_user`
  - JSONB items schema: `[{"catalog_item_id": "uuid", "name": "...", "qty": N, "unit_price": "1.500", "currency": "KWD", "subtotal": "3.000"}]`

- [x] **3.2 — `donations` table + RLS + migration**
  - Columns: `id` (UUID PK), `tenant_id` (FK), `donation_number` (TEXT), `product_id` (FK → products, nullable), `donor_name` (TEXT), `donor_phone` (TEXT), `donor_email` (TEXT), `amount` (NUMERIC(12,3)), `currency` (TEXT, default `'KWD'`), `campaign` (TEXT, nullable), `receipt_requested` (BOOLEAN, default false), `payment_link` (TEXT), `payment_notes` (TEXT), `status` (TEXT + CHECK), `notes` (TEXT), `visit_id` (FK → visits, nullable), `created_at`, `updated_at`
  - Status values: `pending`, `received`, `receipted`, `cancelled`
  - Constraint: `UNIQUE(tenant_id, donation_number)`
  - Indexes: `(tenant_id, created_at DESC)`, `(tenant_id, campaign)`
  - RLS: same pattern as orders
  - GRANT to `app_user`

- [x] **3.3 — `pledges` table + RLS + migration**
  - Columns: `id` (UUID PK), `tenant_id` (FK), `pledge_number` (TEXT), `product_id` (FK → products, nullable), `pledgor_name` (TEXT), `pledgor_phone` (TEXT), `pledgor_email` (TEXT), `amount` (NUMERIC(12,3)), `currency` (TEXT, default `'KWD'`), `target_date` (DATE), `fulfilled_amount` (NUMERIC(12,3), default 0), `payment_link` (TEXT), `payment_notes` (TEXT), `status` (TEXT + CHECK), `notes` (TEXT), `visit_id` (FK → visits, nullable), `created_at`, `updated_at`
  - Status values: `pledged`, `partially_fulfilled`, `fulfilled`, `lapsed`
  - Constraint: `UNIQUE(tenant_id, pledge_number)`
  - Indexes: `(tenant_id, status, target_date)`
  - RLS: same pattern as orders
  - GRANT to `app_user`

- [x] **3.4 — `utm_events` table + RLS + migration**
  - Columns: `id` (UUID PK), `tenant_id` (FK), `visit_id` (FK → visits), `event_type` (TEXT + CHECK), `event_ref_id` (UUID — polymorphic FK to order/donation/pledge), `created_at`
  - Event types: `page_view`, `order`, `donation`, `pledge`
  - RLS: same pattern
  - GRANT to `app_user`

### API Layer

- [x] **3.5 — Public order submission endpoint**
  - `POST /storefront/{slug}/orders` (anonymous, slug-scoped via `get_db_with_slug`)
  - Validates `items` against catalog (product exists, is_active, belongs to tenant)
  - Calculates `total_amount` from items (sum of `qty * unit_price`)
  - Auto-generates `order_number` (ORD-00001 pattern, tenant-scoped)
  - Sets `status = 'pending'`
  - Links `visit_id` if provided (validates visit belongs to tenant)
  - Creates `utm_events` record if `visit_id` present
  - Returns order ID + order number

- [x] **3.6 — Public donation submission endpoint**
  - `POST /storefront/{slug}/donations` (anonymous, slug-scoped)
  - Validates `amount` as NUMERIC(12,3) > 0
  - Auto-generates `donation_number` (DON-00001 pattern)
  - Sets `status = 'pending'`
  - Optional `campaign`, `receipt_requested`, `product_id`
  - Links `visit_id` if provided
  - Creates `utm_events` record if `visit_id` present

- [x] **3.7 — Public pledge submission endpoint**
  - `POST /storefront/{slug}/pledges` (anonymous, slug-scoped)
  - Validates `target_date` is in the future
  - Validates `amount` as NUMERIC(12,3) > 0
  - Auto-generates `pledge_number` (PLG-00001 pattern)
  - Sets `status = 'pledged'`, `fulfilled_amount = 0`
  - Links `visit_id` if provided
  - Creates `utm_events` record if `visit_id` present

- [x] **3.8 — Admin status transition endpoints**
  - `PATCH /tenants/me/orders/{id}/status` (admin+)
  - `PATCH /tenants/me/donations/{id}/status` (admin+)
  - `PATCH /tenants/me/pledges/{id}/status` (admin+)
  - Validates transition is legal:
    - Orders: `pending → confirmed → fulfilled`, `pending → cancelled`, `confirmed → cancelled`
    - Donations: `pending → received → receipted`, `pending → cancelled`, `received → cancelled`
    - Pledges: `pledged → partially_fulfilled → fulfilled`, `pledged → lapsed`, `partially_fulfilled → lapsed`
  - Invalid transitions return 422 with allowed transitions listed
  - `updated_at` set on transition

- [x] **3.9 — Order number auto-generation**
  - Sequential per tenant: `ORD-00001`, `DON-00001`, `PLG-00001`
  - Tenant-scoped uniqueness via `UNIQUE(tenant_id, order_number)` constraint
  - Implementation: `SELECT COALESCE(MAX(...))+1` or sequence per prefix, within same transaction
  - Must be race-safe (use `SELECT ... FOR UPDATE` or advisory lock)

- [x] **3.10 — Integration tests**
  - `@pytest.mark.m3` marker
  - Test files: `test_m3_integration.py`, `test_m3_numbering.py`
  - Coverage:
    - Public submission creates record with correct status + auto-generated number
    - Items validated against catalog (invalid product → 422)
    - Total amount calculated correctly
    - Status transitions: valid accepted, invalid rejected with 422
    - Order numbers increment correctly within tenant
    - UTM visit linking works
    - Cross-tenant isolation (skip if superuser — note in test)
    - Admin-only write access enforced (member cannot PATCH status)

## Status Workflow Reference

```
Orders:     pending → confirmed → fulfilled
                  ↘ cancelled  ↗ cancelled

Donations:  pending → received → receipted
                  ↘ cancelled  ↗ cancelled

Pledges:    pledged → partially_fulfilled → fulfilled
                  ↘ lapsed               ↗ lapsed
```

## Key Design Decisions

- **Separate tables** for orders/donations/pledges (not polymorphic) — different status workflows, different fields
- **JSONB for order items** — single INSERT, no join table for MVP. Snapshot semantics (product name/price captured at order time)
- **TEXT + CHECK** for status (not PG ENUM) — easier migration when adding statuses
- **Auto-number format**: `ORD-NNNNN`, `DON-NNNNN`, `PLG-NNNNN` — zero-padded 5 digits, tenant-scoped
- **Currency**: each record stores its own `currency` (default `'KWD'`), not derived from tenant at query time — captures currency at submission time
