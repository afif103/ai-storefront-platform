# M3 — Structured Capture (Orders, Donations, Pledges)

## Overview

M3 adds public submission endpoints for orders, donations, and pledges, plus
admin status-transition endpoints. Each record gets a tenant-scoped
auto-generated number (ORD-00001, DON-00001, PLG-00001). Submissions optionally
link to a visit record for UTM attribution via the `utm_events` table.

---

## Data Model

### Tables (migration `c4d5e6f7a8b9`)

| Table | Key Columns | Status Values |
|-------|-------------|---------------|
| `orders` | `order_number`, `items` (JSONB), `total_amount` NUMERIC(12,3), `currency` | pending, confirmed, fulfilled, cancelled |
| `donations` | `donation_number`, `amount` NUMERIC(12,3), `campaign`, `receipt_requested` | pending, received, receipted, cancelled |
| `pledges` | `pledge_number`, `amount` NUMERIC(12,3), `target_date` DATE, `fulfilled_amount` | pledged, partially_fulfilled, fulfilled, lapsed |
| `utm_events` | `visit_id` FK, `event_type` (order/donation/pledge/page_view), `event_ref_id` UUID | — |

All tables have `tenant_id` with RLS (NULLIF-guarded GUC cast), indexes on
`(tenant_id, created_at DESC)` and `(tenant_id, status)`, and GRANT to `app_user`.

### Auto-Numbering

Race-safe via `pg_advisory_xact_lock(hashtext(tenant_id:PREFIX))`.
Pattern: `SELECT MAX(CAST(SUBSTRING(col FROM 'PFX-([0-9]+)') AS INTEGER)) + 1`.
Zero-padded to 5 digits, tenant-scoped unique constraint.

---

## Public Endpoints (slug-scoped, no auth)

### `POST /api/v1/storefront/{slug}/orders`

```json
{
  "customer_name": "Ahmad",
  "customer_phone": "+96512345678",
  "items": [{"catalog_item_id": "product-uuid", "qty": 2}],
  "payment_notes": "Bank transfer",
  "visit_id": "visit-uuid"
}
```

**201 Response**:
```json
{
  "id": "order-uuid",
  "order_number": "ORD-00001",
  "total_amount": "10.500",
  "currency": "KWD",
  "status": "pending",
  "items": [{"catalog_item_id": "...", "name": "Widget", "qty": 2, "unit_price": "5.250", "currency": "KWD", "subtotal": "10.500"}],
  "created_at": "2026-03-01T12:00:00Z"
}
```

Items are validated against the catalog (product must exist, be active, and
belong to the tenant). Price and name are snapshotted into the JSONB at order
time. `total_amount` is computed as `sum(qty * unit_price)`. Currency comes from
`tenant.default_currency` (fallback `KWD`).

### `POST /api/v1/storefront/{slug}/donations`

```json
{
  "donor_name": "Fatima",
  "donor_phone": "+96598765432",
  "amount": "10.000",
  "campaign": "Ramadan 2026",
  "receipt_requested": true,
  "visit_id": "visit-uuid"
}
```

**201 Response**:
```json
{
  "id": "donation-uuid",
  "donation_number": "DON-00001",
  "amount": "10.000",
  "currency": "KWD",
  "status": "pending",
  "created_at": "2026-03-01T12:00:00Z"
}
```

### `POST /api/v1/storefront/{slug}/pledges`

```json
{
  "pledgor_name": "Ali",
  "pledgor_phone": "+96555555555",
  "amount": "100.000",
  "target_date": "2026-06-01",
  "visit_id": "visit-uuid"
}
```

**201 Response**:
```json
{
  "id": "pledge-uuid",
  "pledge_number": "PLG-00001",
  "amount": "100.000",
  "currency": "KWD",
  "status": "pledged",
  "created_at": "2026-03-01T12:00:00Z"
}
```

`target_date` must be in the future (UTC). Returns 422 if past.

### UTM Attribution

When `visit_id` is provided, the endpoint validates it belongs to the tenant
and inserts a row into `utm_events` with `event_type` = `order`/`donation`/`pledge`
and `event_ref_id` = the new record's ID. Invalid `visit_id` returns 422.

---

## Admin Endpoints (tenant-scoped, role: admin+)

### `PATCH /api/v1/tenants/me/orders/{id}/status`
### `PATCH /api/v1/tenants/me/donations/{id}/status`
### `PATCH /api/v1/tenants/me/pledges/{id}/status`

```json
{"status": "confirmed"}
```

**200 Response**: full record with updated `status` and `updated_at`.

Incoming status is normalized (`strip().lower()`).

### Allowed Transitions

```
Orders:     pending → confirmed → fulfilled
                  ↘ cancelled  ↗ cancelled

Donations:  pending → received → receipted
                  ↘ cancelled  ↗ cancelled

Pledges:    pledged → partially_fulfilled → fulfilled
                  ↘ lapsed               ↗ lapsed
```

| Entity | From | Allowed Next |
|--------|------|-------------|
| Order | pending | confirmed, cancelled |
| Order | confirmed | fulfilled, cancelled |
| Order | fulfilled | _(terminal)_ |
| Order | cancelled | _(terminal)_ |
| Donation | pending | received, cancelled |
| Donation | received | receipted, cancelled |
| Donation | receipted | _(terminal)_ |
| Donation | cancelled | _(terminal)_ |
| Pledge | pledged | partially_fulfilled, lapsed |
| Pledge | partially_fulfilled | fulfilled, lapsed |
| Pledge | fulfilled | _(terminal)_ |
| Pledge | lapsed | _(terminal)_ |

### Invalid Transition (422)

```json
{
  "detail": {
    "message": "Cannot transition order from 'pending' to 'fulfilled'",
    "allowed": ["confirmed", "cancelled"]
  }
}
```

---

## Testing

```bash
# M3 tests only (20 tests)
cd backend && python -m pytest -q -m m3

# Full suite (72 pass, 1 skip)
cd backend && python -m pytest -q
```

Test file: `tests/test_m3_integration.py` — covers public submissions,
auto-numbering increments, UTM event creation, valid and invalid status
transitions, cancellation flows, and input validation (past dates, unknown
products, invalid visit IDs).

Numbering tests: `tests/test_m3_numbering.py` — covers first-number generation,
increment, and tenant isolation for all three prefixes.
