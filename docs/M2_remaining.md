# Remaining M2 — Storefront & Catalog

## Status: COMPLETE

All M2 items implemented and tested. 33 tests pass, 1 skipped (RLS isolation requires `app_user` connection).

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

## Completed M2 Items

- [x] **2.1 — `storefront_config` table + RLS + migration** (migration 003 + 15e696ca)
- [x] **2.3 — `media_assets` table + RLS + migration** (migration 9513201a, `product_id` FK instead of `catalog_item_id`)
- [x] **2.4 — Storefront config API (GET/PUT)** (commit 06b2226)
- [x] **2.6 — Presigned URL upload/download endpoints** (commit 66d9fd0)
- [x] **2.7 (gap) — Integrate branding into public storefront** (commits c6793b5, be332d4)
- [x] **2.8 — UTM visit capture endpoint + `visits` table** (commits 5546394, 3e98daa)
- [x] **2.10 — M2 integration tests** (commits c3de6cb, e17bf31, 4f3214b)

## Test Summary

Run: `pytest -q -m m2`

| File | Tests | Status |
|------|-------|--------|
| `test_m2_storefront_config.py` | 7 | Pass |
| `test_m2_media_presign.py` | 6 | Pass |
| `test_m2_public_slug_scoping.py` | 10 | 9 pass, 1 skip |
| `test_m2_visits.py` | 5 | Pass |
| `test_rls_isolation.py` | 6 | Pass |

**Skipped**: `test_cross_tenant_isolation` — requires `app_user` DB connection for RLS enforcement. Superuser bypasses RLS. Covered by `tests/test_rls_isolation.py` with `rls_db` fixture.

## M2 Finalization Commits (m2-finish branch)

| Commit | Description |
|--------|-------------|
| `5e84468` | MinIO local dev: docker-compose, dual endpoints, path-style, URL rewrite |
| `45d4194` | Products newest-first sort, DELETE media endpoint, public product images |
| `a673760` | Frontend: products list refresh, image delete wire-up, storefront images |
| `3bd446c` | Fix apiFetch 204 handling + CORS credentials for auth refresh |
| `c9cc764` | Categories list refresh + product create redirects to edit page |
| `aea56c4` | Categories newest-first sort + Created column in dashboard |

## Bugfixes Found During Testing

- `storefront_config` hex color validation used `field_validator` which caused 500 (ValueError not JSON-serializable). Fixed with `Field(pattern=)` for proper 422.
- Public storefront config query used bare `select(StorefrontConfig)` without tenant_id filter. Added explicit `WHERE tenant_id = ...` as defense in depth alongside RLS.
- Dashboard lists (products, categories) sorted by `sort_order ASC, id ASC` — new items could fall past page 1. Fixed to `created_at DESC, id DESC`.
- `apiFetch` crashed on 204 No Content (DELETE endpoints). Fixed to return `{ ok: true, data: null }` for empty responses.
- CORS `allow_credentials: false` blocked auth refresh with `credentials: "include"`. Fixed to `true` with explicit origin allowlist.
