# Security

MVP-focused security controls. Each section ends with a checklist.

---

## 1. Authentication — AWS Cognito

### Setup
- One Cognito User Pool in `me-south-1`.
- Custom Next.js auth pages (signup, login, forgot password, MFA setup). No hosted UI.
- Cognito handles: email verification, password policy, MFA, token issuance.
- Our DB is source-of-truth for users, roles, and tenant membership. Cognito is the identity provider only.

### Token Transport — Authorization Header + httpOnly Refresh Cookie

| Token | Storage | Transport | Lifetime |
|-------|---------|-----------|----------|
| Access token | In-memory (React context) | `Authorization: Bearer` header | 15 minutes |
| ID token | In-memory (React context) | Frontend display only, never sent to backend | 15 minutes |
| Refresh token | httpOnly cookie | Auto-sent by browser to `/api/v1/auth/refresh` | 30 days |

**Refresh token rotation**: enabled in Cognito pool settings. Each use returns a new refresh token; the previous token remains valid during a grace period (default 60 seconds) to handle concurrent requests. This is Cognito's behaviour — it does not immediately invalidate the old token.

### Token Flow
```
1.  User signs in via Next.js → Cognito (InitiateAuth)
2.  Cognito returns: id_token + access_token + refresh_token
3.  Next.js API route sets refresh_token as httpOnly cookie (see cookie spec below);
    returns access_token + id_token in response body
4.  Frontend holds access_token in memory (React context). Never localStorage.
5.  Every API request sends Authorization: Bearer {access_token}
6.  Backend verifies JWT signature against Cognito JWKS (cached, refreshed hourly)
7.  Backend extracts cognito_sub → users row → tenant_id via tenant_members
8.  Middleware executes SET LOCAL app.current_tenant = '<tenant_id>'
9.  On 401 → frontend calls POST /api/v1/auth/refresh (cookie sent automatically)
    → receives new access_token → retries original request
10. On refresh failure → redirect to login
```

### Refresh Cookie Specification

```
Set-Cookie: refresh_token={value};
    HttpOnly;
    Secure;
    SameSite=Strict;
    Path=/api/v1/auth/refresh;
    Max-Age=2592000
```

| Attribute | Value | Why |
|-----------|-------|-----|
| `HttpOnly` | yes | Prevents JS access — mitigates XSS token theft |
| `Secure` | yes | HTTPS only |
| `SameSite=Strict` | yes | Cookie sent only on same-site requests. `https://{slug}.yourdomain.com` → `https://api.yourdomain.com` is same-site (same registrable domain `yourdomain.com`), so the cookie IS sent. `https://attacker.com` → `https://api.yourdomain.com` is cross-site, so the cookie is NOT sent. |
| `Path` | `/api/v1/auth/refresh` | Cookie only sent to the refresh endpoint, not to every API call |
| `Domain` | omitted | Defaults to host-only (`api.yourdomain.com`). Not setting `Domain` prevents the cookie from being sent to other subdomains, limiting exposure. |
| `Max-Age` | 2592000 (30 days) | Matches Cognito refresh token lifetime |

### `/auth/refresh` Hardening

Even though `SameSite=Strict` blocks cross-site cookie sending, we add server-side defenses as defense-in-depth. Note: CORS does NOT protect same-site requests — a malicious script on a compromised same-site subdomain could still call the refresh endpoint. These server-side checks mitigate that:

1. **Origin header validation**: reject the request if the `Origin` header is missing or does not match the same-site allowlist (`yourdomain.com` and `*.yourdomain.com`).
2. **Method restriction**: `POST` only. `GET` returns 405.
3. **Content-Type enforcement**: require `Content-Type: application/json`. This prevents simple form submissions (which use `application/x-www-form-urlencoded` or `multipart/form-data`) from triggering the endpoint.

```python
# Pseudocode — app/api/v1/auth/refresh.py
ALLOWED_REFRESH_ORIGINS = re.compile(r"^https://([a-z0-9-]+\.)?yourdomain\.com$")

@router.post("/auth/refresh")
async def refresh(request: Request):
    origin = request.headers.get("origin", "")
    if not ALLOWED_REFRESH_ORIGINS.match(origin):
        raise HTTPException(403, "Invalid origin")

    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        raise HTTPException(415, "Unsupported media type")

    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(401, "No refresh token")

    # Call Cognito InitiateAuth with REFRESH_TOKEN_AUTH flow
    new_tokens = await cognito_refresh(refresh_token)

    response = JSONResponse({"access_token": new_tokens.access_token})
    response.set_cookie(...)  # New refresh token cookie with same attributes
    return response
```

