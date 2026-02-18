# ADR-0003: Authentication — AWS Cognito + Token Transport

**Status**: Accepted
**Date**: 2026-02-17
**Deciders**: Rami (product owner), ChatGPT (brain/reviewer), Claude (implementor)

## Context
We need an auth provider for a multi-tenant SaaS platform. Requirements: email/password signup, email verification, MFA for Owner/Admin, JWT tokens with tenant context resolved from our DB, and no custom auth implementation.

## Decisions

This ADR covers three related decisions made together.

---

### Decision 1: Auth Provider — AWS Cognito

**Choice**: AWS Cognito with custom Next.js auth pages (no hosted UI).

- Cognito is the identity provider only. Our DB is source-of-truth for users, roles, and tenant membership.
- Flow: Cognito `sub` → `users.cognito_sub` → `tenant_members` → `tenant_id` → `SET LOCAL app.current_tenant`.
- MFA required for Owner/Admin roles in production (TOTP preferred over SMS).

#### Alternatives Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Cognito** | AWS-native, free to 50k MAU, no extra vendor, HIPAA-eligible | Ugly hosted UI (mitigated: custom pages), cryptic error messages, no password export on migration | **Chosen** |
| **Clerk** | Best DX, built-in org model, fastest to ship | External vendor, $0.02/MAU after 10k (2x Cognito), org data in Clerk (sync needed) | Rejected — added vendor dependency + higher cost |
| **Auth0** | Mature, Organizations feature, broad social login | Pricing jumps after 7.5k MAU, more complex than needed for MVP | Rejected — overkill for MVP |

**Rationale**: Cognito stays within the AWS ecosystem (one vendor, one bill), is cheapest at scale, and we bypass the hosted UI entirely with custom Next.js pages. The main downside (no password export) is acceptable — if we migrate later, we use Cognito's forgot-password flow to re-verify users.

---

### Decision 2: Token Transport — Bearer Header + httpOnly Refresh Cookie

**Choice**: access token in memory + `Authorization: Bearer` header; refresh token in httpOnly cookie.

| Token | Storage | Transport |
|-------|---------|-----------|
| Access token | In-memory (React context) | `Authorization: Bearer` header on every API call |
| Refresh token | httpOnly / Secure / SameSite=Strict cookie | Auto-sent to `POST /api/v1/auth/refresh` only |

Cookie attributes: `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth/refresh; Max-Age=2592000`. Domain omitted (host-only, defaults to `api.yourdomain.com`).

#### Alternatives Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Bearer + httpOnly refresh cookie** | Access token safe from CSRF (header-based), refresh token safe from XSS (httpOnly). Clean separation. | Slightly more complex than pure cookie or pure header approach | **Chosen** |
| **httpOnly cookies for everything** | Simple — browser handles token transport automatically | Requires CSRF protection on every mutating endpoint. Cookie scoping across subdomains is complex. | Rejected |
| **Both tokens in memory (localStorage)** | Simple frontend code | Refresh token exposed to XSS. localStorage persists after tab close — wider attack window. | Rejected |
| **Both tokens in memory (JS variable only)** | Safest from XSS for both tokens | User loses session on page refresh (must re-login). Bad UX. | Rejected |

**Rationale**: the hybrid approach gives us the best of both worlds — API calls use Authorization header (no CSRF concern), while the refresh token is protected from XSS in an httpOnly cookie. `SameSite=Strict` is safe for our subdomain architecture because `{slug}.yourdomain.com` → `api.yourdomain.com` is same-site (same registrable domain).

---

### Decision 3: Refresh Endpoint Hardening

**Choice**: server-side Origin validation + POST + Content-Type enforcement on `/api/v1/auth/refresh`.

Even though `SameSite=Strict` blocks cross-site cookie sending, we add defense-in-depth because CORS does not protect same-site requests (a compromised subdomain could call the endpoint):

1. **Origin header**: must match `^https://([a-z0-9-]+\.)?yourdomain\.com$`. Missing or non-matching → 403.
2. **Method**: POST only. GET → 405.
3. **Content-Type**: must be `application/json`. Prevents simple form submissions from triggering the endpoint.

#### CORS Configuration
Dynamic origin validation — backend checks `Origin` header against allowlist and echoes the validated origin in `Access-Control-Allow-Origin`. Never returns `*`. `Access-Control-Allow-Credentials` not set on general API responses (auth is via header, not cookies).

---

### Cognito Refresh Token Rotation
Rotation enabled in Cognito pool settings. Each use returns a new refresh token; the **previous token remains valid during a configurable grace period** (default 60 seconds) to handle concurrent requests. Cognito does not immediately invalidate the old token.

## Consequences
- Backend must cache Cognito JWKS and verify JWT signatures on every request.
- Frontend needs an interceptor: on 401 → call refresh → retry original request; on refresh failure → redirect to login.
- Refresh endpoint rate-limited (10 attempts per IP per 5 minutes) alongside other auth endpoints.
- Migration off Cognito is possible but requires users to reset passwords (no password export from Cognito). Mitigated by owning all user/role data in our DB.
- Cookie `Path=/api/v1/auth/refresh` limits cookie exposure — it is not sent on any other API call.

See `docs/01-architecture/security.md` for full implementation details, cookie spec, and checklists.
