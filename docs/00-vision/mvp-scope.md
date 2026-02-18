# MVP Scope

## In Scope

### M1 — Auth & Tenancy
- AWS Cognito user pool with custom Next.js auth pages (no hosted UI).
- Email/password signup; Cognito handles verification and password reset.
- Cognito `sub` mapped to `users.cognito_sub` in our DB; our DB is source-of-truth for users, roles, and tenant membership.
- JWT access + refresh tokens; backend extracts `sub` → resolves `user` → resolves `tenant_id` → executes `SET LOCAL app.current_tenant`.
- Org creation → `tenants` row + RLS policies active immediately.
- Invite team members by email (roles: Owner / Admin / Member).
- MFA required for Owner and Admin roles in production.

### M2 — Tenant Settings & Storefront
- Tenant profile: name, slug, logo (S3 under `{tenant_id}/`), brand colours.
- Product/service catalogue CRUD.
- Public storefront at `https://{slug}.yourdomain.com` (Vercel wildcard subdomain).
- UTM param capture on storefront visits.

### M3 — Structured Capture
- Order creation (product, qty, customer info, status: pending → confirmed → fulfilled → cancelled).
- Donation capture (donor, amount KWD `NUMERIC(12,3)`, campaign, receipt flag).
- Pledge capture (pledgor, amount, target date, status: pledged → partially_fulfilled → fulfilled → lapsed).
- Manual payment instructions + optional payment link field on orders/donations.

### M4 — AI Assistant
- Chat interface on storefront for customer-facing enquiries.
- AI gateway: quota check (Redis) → call provider → log usage → return response.
- Per-tenant monthly token quota with soft/hard limits.
- Admin view of AI usage and costs.

### M5 — Attribution & Dashboard
- UTM storage per visit and per conversion event.
- Tenant dashboard: orders/donations over time, conversion by channel, top campaigns.
- AI cost dashboard per tenant.

### M6 — Admin Panel
- Super admin: list tenants, view usage, toggle tenant active/suspended.
- Tenant-level admin: team management, storefront config, export data (CSV).

### M7 — Notifications
- Transactional email via SES (order confirmations, donation receipts, invite emails, password reset handled by Cognito).
- Telegram notifications via Celery tasks (order received, donation received, pledge due soon).
- Tenant configures notification preferences (email on/off, Telegram bot token + chat ID).
- All notification dispatch is async via Celery worker.

### M8 — Infrastructure & DevOps
- Docker Compose for local dev.
- **Frontend**: Next.js on Vercel (wildcard subdomains, preview deploys).
- **Backend + Worker**: ECS Fargate in `me-south-1` (Bahrain).
- RDS Postgres, ElastiCache Redis, S3, CloudFront + WAF (backend ALB), SES.
- CI/CD: GitHub Actions → Vercel (frontend) + ECR → ECS (backend/worker).
- Alembic migrations in CI.

### M9 — Hardening & Launch Prep
- Rate limiting (per-tenant, per-IP).
- OWASP top-10 audit pass.
- Structured JSON logging → CloudWatch.
- Health checks, alarms, basic runbook.
- Seed data + smoke test suite.

## Out of Scope (MVP)
- KNET / card payment gateway (v1.1+ via PSP).
- Custom domains per tenant.
- Native mobile app.
- Arabic language AI.
- Webhooks / external integrations.
- Real-time notifications (WebSocket).
