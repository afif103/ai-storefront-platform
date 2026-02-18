# QA Checklist

## When to Use
Before promoting any release to production. Run through this checklist on staging.

## Preconditions
- Staging environment is up and running the candidate build.
- At least two test tenants exist with sample data.
- Tester has credentials for: Tenant Owner, Tenant Admin, Tenant Member, Super Admin.

---

## Steps

### 1. Auth & Onboarding

- [ ] **Signup**: new user can register, receives verification email (SES), verifies, lands on onboarding.
- [ ] **Login**: existing user can log in, receives access token, frontend stores in memory.
- [ ] **Token refresh**: wait 15+ minutes (or force token expiry), confirm automatic refresh works without redirect to login.
- [ ] **Logout**: clears access token from memory, clears refresh cookie, redirects to login.
- [ ] **MFA (Owner/Admin)**: TOTP setup flow works, subsequent logins require TOTP.
- [ ] **Invite flow**: Owner invites a new member by email → member receives invite → accepts → joins tenant.
- [ ] **Role enforcement**: Member cannot access admin settings. Admin cannot access super-admin panel.

### 2. Tenant Isolation

- [ ] **Cross-tenant data**: log in as Tenant A user, attempt to access Tenant B's orders/catalog (via URL manipulation or API call). Must return 404 or empty, never Tenant B's data.
- [ ] **API isolation**: call `GET /api/v1/orders` with Tenant A's token. Response must contain only Tenant A's orders.
- [ ] **S3 isolation**: attempt to generate presigned URL for a media asset belonging to another tenant. Must fail.

### 3. Storefront

- [ ] **Public access**: storefront loads at `https://{slug}.yourdomain.com` without authentication.
- [ ] **Branding**: tenant logo, colours, hero text render correctly.
- [ ] **Catalog display**: products/services/projects show with images, prices (KWD with 3 decimals), descriptions.
- [ ] **UTM capture**: visit `https://{slug}.yourdomain.com?utm_source=test&utm_campaign=qa` → verify visit record created with UTM params.

### 4. Structured Capture

- [ ] **Order creation**: customer fills order form → order created with status `pending` → order number assigned (unique per tenant).
- [ ] **Donation capture**: donor submits donation → record created with amount (KWD), campaign, receipt flag.
- [ ] **Pledge capture**: pledgor submits pledge → record with target date → status `pledged`.
- [ ] **Status transitions**: admin can move order through `pending → confirmed → fulfilled`. Cannot skip to invalid states.
- [ ] **Payment link**: optional payment link field displays correctly on order/donation detail.
- [ ] **UTM attribution**: order/donation created from a UTM-tagged visit → `utm_events` record links visit to conversion.

### 5. AI Assistant

- [ ] **Chat works**: visitor sends message on storefront → receives relevant AI response.
- [ ] **Tenant context**: AI response references the tenant's products/services (not generic or another tenant's).
- [ ] **Quota enforcement**: exhaust a test tenant's AI quota → next message returns 429 with user-friendly message.
- [ ] **Quota rollback**: if AI provider returns an error, verify Redis counter does not increment (check via admin dashboard or Redis CLI).
- [ ] **Usage logging**: after AI chat, `ai_usage_log` row exists with correct `tenant_id`, `tokens_in`, `tokens_out`, `cost_usd`.
- [ ] **Rate limiting**: send 11+ messages in 5 minutes from same session → 429 response.

### 6. Dashboard & Analytics

- [ ] **Orders/donations over time**: chart renders with correct data.
- [ ] **Conversion by channel**: UTM-attributed conversions show in breakdown.
- [ ] **AI cost dashboard**: shows token usage and estimated cost per tenant.
- [ ] **Data matches reality**: manually count orders in DB, compare with dashboard totals.

### 7. Notifications

- [ ] **Email notification**: create an order → tenant receives email confirmation (check SES delivery logs).
- [ ] **Telegram notification**: configure Telegram bot for test tenant → create order → Telegram message received.
- [ ] **Notification preferences**: disable email → create order → no email sent. Re-enable → email sent.
- [ ] **Async delivery**: notifications are processed by Celery worker, not blocking the API response.

### 8. Admin Panel

- [ ] **Super admin**: can list all tenants, view usage summary, suspend/reactivate a tenant.
- [ ] **Tenant admin**: can manage team members (invite, change role, remove).
- [ ] **Export**: tenant admin can export orders/donations as CSV. CSV contains correct data, no cross-tenant leakage.
- [ ] **Suspended tenant**: suspended tenant's storefront shows "unavailable" message. API calls return 403.

### 9. Security Spot Checks

- [ ] **SQL injection**: submit `'; DROP TABLE orders;--` in a form field → no error, safely stored as text.
- [ ] **XSS**: submit `<script>alert('xss')</script>` in a text field → rendered as escaped text, no script execution.
- [ ] **CORS**: make API call from `https://attacker.com` origin → no `Access-Control-Allow-Origin` header in response.
- [ ] **Rate limiting**: hit login endpoint 11 times in 5 minutes → 429 response with `Retry-After` header.
- [ ] **Presigned URL expiry**: generate a presigned URL, wait 16 minutes, attempt access → 403 from S3.

### 10. Performance Baseline

- [ ] **API latency**: `GET /api/v1/orders` (100 records) responds in < 300ms (P95).
- [ ] **Storefront load**: public storefront loads in < 2s (LCP).
- [ ] **AI chat latency**: first AI response in < 5s (depends on provider).

---

## Rollback
If any critical check fails (tenant isolation, data leaks, auth bypass): **do not promote to production**. File a bug, fix, and re-run the checklist.

---

## Post-QA Notes
- Record any flaky tests or edge cases discovered.
- Update this checklist with new scenarios as features are added.
- Screenshot evidence of tenant isolation test for audit trail.
