# Data Model

## Tenancy Model
Shared database, shared schema. All tenant-scoped tables carry `tenant_id UUID NOT NULL` with RLS enforced. Global tables (`tenants`, `users`, `plans`) have no `tenant_id` and no RLS.

`app.current_tenant` is set via `SET LOCAL app.current_tenant = '<uuid>';` in middleware at the start of every DB transaction. See `tenancy-rls.md` for full details.

---

## ERD (Text)

```
┌──────────────┐       ┌──────────────┐       ┌─────────────────┐
│   tenants    │       │    users     │       │     plans       │
│──────────────│       │──────────────│       │─────────────────│
│ id PK        │       │ id PK        │       │ id PK           │
│ name         │       │ cognito_sub  │       │ name            │
│ slug UNIQUE  │       │ email UNIQUE │       │ ai_token_quota  │
│ plan_id FK ──│───────│──────────────│──────▶│ price_amount    │ NUMERIC(12,3)
│ is_active    │       │ full_name    │       │ currency        │ default 'KWD'
│ created_at   │       │ is_active    │       │ max_members     │
│ updated_at   │       │ created_at   │       └─────────────────┘
└──────┬───────┘       │ updated_at   │
       │               └──────┬───────┘
       │                      │
       ▼                      ▼
┌─────────────────────┐
│  tenant_members     │
│─────────────────────│
│ id PK               │
│ tenant_id FK  ──────│── RLS
│ user_id FK          │
│ role TEXT+CHECK      │  (owner/admin/member)
│ status TEXT+CHECK    │  (active/invited/removed)
│ invited_at          │
│ joined_at           │
│ UNIQUE(tenant_id,   │
│        user_id)     │
└─────────────────────┘
       │
       │ tenant_id present on all below (RLS enforced)
       ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│ storefront_config   │     │  catalog_items       │     │   media_assets      │
│─────────────────────│     │─────────────────────│     │─────────────────────│
│ id PK               │     │ id PK               │     │ id PK               │
│ tenant_id FK UNIQUE │     │ tenant_id FK        │     │ tenant_id FK        │
│ logo_s3_key         │     │ type TEXT+CHECK      │     │ catalog_item_id FK  │ nullable
│ primary_color       │     │  (product/service/   │     │ entity_type TEXT    │ (catalog_item/
│ secondary_color     │     │   project)           │     │                     │  order/donation/
│ hero_text           │     │ name                │     │                     │  proof)
│ custom_css JSONB    │     │ description         │     │ entity_id UUID      │ polymorphic FK
│ created_at          │     │ price_amount NUM    │     │ s3_key              │
│ updated_at          │     │ currency TEXT       │     │ file_name           │
└─────────────────────┘     │  default 'KWD'      │     │ content_type        │
                            │ is_active           │     │ sort_order INT      │
                            │ sort_order          │     │ created_at          │
                            │ metadata JSONB      │     │ INDEX(tenant_id,    │
                            │ created_at          │     │   entity_type,      │
                            │ updated_at          │     │   entity_id)        │
                            │ INDEX(tenant_id,    │     └─────────────────────┘
                            │       type,         │
                            │       is_active)    │
                            └──────────┬──────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│      orders         │  │    donations        │  │     pledges         │
│─────────────────────│  │─────────────────────│  │─────────────────────│
│ id PK               │  │ id PK               │  │ id PK               │
│ tenant_id FK        │  │ tenant_id FK        │  │ tenant_id FK        │
│ order_number        │  │ donation_number     │  │ pledge_number       │
│ catalog_item_id FK  │  │ catalog_item_id FK  │  │ catalog_item_id FK  │
│ customer_name       │  │ donor_name          │  │ pledgor_name        │
│ customer_phone      │  │ donor_phone         │  │ pledgor_phone       │
│ customer_email      │  │ donor_email         │  │ pledgor_email       │
│ items JSONB         │  │ amount NUM(12,3)    │  │ amount NUM(12,3)    │
│ total_amount NUM    │  │ currency TEXT       │  │ currency TEXT       │
│ currency TEXT       │  │  default 'KWD'      │  │  default 'KWD'      │
│ payment_link        │  │ campaign            │  │ target_date DATE    │
│ payment_notes       │  │ receipt_requested   │  │ payment_link        │
│ status TEXT+CHECK   │  │ payment_link        │  │ payment_notes       │
│ notes               │  │ payment_notes       │  │ status TEXT+CHECK   │
│ created_at          │  │ status TEXT+CHECK   │  │ notes               │
│ updated_at          │  │ notes               │  │ fulfilled_amount    │
│ UNIQUE(tenant_id,   │  │ created_at          │  │  NUM(12,3)          │
│        order_number)│  │ updated_at          │  │ created_at          │
└─────────────────────┘  │ UNIQUE(tenant_id,   │  │ updated_at          │
                         │   donation_number)  │  │ UNIQUE(tenant_id,   │
                         └─────────────────────┘  │   pledge_number)    │
                                                  └─────────────────────┘

Status values (TEXT + CHECK constraint):
  orders:    pending → confirmed → fulfilled → cancelled
  donations: pending → received → receipted → cancelled
  pledges:   pledged → partially_fulfilled → fulfilled → lapsed

┌─────────────────────┐     ┌─────────────────────┐
│      visits         │     │    utm_events       │
│─────────────────────│     │─────────────────────│
│ id PK               │     │ id PK               │
│ tenant_id FK        │     │ tenant_id FK        │
│ session_id          │     │ visit_id FK         │
│ ip_hash TEXT        │     │ event_type TEXT+CHK │ (page_view/order/donation/pledge)
│ user_agent          │     │ event_ref_id UUID   │ polymorphic FK
│ utm_source          │     │ created_at          │
│ utm_medium          │     └─────────────────────┘
│ utm_campaign        │
│ utm_content         │
│ utm_term            │
│ landed_at           │
│ INDEX(tenant_id,    │
│       landed_at)    │
└─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│ ai_conversations    │     │   ai_usage_log      │
│─────────────────────│     │─────────────────────│
│ id PK               │     │ id PK               │
│ tenant_id FK        │     │ tenant_id FK        │
│ visitor_session_id  │     │ user_id FK nullable  │
│ started_at          │     │ conversation_id FK   │
│ messages JSONB      │     │ model TEXT           │
│ created_at          │     │ tokens_in INT        │
│ updated_at          │     │ tokens_out INT       │
│ INDEX(tenant_id,    │     │ cost_usd NUM(10,6)  │
│       created_at)   │     │ created_at          │
└─────────────────────┘     │ INDEX(tenant_id,    │
                            │       created_at)   │
                            └─────────────────────┘

┌──────────────────────────┐
│ notification_preferences │
│──────────────────────────│
│ id PK                    │
│ tenant_id FK UNIQUE      │
│ email_enabled BOOL       │
│ telegram_enabled BOOL    │
│ telegram_bot_token_ref   │  (Secrets Manager ARN, not plaintext)
│ telegram_chat_id         │
│ created_at               │
│ updated_at               │
└──────────────────────────┘
```

