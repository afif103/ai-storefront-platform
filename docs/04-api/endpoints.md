# API Endpoints

All endpoints are under `/api/v1`. Auth column: `public` = no token needed, `member/admin/owner` = minimum role required, `super` = super admin only.

---

## Health

### `GET /health`
**Auth**: public

```bash
curl https://api.yourdomain.com/api/v1/health
```

**200 Response**:
```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok",
  "version": "1.0.0"
}
```

---

## Auth

### `POST /auth/refresh`
**Auth**: public (uses httpOnly refresh cookie)

Refresh the access token. Browser auto-sends the httpOnly cookie.

```bash
curl -X POST https://api.yourdomain.com/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -H "Origin: https://app.yourdomain.com" \
  --cookie "refresh_token=<token>"
```

**200 Response**:
```json
{
  "access_token": "eyJhbGciOi..."
}
```

Also sets a new `refresh_token` cookie. See `security.md §1` for cookie spec.

**Error Codes**: `401` (no/invalid refresh token), `403` (invalid origin), `415` (wrong content-type), `429` (rate limited).

---

## Tenants

### `POST /tenants`
**Auth**: member (any authenticated user can create a tenant)

Create a new tenant. The creator becomes the owner.

```bash
curl -X POST https://api.yourdomain.com/api/v1/tenants \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Shop",
    "slug": "my-shop"
  }'
```