### MFA
- MFA required for Owner and Admin roles in production.
- Enforced at Cognito level via adaptive auth or at app level by checking MFA status on sensitive operations.
- TOTP preferred (Cognito supports TOTP and SMS; avoid SMS where possible).

### Checklist
- [ ] Cognito User Pool created in `me-south-1` with password policy (min 12 chars, mixed case, numbers, symbols).
- [ ] Custom auth pages in Next.js (no hosted UI).
- [ ] JWT verification in FastAPI middleware using `python-jose` + cached JWKS.
- [ ] `cognito_sub` → `users` → `tenant_members` → `tenant_id` resolution in middleware.
- [ ] Access token held in memory (React context). Never in localStorage or sessionStorage.
- [ ] Refresh token stored as httpOnly / Secure / SameSite=Strict cookie, Path=/api/v1/auth/refresh, Domain omitted (host-only).
- [ ] `POST /api/v1/auth/refresh` validates: Origin header (same-site allowlist), Content-Type (application/json), POST method.
- [ ] Frontend interceptor: on 401 → call refresh → retry; on refresh failure → redirect to login.
- [ ] Refresh token rotation enabled in Cognito pool settings (with grace period).
- [ ] MFA enforced for Owner/Admin roles in production.
- [ ] No tokens in URL params, localStorage, or sessionStorage.

---

## 2. Tenant Isolation — RLS

Full details in `tenancy-rls.md`. Summary of security-critical points:

- Every authenticated request → middleware resolves `tenant_id` → `SET LOCAL app.current_tenant = '<uuid>';`.
- `SET LOCAL` is transaction-scoped — cannot leak across pooled connections.
- All tenant-scoped tables have `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`.
- No RLS-bypass application role. Platform admin queries global tables or impersonates a tenant via `SET LOCAL`.
- Global tables (`users`, `tenants`, `plans`) never exposed to tenant-facing endpoints unless joined through `tenant_members` filtered by current tenant.