---

## Design Decisions

### Separate Tables for Orders / Donations / Pledges (not a single table with type discriminator)

**Rationale**: the three record types have different status workflows, different required fields, and different business rules:

| | Orders | Donations | Pledges |
|---|---|---|---|
| Has line items? | Yes (JSONB) | No (single amount) | No (single amount) |
| Has `campaign`? | No | Yes | Optional |
| Has `target_date`? | No | No | Yes |
| Has `fulfilled_amount`? | No | No | Yes (partial fulfilment tracking) |
| Status values | 4 states | 4 states (different) | 4 states (different) |

A single polymorphic table would require many nullable columns and conditional validation. Separate tables keep each schema tight, each status workflow honest, and each migration simple.

**Tradeoff**: cross-type reporting ("all transactions this month") requires a UNION query or a materialised view. Acceptable for MVP — if reporting becomes complex, add a `transactions_view` later.

### JSONB for Order Line Items

`orders.items` stores line items as JSONB:

```json
[
  {"catalog_item_id": "uuid", "name": "Widget", "qty": 2, "unit_price": "1.500", "currency": "KWD", "subtotal": "3.000"},
  {"catalog_item_id": "uuid", "name": "Gadget", "qty": 1, "unit_price": "5.250", "currency": "KWD", "subtotal": "5.250"}
]
```

**Why**: fastest path for MVP. Avoids an `order_items` join table, simplifies order creation to a single INSERT.

**Future normalisation path**: when we need per-item status tracking, inventory deduction, or item-level analytics, introduce an `order_items` table and backfill from JSONB. The JSONB column remains as a snapshot (append-only, never updated).

### Single `catalog_items` Table with Type Discriminator

Products, services, and charity projects share enough structure (name, description, price, image, sort order) that a single table with `type TEXT CHECK (type IN ('product','service','project'))` is cleaner than three tables. Type-specific attributes go in `metadata JSONB`.

### `media_assets` — Polymorphic Media Table

Rather than `image_s3_key` on `catalog_items` (single image only), a dedicated `media_assets` table supports multiple images/files per entity:

- `catalog_item_id FK` for direct catalog lookups (nullable — media can attach to other entities).
- `entity_type` + `entity_id` for polymorphic attachment to orders, donations, proofs, etc.
- `sort_order` controls display sequence.
- All S3 keys follow `{tenant_id}/` prefix rule. Presigned URLs generated only after tenant ownership check.

### Status Fields: TEXT + CHECK (not PostgreSQL ENUMs)

**Decision**: use `TEXT` columns with `CHECK` constraints instead of `CREATE TYPE ... AS ENUM`.

**Why**: PostgreSQL enums cannot have values removed, and adding values requires `ALTER TYPE ... ADD VALUE` which cannot run inside a transaction. This makes migrations painful when status workflows evolve. `TEXT + CHECK` gives the same data integrity with simpler migration paths:

```sql
-- Adding a new status: simple ALTER
ALTER TABLE orders DROP CONSTRAINT orders_status_check;
ALTER TABLE orders ADD CONSTRAINT orders_status_check
    CHECK (status IN ('pending','confirmed','fulfilled','cancelled','refunded'));

-- vs ENUM: cannot remove values, ADD VALUE can't be transactional
```

