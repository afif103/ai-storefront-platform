# M2 — Media Uploads & Media List

## Overview

Presigned-URL media upload for storefront logos and product images, plus a
tenant-scoped media list endpoint. All storage is S3-prefixed by `{tenant_id}/`
and protected by RLS.

---

## Upload Flows

### Storefront Logo

```
1. POST /api/v1/tenants/me/media/upload-url
   Body: { file_name, content_type, size_bytes }          # no entity fields
   Response 201: { media_id, upload_url, s3_key, expires_in }

2. PUT <upload_url>                                        # client uploads directly to S3
   Headers: Content-Type: <content_type>
   Body: <raw file bytes>

3. PUT /api/v1/tenants/me/storefront
   Body: { logo_s3_key: "<s3_key from step 1>" }          # links logo to storefront
```

Frontend: `dashboard/storefront/page.tsx` handles the full flow with a
preview thumbnail and progress indicator.

### Product Images

```
1. POST /api/v1/tenants/me/media/upload-url
   Body: {
     file_name, content_type, size_bytes,
     entity_type: "product",
     entity_id: "<product_id>",
     product_id: "<product_id>"
   }
   Response 201: { media_id, upload_url, s3_key, expires_in }

2. PUT <upload_url>                                        # client uploads directly to S3

3. Images are immediately persisted as media_assets rows.
   The edit page shows thumbnails with upload progress overlay.
```

Frontend: `dashboard/products/[id]/edit/page.tsx` supports multi-file
selection, parallel uploads, per-file progress. (Removal depends on
backend delete/unlink support.)

Shared upload helper: `frontend/src/lib/upload.ts` (`uploadFile()` with
`onProgress` callback and XHR-based S3 PUT for progress tracking).

---

## Media List Endpoint

```
GET /api/v1/tenants/me/media
```

Query parameters:
| Param | Type | Description |
|-------|------|-------------|
| `product_id` | UUID | Filter by product |
| `entity_type` | string | Filter by entity type (e.g. `"product"`) |
| `entity_id` | UUID | Filter by entity ID |
| `limit` | int (1-200) | Page size (default 50) |
| `offset` | int (>=0) | Offset (default 0) |

Response: `MediaAssetResponse[]` ordered by `created_at DESC, id DESC`.

Role requirement: `member` or higher.

---

## RLS Hardening (Migration `b3c4d5e6f7a8`)

All RLS policies across 6 tables were updated to guard against empty-string
GUC values. PostgreSQL's `current_setting('app.current_tenant', true)` returns
`''` (not `NULL`) when the setting has never been set, causing
`''::uuid` to throw `invalid input syntax for type uuid`.

**Fix**: wrap every cast with `NULLIF`:
```sql
-- Before (crashes on empty GUC):
tenant_id = current_setting('app.current_tenant', true)::uuid

-- After (returns NULL, row excluded safely):
tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
```

Tables fixed: `tenant_members`, `categories`, `products`, `storefront_config`,
`media_assets`, `visits`.

Also added the missing `true` (missing_ok) flag to `tenant_members`
INSERT/UPDATE/DELETE policies that previously used bare
`current_setting('app.current_tenant')`.

---

## Verification

```bash
# Backend tests (33 pass, 1 skip)
cd backend && pytest -q -m m2

# Frontend
cd frontend && npx eslint src/ && npx next build
```