### Checklist
- [ ] `SET LOCAL` (not `SET`) confirmed in middleware code.
- [ ] `FORCE ROW LEVEL SECURITY` on every tenant-scoped table.
- [ ] Cross-tenant isolation integration tests (Tenant A cannot read/write Tenant B's data).
- [ ] No `SECURITY DEFINER` functions without ADR.
- [ ] No direct `users` table exposure to tenant endpoints.

---

## 3. Secrets Management

### Policy
- **Preferred**: AWS Secrets Manager (auto-rotation support, audit via CloudTrail).
- **Acceptable**: SSM Parameter Store SecureString (for simpler config values).
- **Never**: plaintext in environment variables, `.env` files committed to git, database columns, or client-side bundles.

### What Goes Where
| Secret | Storage | Key Pattern |
|--------|---------|-------------|
| Database credentials | Secrets Manager | `/{env}/rds/credentials` |
| Cognito app client secret | Secrets Manager | `/{env}/cognito/client-secret` |
| AI provider API key | Secrets Manager | `/{env}/ai/api-key` |
| IP hash rotating salt | Secrets Manager | `/{env}/ip-hash-salt/current` |
| SES SMTP credentials | Secrets Manager | `/{env}/ses/smtp` |
| Telegram bot tokens (per-tenant) | Secrets Manager | `/{env}/telegram/{tenant_id}/bot-token` |
| Feature flags, non-secret config | SSM SecureString | `/{env}/config/{key}` |

### Telegram Bot Token Pattern
Tenant-provided Telegram bot tokens are **never stored in the database**. Instead:
1. Tenant submits bot token via admin UI.
2. Backend stores it in Secrets Manager at `/{env}/telegram/{tenant_id}/bot-token`.
3. Database column `notification_preferences.telegram_bot_token_ref` stores the Secrets Manager key — not the token itself.
4. Worker retrieves the token from Secrets Manager at dispatch time (cached in-memory for 5 min, per-tenant).

### Checklist
- [ ] No secrets in `.env` files committed to git (`.env` in `.gitignore`).
- [ ] All secrets loaded from Secrets Manager or SSM at app startup / on-demand.
- [ ] `telegram_bot_token_ref` column stores Secrets Manager key, not plaintext.
- [ ] Secrets Manager resource policy restricts access to ECS task roles only.
- [ ] CloudTrail logging enabled for Secrets Manager access events.

---

## 4. S3 Object Security

### Tenant Prefix Rule
All tenant-uploaded objects stored under `{tenant_id}/` prefix:
```
s3://bucket-name/{tenant_id}/logo.png
s3://bucket-name/{tenant_id}/media/{media_asset_id}/photo.jpg
```

### Access Control
- S3 bucket is **private** (Block All Public Access enabled).
- All object access is via **presigned URLs** (GET for downloads, PUT for uploads).
- Presigned URLs are generated **only after verifying tenant ownership**:
  ```python
  # Pseudocode
  def get_presigned_url(tenant_id: UUID, s3_key: str):
      # Verify the s3_key starts with this tenant's prefix
      assert s3_key.startswith(f"{tenant_id}/")
      # Verify the media_asset row belongs to this tenant (RLS handles this)
      asset = await db.get(MediaAsset, s3_key=s3_key)  # RLS-filtered
      if not asset:
          raise 404
      return s3_client.generate_presigned_url(...)
  ```
- Presigned URL expiry: 15 minutes for GET, 30 minutes for PUT.
- PUT presigned URLs include `Content-Type` and `Content-Length` conditions.

### Checklist
- [ ] S3 bucket: Block Public Access enabled.
- [ ] Bucket policy denies any request without `{tenant_id}/` prefix from app role.
- [ ] Presigned URL generation validates `tenant_id` prefix match.
- [ ] Presigned URL generation checks RLS-filtered ownership of the asset.
- [ ] PUT presigned URLs set max content-length (e.g., 10 MB).
- [ ] No direct S3 URLs exposed to clients — presigned only.

---

## 5. Input Validation

### Backend (FastAPI + Pydantic)
- Every request/response has a Pydantic model. No raw `dict` or `Any`.
- Pydantic validates types, lengths, formats, and allowed values.
- SQL queries use parameterised statements exclusively (`text(:param)` or ORM). No f-strings, no string concatenation for SQL.
- File uploads validated: content-type allowlist, max size, filename sanitisation.

### Frontend (Next.js + Zod)
- All form inputs validated with Zod schemas before submission.
- TypeScript strict mode — no `any` types.
- User-generated content rendered with proper escaping (React handles this by default; avoid `dangerouslySetInnerHTML`).

### Checklist
- [ ] Every API endpoint has Pydantic request model with field constraints.
- [ ] No raw SQL string construction anywhere in codebase.
- [ ] File upload endpoint validates content-type against allowlist.
- [ ] Frontend Zod schemas match backend Pydantic schemas (shared types or generated).
- [ ] `dangerouslySetInnerHTML` usage: zero occurrences (grep check in CI).

---

## 6. Rate Limiting

### Strategy
Two layers, both enforced at the backend (FastAPI middleware using Redis counters):

| Scope | Limit | Window | Applies To |
|-------|-------|--------|------------|
| Per-IP | 100 requests | 1 minute | All endpoints (prevents brute force) |
| Per-tenant | 1,000 requests | 1 minute | Authenticated endpoints |
| Per-IP (auth) | 10 attempts | 5 minutes | Login / signup / password reset / refresh |
| Per-tenant (AI) | Based on plan quota | Monthly | AI chat endpoint |
| Per-IP (storefront) | 60 requests | 1 minute | Public storefront pages |
| Per-session (AI chat) | 10 messages | 5 minutes | Public AI chat on storefront |

### Implementation
- Redis `INCR` + `EXPIRE` for sliding window counters.
- Key pattern: `rl:{scope}:{identifier}:{window}` (e.g., `rl:ip:1.2.3.4:60`).
- Return `429 Too Many Requests` with `Retry-After` header.
- AI quota tracked separately in Redis (see `ai-architecture.md`); rate limiting here is for burst protection, not billing.

### Checklist
- [ ] Rate limit middleware in FastAPI using Redis.
- [ ] Per-IP limits on all endpoints.
- [ ] Stricter limits on auth and refresh endpoints.
- [ ] AI chat burst limits (per-session, per-IP).
- [ ] `429` responses include `Retry-After` header.
- [ ] Rate limit keys expire automatically (no Redis memory leak).

---

## 7. Logging & Audit Trail

### Structured Logging
- All logs emitted as structured JSON (using `structlog` or `python-json-logger`).
- Every log entry includes: `timestamp`, `level`, `request_id`, `tenant_id` (if authenticated), `user_id` (if authenticated), `endpoint`, `method`.
- Logs shipped to CloudWatch Logs (log group per service: `/{env}/backend`, `/{env}/worker`).

### Audit Events
Admin-significant actions are logged as audit events to a dedicated log stream:

| Action | Fields Logged |
|--------|--------------|
| User signup | `user_id`, `email` |
| Tenant created | `tenant_id`, `owner_user_id` |
| Member invited/removed | `tenant_id`, `target_user_id`, `role`, `actor_user_id` |
| Role changed | `tenant_id`, `target_user_id`, `old_role`, `new_role`, `actor_user_id` |
| Storefront config updated | `tenant_id`, `actor_user_id`, `changed_fields` |
| Order/donation/pledge status change | `tenant_id`, `entity_type`, `entity_id`, `old_status`, `new_status`, `actor_user_id` |
| AI quota exhausted | `tenant_id`, `quota_limit`, `current_usage` |
| Tenant suspended/reactivated | `tenant_id`, `actor_user_id` (super admin) |
| Refresh token used | `user_id`, `ip_hash`, `success/failure` |

### PII Handling
- **Never log**: passwords, tokens (access, refresh, API keys), Telegram bot tokens, raw IP addresses.
- **Log with care** (include only when necessary for debugging, redact in long-term storage): email addresses, phone numbers, customer names.
- IP addresses: log `ip_hash` only (salted hash, same as `visits` table).
- Request/response bodies: never logged in production. In staging, log request bodies with PII fields redacted.

### Checklist
- [ ] `structlog` configured for JSON output in backend and worker.
- [ ] `request_id` generated in middleware and propagated to all log entries.
- [ ] Audit events emitted for all actions listed above.
- [ ] PII fields excluded from logs (grep CI check for email/phone patterns in log statements).
- [ ] CloudWatch log groups created with 90-day retention (configurable).
- [ ] No token or secret values in any log output.

---

## 8. Network & Edge Protection

### Architecture
```
Internet → CloudFront (WAF) → ALB → ECS Fargate (backend + worker)
Internet → Vercel Edge Network → (calls backend API via ALB)
```

### CloudFront + WAF
- WAF attached to CloudFront distribution (or directly to ALB).
- WAF rules (AWS Managed Rules):
  - `AWSManagedRulesCommonRuleSet` (OWASP core rules).
  - `AWSManagedRulesSQLiRuleSet` (SQL injection).
  - `AWSManagedRulesKnownBadInputsRuleSet` (log4j, etc.).
  - Rate-based rule: 2,000 requests per 5 minutes per IP (outer layer; app-level limits are tighter).
- Geo-restriction: optional, can limit to MENA + common VPN regions if abuse is observed.

### ALB
- HTTPS only (redirect HTTP → HTTPS).
- TLS 1.2+ enforced.
- Security groups: ALB accepts 443 from CloudFront IP ranges only (if using CloudFront) or 0.0.0.0/0 (if ALB is public).
- ECS tasks accept traffic from ALB security group only.

### CORS
Authentication uses `Authorization` header on most endpoints, so CORS cookie handling (`Access-Control-Allow-Credentials`) is not required for general API calls. The refresh endpoint uses a same-site httpOnly cookie, but since it is same-site (`*.yourdomain.com` → `api.yourdomain.com`), the browser does not treat it as a cross-origin credentialed request.

CORS configuration uses **dynamic origin validation** — the backend checks the `Origin` header against an allowlist at runtime and echoes back the validated origin:

```python
# app/core/middleware/cors.py
import re

ALLOWED_ORIGIN_PATTERN = re.compile(r"^https://([a-z0-9-]+\.)?yourdomain\.com$")
ALLOWED_ORIGINS_STATIC = {
    "https://yourdomain.com",
    "https://admin.yourdomain.com",
}

def validate_origin(origin: str) -> bool:
    if origin in ALLOWED_ORIGINS_STATIC:
        return True
    if ALLOWED_ORIGIN_PATTERN.match(origin):
        return True
    return False

# Middleware: if validate_origin(request_origin) is True,
# set Access-Control-Allow-Origin to the exact request origin value.
# Otherwise, omit the header entirely (browser blocks the response).
# Never return Access-Control-Allow-Origin: *
```

- Allowed methods: `GET, POST, PUT, PATCH, DELETE, OPTIONS`.
- `Access-Control-Allow-Credentials`: not set (not needed — auth is via Authorization header, not cookies, for standard API calls).
- Staging: add staging-specific origins to the static set.

### TLS
- All external traffic over HTTPS. No exceptions.
- Internal traffic (ECS → RDS, ECS → ElastiCache): encrypted in transit (RDS: `require_ssl`, ElastiCache: in-transit encryption enabled).
- ACM certificates for all domains (auto-renewed).

### Checklist
- [ ] WAF attached with managed rule sets.
- [ ] ALB HTTPS-only with TLS 1.2+ policy.
- [ ] Security groups: ECS only accepts from ALB, RDS only accepts from ECS, ElastiCache only accepts from ECS.
- [ ] CORS uses dynamic origin validation — never returns `*`, echoes validated origin only.
- [ ] `Access-Control-Allow-Credentials` not set on general API responses.
- [ ] RDS `require_ssl` enabled.
- [ ] ElastiCache in-transit encryption enabled.
- [ ] ACM certificates provisioned for all domains.
- [ ] CloudFront custom error pages (no stack traces exposed).