**Tradeoff**: slightly less self-documenting in `\d` output. Mitigated by keeping status values documented here and validated in Pydantic schemas.

---

## Column Conventions

| Convention | Rule |
|---|---|
| Primary keys | `id UUID DEFAULT gen_random_uuid()` |
| Monetary amounts (KWD) | `NUMERIC(12,3)` — three decimal places for KWD fils |
| Currency field | `currency TEXT NOT NULL DEFAULT 'KWD'` alongside every amount column |
| AI cost tracking (USD) | `NUMERIC(10,6)` — six decimal places for sub-cent precision |
| Timestamps | `created_at TIMESTAMPTZ DEFAULT now()`, `updated_at TIMESTAMPTZ` (trigger or app-level) |
| Status/type fields | `TEXT + CHECK` constraint (see rationale above) |
| Soft deletes | Not used in MVP. Use `is_active BOOL` where needed; hard delete otherwise |
| Tenant FK | `tenant_id UUID NOT NULL REFERENCES tenants(id)` on all tenant-scoped tables |

---

## Privacy: IP Hashing

`visits.ip_hash` stores a salted hash of the visitor's IP address, **not** the raw IP.

- Hash algorithm: SHA-256 with a rotating salt.
- Salt rotation: new salt generated monthly; old salt kept for 30 days for deduplication window, then deleted.
- Salt storage: AWS Secrets Manager, key `/{env}/ip-hash-salt/current` and `/{env}/ip-hash-salt/previous`.
- This reduces re-identification risk while preserving basic uniqueness for analytics deduplication.

---

## Index Strategy

Every tenant-scoped table gets at minimum:

```sql
CREATE INDEX ix_{table}_tenant ON {table} (tenant_id);
```

Additional indexes per access pattern:

| Table | Index | Reason |
|---|---|---|
| `orders` | `(tenant_id, created_at DESC)` | List orders by recency |
| `orders` | `(tenant_id, status)` | Filter by status |
| `orders` | `(tenant_id, order_number)` UNIQUE | Lookup by order number |
| `donations` | `(tenant_id, created_at DESC)` | List by recency |
| `donations` | `(tenant_id, campaign)` | Filter by campaign |
| `pledges` | `(tenant_id, status, target_date)` | Due-soon pledges query |
| `catalog_items` | `(tenant_id, type, is_active)` | Storefront listing |
| `media_assets` | `(tenant_id, entity_type, entity_id)` | Lookup media for an entity |
| `media_assets` | `(catalog_item_id)` | Direct catalog media lookup |
| `visits` | `(tenant_id, landed_at DESC)` | Analytics time range |
| `ai_usage_log` | `(tenant_id, created_at DESC)` | Usage dashboard |
| `users` | `(cognito_sub)` UNIQUE | JWT sub → user lookup |
| `tenants` | `(slug)` UNIQUE | Storefront URL routing |

---

## Unique Constraints

| Table | Constraint | Purpose |
|---|---|---|
| `tenants` | `UNIQUE(slug)` | One subdomain per tenant |
| `users` | `UNIQUE(email)` | One account per email (MVP — see note) |
| `users` | `UNIQUE(cognito_sub)` | Maps 1:1 to Cognito |
| `tenant_members` | `UNIQUE(tenant_id, user_id)` | User joins a tenant once |
| `orders` | `UNIQUE(tenant_id, order_number)` | Order numbers unique per tenant |
| `donations` | `UNIQUE(tenant_id, donation_number)` | Donation numbers unique per tenant |
| `pledges` | `UNIQUE(tenant_id, pledge_number)` | Pledge numbers unique per tenant |
| `storefront_config` | `UNIQUE(tenant_id)` | One config per tenant |
| `notification_preferences` | `UNIQUE(tenant_id)` | One preference set per tenant |

> **Note on `UNIQUE(email)`**: sufficient for MVP where one person = one account across tenants. If we later need to support multiple accounts per email (e.g., personal vs work), drop the email uniqueness and rely solely on `UNIQUE(cognito_sub)` as the identity anchor. The `tenant_members` join table already supports one user belonging to multiple tenants.

---

## RLS Checklist Reminder

Every tenant-scoped table in this model must follow the checklist in `tenancy-rls.md`:

1. `tenant_id UUID NOT NULL REFERENCES tenants(id)` column.
2. Index on `tenant_id` (at minimum; composite indexes above satisfy this).
3. `ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;`
4. `ALTER TABLE {t} FORCE ROW LEVEL SECURITY;`
5. `CREATE POLICY tenant_isolation ON {t} USING (tenant_id = current_setting('app.current_tenant')::uuid);`
6. `CREATE POLICY tenant_insert ON {t} FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);`
7. SQLAlchemy model inherits `TenantScopedBase`.
8. Cross-tenant isolation test added.

Global tables (`tenants`, `users`, `plans`) have NO RLS. Access to global tables from tenant-facing endpoints must always go through `tenant_members` filtered by current tenant (see Safety Rule #5 in `tenancy-rls.md`).