**201 Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Shop",
  "slug": "my-shop",
  "plan_id": "free-tier-uuid",
  "is_active": true,
  "created_at": "2026-02-17T10:00:00Z"
}
```

**Error Codes**: `400` (validation), `409` (slug already taken).

### `GET /tenants/me`
**Auth**: member

Get the current tenant (resolved from JWT).

**200 Response**: same shape as above, plus `plan` details.

### `PATCH /tenants/me`
**Auth**: owner

Update tenant settings (name, slug).

---

## Team

### `GET /tenants/me/members`
**Auth**: admin

List tenant members.

**200 Response**:
```json
{
  "items": [
    {
      "id": "member-uuid",
      "user_id": "user-uuid",
      "email": "rami@example.com",
      "full_name": "Rami",
      "role": "owner",
      "status": "active",
      "joined_at": "2026-02-17T10:00:00Z"
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

### `POST /tenants/me/members/invite`
**Auth**: admin

```json
{
  "email": "newmember@example.com",
  "role": "member"
}
```

**201 Response**: member object with `status: "invited"`.

### `PATCH /tenants/me/members/{member_id}`
**Auth**: owner (role changes), admin (remove)

```json
{
  "role": "admin"
}
```

### `DELETE /tenants/me/members/{member_id}`
**Auth**: admin

Removes member from tenant. Cannot remove the last owner.

---

## Storefront Config

### `GET /tenants/me/storefront`
**Auth**: admin

### `PUT /tenants/me/storefront`
**Auth**: admin

```json
{
  "logo_s3_key": "550e8400.../logo.png",
  "primary_color": "#1a73e8",
  "secondary_color": "#ffffff",
  "hero_text": "Welcome to My Shop"
}
```

---

## Categories

### `GET /tenants/me/categories`
**Auth**: member

List categories. Optional query params: `is_active`, `cursor`, `limit`.

**200 Response**:
```json
{
  "items": [
    {
      "id": "cat-uuid",
      "name": "Electronics",
      "description": "Electronic products",
      "sort_order": 0,
      "is_active": true,
      "created_at": "2026-02-17T10:00:00Z"
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

### `POST /tenants/me/categories`
**Auth**: admin

```json
{
  "name": "Electronics",
  "description": "Electronic products",
  "sort_order": 0,
  "is_active": true
}
```

### `GET /tenants/me/categories/{category_id}`
**Auth**: member

### `PATCH /tenants/me/categories/{category_id}`
**Auth**: admin

### `DELETE /tenants/me/categories/{category_id}`
**Auth**: admin

Hard delete. Products with this `category_id` get `SET NULL` via FK.

---

## Products

### `GET /tenants/me/products`
**Auth**: member

List products. Optional query params: `category_id`, `is_active`, `cursor`, `limit`.

**200 Response**:
```json
{
  "items": [
    {
      "id": "prod-uuid",
      "category_id": "cat-uuid",
      "name": "Widget",
      "description": "A great widget",
      "price_amount": "5.250",
      "currency": null,
      "effective_currency": "KWD",
      "is_active": true,
      "sort_order": 1,
      "metadata": {},
      "created_at": "2026-02-17T10:00:00Z"
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

**Currency fallback**: `effective_currency = product.currency ?? tenant.default_currency`. Computed in the API layer, not stored.

### `POST /tenants/me/products`
**Auth**: admin

```json
{
  "name": "Widget",
  "description": "A great widget",
  "price_amount": "5.250",
  "currency": null,
  "category_id": "cat-uuid",
  "metadata": {}
}
```

When `currency` is null, the product inherits the tenant's `default_currency`.

### `GET /tenants/me/products/{product_id}`
**Auth**: member

### `PATCH /tenants/me/products/{product_id}`
**Auth**: admin

### `DELETE /tenants/me/products/{product_id}`
**Auth**: admin

---

## Public Storefront (Catalog)

### `GET /storefront/{slug}/categories`
**Auth**: public

List active categories for a storefront (sorted by `sort_order`). Slug is resolved to `tenant_id` + `SET LOCAL` before querying.

### `GET /storefront/{slug}/products`
**Auth**: public

List active products. Optional query param: `category_id`. Includes `effective_currency`. Cursor pagination.

---

## Media

### `POST /tenants/me/media/upload-url`
**Auth**: admin

Request a presigned PUT URL for uploading media.

```json
{
  "file_name": "photo.jpg",
  "content_type": "image/jpeg",
  "entity_type": "catalog_item",
  "entity_id": "item-uuid"
}
```

**200 Response**:
```json
{
  "upload_url": "https://s3.amazonaws.com/bucket/tenant-id/media/...",
  "s3_key": "tenant-id/media/media-uuid/photo.jpg",
  "expires_in": 1800
}
```

Frontend PUTs the file directly to S3 using this URL.

### `GET /tenants/me/media/{media_id}/url`
**Auth**: member

Get a presigned GET URL (15-min expiry).

---

## Orders

### `POST /storefront/{slug}/orders`
**Auth**: public

Place an order from the storefront. Items are validated against the catalog; price/name snapshotted into JSONB. `total_amount` computed as `sum(qty * unit_price)`. Currency from `tenant.default_currency` (fallback KWD). Auto-generates `order_number` (ORD-00001 pattern, tenant-scoped).

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

**Error Codes**: `422` (invalid product, missing price, invalid visit_id).

### `PATCH /tenants/me/orders/{order_id}/status`
**Auth**: admin

Transition order status. Allowed: `pending→confirmed|cancelled`, `confirmed→fulfilled|cancelled`. Terminal: `fulfilled`, `cancelled`.

```json
{"status": "confirmed"}
```

**200 Response**: full order with updated `status` and `updated_at`.

**422 on invalid transition**:
```json
{"detail": {"message": "Cannot transition order from 'pending' to 'fulfilled'", "allowed": ["confirmed", "cancelled"]}}
```

---

## Donations

### `POST /storefront/{slug}/donations`
**Auth**: public

Submit a donation. Auto-generates `donation_number` (DON-00001). Status starts as `pending`.

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

### `PATCH /tenants/me/donations/{donation_id}/status`
**Auth**: admin

Allowed: `pending→received|cancelled`, `received→receipted|cancelled`. Terminal: `receipted`, `cancelled`.

```json
{"status": "received"}
```

---

## Pledges

### `POST /storefront/{slug}/pledges`
**Auth**: public

Submit a pledge. `target_date` must be in the future (UTC). Auto-generates `pledge_number` (PLG-00001). Status starts as `pledged`.

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

**Error Codes**: `422` (past target_date, invalid visit_id).

### `PATCH /tenants/me/pledges/{pledge_id}/status`
**Auth**: admin

Allowed: `pledged→partially_fulfilled|lapsed`, `partially_fulfilled→fulfilled|lapsed`. Terminal: `fulfilled`, `lapsed`.

```json
{"status": "partially_fulfilled"}
```

---

## AI Chat

### `POST /storefront/{slug}/ai/chat`
**Auth**: public (rate-limited: 10 messages / 5 min per session)

```json
{
  "session_id": "visitor-session-uuid",
  "message": "What products do you have?"
}
```

**200 Response**:
```json
{
  "reply": "We have several products including...",
  "conversation_id": "conv-uuid",
  "tokens_used": 342
}
```

**Error Codes**: `429` (rate limit or quota exhausted — body includes `"type": "quota_exhausted"` or `"type": "rate_limited"`).

---

## Visits & Attribution

### `POST /storefront/{slug}/visit`
**Auth**: public

```json
{
  "session_id": "visitor-session-uuid",
  "utm_source": "instagram",
  "utm_medium": "social",
  "utm_campaign": "ramadan-2026"
}
```

**201 Response**:
```json
{
  "visit_id": "visit-uuid"
}
```

---

## Dashboard

### `GET /tenants/me/dashboard/summary`
**Auth**: admin

```json
{
  "orders_count": 42,
  "orders_total_kwd": "1250.750",
  "donations_count": 15,
  "donations_total_kwd": "500.000",
  "pledges_count": 8,
  "pledges_total_kwd": "800.000",
  "visits_count": 320,
  "conversion_rate": 0.053,
  "ai_tokens_used": 15000,
  "ai_cost_usd": "0.045000",
  "period": "2026-02"
}
```

### `GET /tenants/me/dashboard/conversions-by-channel`
**Auth**: admin

### `GET /tenants/me/dashboard/ai-usage`
**Auth**: admin

---

## Notifications

### `GET /tenants/me/notification-preferences`
**Auth**: admin

### `PUT /tenants/me/notification-preferences`
**Auth**: owner

```json
{
  "email_enabled": true,
  "telegram_enabled": true,
  "telegram_bot_token": "<token>",
  "telegram_chat_id": "123456789"
}
```

Note: `telegram_bot_token` is accepted in the request body but stored in Secrets Manager (not DB). The response returns `telegram_bot_token_configured: true/false`, never the token itself.

---

## Admin (Super Admin)

### `GET /admin/tenants`
**Auth**: super

List all tenants with usage summary. Supports limit/offset pagination.

### `PATCH /admin/tenants/{tenant_id}`
**Auth**: super

Suspend or reactivate a tenant.

```json
{
  "is_active": false
}
```

### `POST /admin/tasks/reconcile-ai-quotas`
**Auth**: super

Trigger AI quota reconciliation (rebuild Redis counters from `ai_usage_log`).
