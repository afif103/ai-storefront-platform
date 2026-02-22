# Remaining M2 — Storefront & Catalog

## Docs Sources

- `docs/05-backlog/backlog-v1.md` (tasks 2.1–2.10)
- `docs/05-backlog/milestones.md` (M2 acceptance criteria)
- `docs/01-architecture/data-model.md` (ERD + column conventions)
- `docs/04-api/endpoints.md` (implemented endpoint reference)

## Done (Matched)

| Backlog | Implemented As | Notes |
|---------|---------------|-------|
| 2.2 `catalog_items` table + RLS | `categories` + `products` tables (migration 002) | Separate tables instead of single discriminated table. Both have RLS + tenant_id indexes. |
| 2.5 Catalog CRUD API | `categories.py` + `products.py` routes | Full CRUD with cursor pagination. Admin role for writes, member for reads. |
| 2.7 Public storefront page (basic) | `storefront/[slug]/page.tsx` + `public_storefront.py` | Anonymous category/product listing via slug-based tenant resolution. No branding yet. |
| 2.9 Vercel wildcard subdomain | Kimi's task — not in scope for Claude. | |

## Remaining M2 Items

- [ ] **2.1 — `storefront_config` table + RLS + migration**
- [ ] **2.3 — `media_assets` table + RLS + migration**
- [ ] **2.4 — Storefront config API (GET/PUT)**
- [ ] **2.6 — Presigned URL upload/download endpoints**
- [ ] **2.7 (gap) — Integrate branding into public storefront**
- [ ] **2.8 — UTM visit capture endpoint + `visits` table**
- [ ] **2.10 — M2 integration tests**

## Acceptance Criteria

### 2.1 — `storefront_config` table

- Table columns per data-model.md: `id`, `tenant_id UNIQUE`, `logo_s3_key`, `primary_color`, `secondary_color`, `hero_text`, `custom_css JSONB`, timestamps.
- RLS: ENABLE + FORCE, SELECT/INSERT/UPDATE policies using `current_setting('app.current_tenant')::uuid`.
- Index on `tenant_id` (covered by UNIQUE constraint).
- SQLAlchemy model inherits `TenantScopedBase`.
- Alembic migration with reversible `downgrade()`.

### 2.3 — `media_assets` table

- Columns per data-model.md: `id`, `tenant_id`, `catalog_item_id FK nullable` (SET NULL on delete), `entity_type TEXT`, `entity_id UUID`, `s3_key`, `file_name`, `content_type`, `sort_order INT`, `created_at`.
- Composite index on `(tenant_id, entity_type, entity_id)`.
- Index on `catalog_item_id`.
- RLS: same pattern as storefront_config.
- SQLAlchemy model inherits `TenantScopedBase`.

### 2.4 — Storefront config API

- `GET /api/v1/tenants/me/storefront` — returns config or empty defaults. Auth: member.
- `PUT /api/v1/tenants/me/storefront` — upserts config (INSERT ON CONFLICT UPDATE). Auth: admin.
- Logo stored at S3 key under `{tenant_id}/` prefix.
- Pydantic request/response schemas.

### 2.6 — Presigned URL endpoints

- `POST /api/v1/tenants/me/media/upload-url` — generates a PUT presigned URL. Auth: admin.
  - Validates `content_type` against allowlist (image/jpeg, image/png, image/webp, application/pdf).
  - Max 10 MB via presigned URL condition.
  - S3 key follows `{tenant_id}/media/{media_id}/{file_name}` pattern.
  - Creates `media_assets` row, returns `{ upload_url, s3_key, media_id, expires_in }`.
- `GET /api/v1/tenants/me/media/{media_id}/url` — generates a GET presigned URL (15-min expiry). Auth: member.
  - Verifies tenant owns the media_asset via RLS before signing.
- Requires S3 service layer (`app/services/s3_service.py`) with boto3 client.

### 2.7 (gap) — Storefront branding

- Public storefront page fetches `storefront_config` alongside categories/products.
- Backend: add `GET /storefront/{slug}/config` public endpoint (returns branding only, no admin fields).
- Frontend: apply `primary_color`, `hero_text`, logo URL to storefront layout.

### 2.8 — UTM visit capture

- `visits` table per data-model.md: `id`, `tenant_id`, `session_id`, `ip_hash TEXT`, `user_agent`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `landed_at`.
- RLS enabled.
- Index on `(tenant_id, landed_at)`.
- `POST /storefront/{slug}/visit` — public, slug-based tenant resolution via `get_db_with_slug`.
  - Accepts UTM params + session_id.
  - Hashes IP with SHA-256 + salt (from env var `IP_HASH_SALT`).
  - Returns `{ visit_id }`.

### 2.10 — Integration tests

- Catalog CRUD: create/read/update/delete categories and products, verify cursor pagination.
- Storefront config: upsert, read defaults when empty.
- Presigned URLs: upload URL generated with correct prefix, download URL requires tenant ownership.
- Cross-tenant isolation: tenant A cannot read tenant B's config/media/visits.
- Visit capture: UTM params stored, ip_hash is not raw IP.
