# Milestones

## Overview
MVP is split into 9 milestones (M1–M9), ordered by dependency. Each milestone has a target duration and dependency chain. See `backlog-v1.md` for detailed tasks within each milestone.

---

## Milestone Map

```
M1 Auth & Tenancy ──────┐
                         ├──▶ M2 Storefront ──┐
                         │                     ├──▶ M3 Structured Capture ──┐
                         │                     │                            │
                         │                     └──▶ M4 AI Assistant ────────┤
                         │                                                  │
                         └─────────────────────────────────────────────────▶│
                                                                            ▼
                                                           M5 Attribution & Dashboard
                                                                            │
                                                                            ▼
                                                                   M6 Admin Panel
                                                                            │
                                                                            ▼
                                                              M7 Notifications
                                                                            │
                                                                            ▼
                                                         M8 Infrastructure & DevOps
                                                                            │
                                                                            ▼
                                                       M9 Hardening & Launch Prep
```

Note: M8 (Infra) work starts in parallel with M1 (Docker Compose, CI skeleton). The dependency arrow means "must be feature-complete before the next milestone's features are testable end-to-end."

---

## Milestone Details

### M1 — Auth & Tenancy
**Priority**: P0 (everything depends on this)
**Target**: 2 weeks
**Dependencies**: None (first milestone)

| Acceptance Criteria |
|---------------------|
| User can sign up, verify email, log in via custom Next.js pages + Cognito |
| JWT access token verified in FastAPI middleware |
| `cognito_sub` → `users` → `tenant_members` → `tenant_id` chain works |
| `SET LOCAL app.current_tenant` executes on every authenticated request |
| RLS policies active on `tenant_members` and verified via cross-tenant test |
| Owner can invite members by email; invited user can accept and join |
| MFA setup flow works for Owner/Admin |

---

### M2 — Storefront & Catalog
**Priority**: P0
**Target**: 2 weeks
**Dependencies**: M1

| Acceptance Criteria |
|---------------------|
| Tenant can configure storefront (name, slug, logo, colours) |
| Public storefront loads at `https://{slug}.yourdomain.com` |
| Catalog items (product/service/project) CRUD works |
| Media upload via presigned URL (S3 `{tenant_id}/` prefix) |
| Multiple images per catalog item via `media_assets` |
| UTM params captured on storefront visit |

---

### M3 — Structured Capture
**Priority**: P0
**Target**: 2 weeks
**Dependencies**: M2

| Acceptance Criteria |
|---------------------|
| Public order submission → creates order with `pending` status |
| Public donation submission → creates donation with amount in KWD `NUMERIC(12,3)` |
| Public pledge submission → creates pledge with target date |
| Admin can transition order/donation/pledge through status workflow |
| Invalid status transitions rejected |
| Order numbers unique per tenant (auto-generated) |
| `utm_visit_id` links to visit record for attribution |

---

### M4 — AI Assistant
**Priority**: P1
**Target**: 2 weeks
**Dependencies**: M2 (needs catalog for system prompt)

| Acceptance Criteria |
|---------------------|
| Chat widget on storefront sends messages to AI gateway |
| AI gateway checks Redis quota before provider call |
| Provider failure → Redis rollback, no usage logged |
| Successful call → usage logged to `ai_usage_log` with correct tokens and cost |
| Soft limit → notification to tenant owner (deduped per month) |
| Hard limit → 429 with user-friendly message |
| Per-session rate limit (10 messages / 5 min) enforced |
| System prompt includes tenant name + cached catalog summary |

---

### M5 — Attribution & Dashboard
**Priority**: P1
**Target**: 1.5 weeks
**Dependencies**: M3 (needs orders/donations data), M4 (needs AI usage data)

| Acceptance Criteria |
|---------------------|
| Tenant dashboard shows: orders/donations/pledges count + totals (KWD) |
| Conversion rate displayed (visits → orders) |
| Conversions broken down by UTM source/campaign |
| AI usage dashboard shows tokens used + cost (USD) per month |
| Data matches reality (manual DB count matches dashboard) |

---

### M6 — Admin Panel
**Priority**: P1
**Target**: 1.5 weeks
**Dependencies**: M5

| Acceptance Criteria |
|---------------------|
| Super admin can list all tenants with usage summary |
| Super admin can suspend/reactivate a tenant |
| Suspended tenant: storefront shows "unavailable", API returns 403 |
| Tenant admin can manage team (invite, change role, remove) |
| Tenant admin can export orders/donations as CSV |
| Export contains only current tenant's data (RLS verified) |

---

### M7 — Notifications
**Priority**: P2
**Target**: 1 week
**Dependencies**: M3 (needs orders/donations to notify about)

| Acceptance Criteria |
|---------------------|
| Order created → email sent to tenant (if email_enabled) |
| Order created → Telegram message sent (if telegram_enabled) |
| Donation receipt requested → email sent to donor |
| Pledge due soon → Telegram reminder to tenant |
| Notification preferences configurable per tenant |
| Telegram bot token stored in Secrets Manager (not DB) |
| All notifications dispatched async via Celery |

---

### M8 — Infrastructure & DevOps
**Priority**: P0 (starts in parallel with M1)
**Target**: 2 weeks (spread across M1–M7)
**Dependencies**: None (runs in parallel)

| Acceptance Criteria |
|---------------------|
| Docker Compose works for full local dev stack |
| GitHub Actions CI: test → lint → build → push ECR |
| ECS Fargate services running in `me-south-1` (backend + worker) |
| RDS, ElastiCache, S3 provisioned with security settings per `aws-deployment.md` |
| Vercel deployment with wildcard subdomain |
| Alembic migrations run in CI before deploy |
| CloudWatch log groups and basic alarms configured |

---

### M9 — Hardening & Launch Prep
**Priority**: P1
**Target**: 1.5 weeks
**Dependencies**: M1–M8 complete

| Acceptance Criteria |
|---------------------|
| Rate limiting active (per-IP, per-tenant, auth endpoints) |
| QA checklist passed (see `qa-checklist.md`) |
| OWASP top-10 spot check passed (SQL injection, XSS, CSRF on refresh) |
| Structured JSON logging verified in CloudWatch |
| Health checks and alarms functional |
| Seed data script works for demo |
| Smoke test suite passes end-to-end |
| Runbook and incident response docs reviewed |

---

## Timeline Summary

| Milestone | Target Duration | Cumulative |
|-----------|----------------|------------|
| M1 Auth & Tenancy | 2 weeks | Week 2 |
| M2 Storefront | 2 weeks | Week 4 |
| M3 Structured Capture | 2 weeks | Week 6 |
| M4 AI Assistant | 2 weeks | Week 8 |
| M5 Dashboard | 1.5 weeks | Week 9.5 |
| M6 Admin Panel | 1.5 weeks | Week 11 |
| M7 Notifications | 1 week | Week 12 |
| M8 Infra (parallel) | — | — |
| M9 Hardening | 1.5 weeks | Week 13.5 |

**Estimated MVP delivery: ~14 weeks** (with M8 infra running in parallel throughout).
