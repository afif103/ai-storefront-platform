# API Overview

## Base URL
- **Production**: `https://api.yourdomain.com/api/v1`
- **Staging**: `https://api-staging.yourdomain.com/api/v1`
- **Local dev**: `http://localhost:8000/api/v1`

Interactive docs (Swagger UI): append `/docs` to the base URL (e.g., `http://localhost:8000/docs`).

---

## Authentication

Most endpoints require a valid JWT access token from AWS Cognito.

```
Authorization: Bearer {access_token}
```

Access tokens are obtained via Cognito sign-in and refreshed via `POST /api/v1/auth/refresh` (httpOnly cookie). See `security.md §1` and `ADR-0003` for full details.

### Public Endpoints (No Auth Required)
- `GET /api/v1/health` — health check
- `GET /api/v1/storefront/{slug}` — public storefront data
- `GET /api/v1/storefront/{slug}/catalog` — public catalog listing
- `POST /api/v1/storefront/{slug}/visit` — record a visit (UTM capture)
- `POST /api/v1/storefront/{slug}/ai/chat` — AI chat (public, rate-limited)
- `POST /api/v1/storefront/{slug}/orders` — place an order (public)
- `POST /api/v1/storefront/{slug}/donations` — submit a donation (public)
- `POST /api/v1/storefront/{slug}/pledges` — submit a pledge (public)
- `POST /api/v1/auth/refresh` — refresh access token (uses httpOnly cookie)

### Authenticated Endpoints
All other endpoints require `Authorization: Bearer` header. The backend resolves `tenant_id` from the JWT and sets `SET LOCAL app.current_tenant`.

### Role-Based Access
Some endpoints require specific roles within the tenant:

| Role | Access Level |
|------|-------------|
| `member` | Read own assigned records, use AI assistant |
| `admin` | Full CRUD on tenant data, manage storefront, view dashboard |
| `owner` | Everything admin can do + manage team, billing, tenant settings |
| `super_admin` | Platform-wide: list tenants, view usage, suspend tenants (not tenant-scoped) |

---

## Request / Response Conventions

### Content-Type
All requests and responses use `application/json` unless otherwise noted (file uploads use `multipart/form-data`).

### Pagination
- **Tenant-facing list endpoints**: cursor-based pagination.
  ```json
  {
    "items": [...],
    "next_cursor": "eyJpZCI6ICIuLi4ifQ==",
    "has_more": true
  }
  ```
  Pass `?cursor={next_cursor}` on the next request. Default page size: 20, max: 100.

- **Admin endpoints (MVP)**: may use limit/offset.
  ```
  ?limit=20&offset=0
  ```

### Error Responses
All errors follow RFC 7807 (`application/problem+json`):

```json
{
  "type": "https://api.yourdomain.com/errors/not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "Order ORD-00042 not found.",
  "instance": "/api/v1/orders/ORD-00042"
}
```

### Common Error Codes

| Status | Meaning | When |
|--------|---------|------|
| `400` | Bad Request | Validation error (Pydantic). Body includes `detail` with field-level errors. |
| `401` | Unauthorized | Missing or invalid/expired access token. Frontend should attempt refresh. |
| `403` | Forbidden | Valid token but insufficient role, or tenant suspended. |
| `404` | Not Found | Resource doesn't exist or belongs to another tenant (RLS hides it). |
| `409` | Conflict | Duplicate resource (e.g., duplicate order number, slug already taken). |
| `415` | Unsupported Media Type | Wrong `Content-Type` header. |
| `422` | Unprocessable Entity | Request body is syntactically valid JSON but semantically invalid. |
| `429` | Too Many Requests | Rate limit exceeded. Check `Retry-After` header. |
| `500` | Internal Server Error | Unexpected server error. Logged with `request_id`. |

### Request ID
Every response includes an `X-Request-Id` header. Include this when reporting bugs.

---

## Versioning
API is versioned in the URL path: `/api/v1/`. Breaking changes will go to `/api/v2/` with a deprecation period for v1.

---

## Rate Limits

| Scope | Limit | Window |
|-------|-------|--------|
| Per-IP (all endpoints) | 100 requests | 1 minute |
| Per-tenant (authenticated) | 1,000 requests | 1 minute |
| Per-IP (auth endpoints) | 10 attempts | 5 minutes |
| Per-IP (public storefront) | 60 requests | 1 minute |
| Per-session (AI chat) | 10 messages | 5 minutes |

Exceeding limits returns `429` with `Retry-After` header (seconds until reset).
