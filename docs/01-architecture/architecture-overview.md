# Architecture Overview

High-level view of the multi-tenant SaaS platform. This document ties together the detailed docs and ADRs — read it first, drill into specifics as needed.

---

## System Context

```
┌─────────────┐   ┌──────────────┐   ┌────────────┐   ┌───────────┐
│  Tenant     │   │  Storefront  │   │  Platform   │   │  External │
│  Team       │   │  Visitors    │   │  Admin      │   │  Services │
│  (Owner,    │   │  (customers, │   │  (super     │   │           │
│   Admin,    │   │   donors)    │   │   admin)    │   │           │
│   Member)   │   │              │   │             │   │           │
└──────┬──────┘   └──────┬───────┘   └──────┬──────┘   └─────┬─────┘
       │                 │                   │                │
       └────────┬────────┴───────────────────┘                │
                ▼                                             │
  ┌──────────────────────────────┐                            │
  │       Next.js Frontend       │                            │
  │       (Vercel Edge)          │                            │
  │  *.yourdomain.com            │                            │
  └──────────────┬───────────────┘                            │
                 │ Authorization: Bearer {access_token}       │
                 ▼                                            │
  ┌──────────────────────────────┐    ┌───────────────────────┤
  │       FastAPI Backend        │    │                       │
  │       (ECS Fargate)          │◄───┤  AWS Cognito (auth)   │
  │       me-south-1             │    │  AI Provider (LLM)    │
  └──────┬───────┬───────┬───────┘    │  SES (email)          │
         │       │       │            │  Telegram API          │
         ▼       ▼       ▼            └───────────────────────┘
  ┌────────┐ ┌───────┐ ┌────┐
  │ RDS PG │ │ Redis │ │ S3 │
  │ (RLS)  │ │       │ │    │
  └────────┘ └───────┘ └────┘
```

---

## Key Architectural Principles

| Principle | How It's Enforced |
|-----------|-------------------|
| **Tenant isolation at the DB level** | RLS on every tenant-scoped table. `SET LOCAL app.current_tenant` per transaction. No bypass role. See `tenancy-rls.md`. |
| **Auth is external, identity is ours** | Cognito issues tokens; our DB owns users, roles, tenant membership. See `ADR-0003`. |
| **AI is metered and gated** | Single AI gateway. Redis quota reserve/rollback. PostgreSQL usage log. See `ADR-0004`, `ai-architecture.md`. |
| **Secrets never in code or DB** | Secrets Manager (preferred) or SSM SecureString. Telegram bot tokens stored as refs. See `security.md §3`. |
| **S3 is tenant-prefixed** | All objects under `{tenant_id}/`. Presigned URLs only, after ownership check. See `security.md §4`. |
| **Frontend and backend deploy independently** | Vercel (frontend) + ECS (backend/worker). Separate release cycles. See `aws-deployment.md`. |

---

## Request Lifecycle (Authenticated)

```
1. Browser sends request to https://{slug}.yourdomain.com
2. Vercel serves Next.js page (SSR/RSC)
3. Frontend JS calls backend API: Authorization: Bearer {access_token}
4. CloudFront + WAF inspect request → forward to ALB
5. ALB routes to ECS backend task
6. FastAPI middleware:
   a. Verify JWT signature against Cognito JWKS (cached)
   b. Extract cognito_sub → look up users row
   c. Resolve tenant_id via tenant_members
   d. Execute: SET LOCAL app.current_tenant = '<tenant_id>'
7. Route handler runs — all DB queries are RLS-filtered
8. Response returns through ALB → CloudFront → browser
```

### Token Refresh (on 401)
```
9.  Frontend receives 401
10. Frontend calls POST /api/v1/auth/refresh
    (httpOnly cookie auto-sent, SameSite=Strict, Path=/api/v1/auth/refresh)
11. Backend validates refresh token with Cognito, returns new access_token
12. Frontend retries original request with new token
```

---

## Request Lifecycle (Public Storefront)

```
1. Visitor hits https://{slug}.yourdomain.com (no auth)
2. Vercel serves public storefront page
3. UTM params captured and sent to backend: POST /api/v1/visits
4. Visitor interacts with AI chat widget → POST /api/v1/ai/chat
   - Tenant resolved from storefront slug (no JWT needed for public endpoints)
   - AI gateway: quota check → provider call → log usage
5. Visitor places order/donation → POST /api/v1/orders (or /donations)
   - Creates record with customer info, links to visit for UTM attribution
```

---

## Component Map

| Component | Technology | Deployed On | Details Doc |
|-----------|-----------|-------------|-------------|
| Frontend | Next.js (App Router, TypeScript) | Vercel | — |
| Backend API | FastAPI (Python 3.12+, async) | ECS Fargate | — |
| Celery Worker | Celery + Redis broker | ECS Fargate | — |
| Database | PostgreSQL 16, RLS | RDS (me-south-1) | `tenancy-rls.md`, `data-model.md` |
| Cache / Queues | Redis 7 | ElastiCache | `ai-architecture.md` (quota keys) |
| Object Storage | S3 | me-south-1 | `security.md §4` |
| Auth | Cognito User Pool | me-south-1 | `ADR-0003`, `security.md §1` |
| AI Gateway | `app/services/ai_gateway.py` | ECS (in backend) | `ai-architecture.md`, `ADR-0004` |
| Email | SES | me-south-1 | `aws-deployment.md` |
| Notifications | Celery tasks (email + Telegram) | ECS (worker) | `mvp-scope.md §M7` |
| Edge | CloudFront + WAF | Global / me-south-1 | `security.md §8`, `aws-deployment.md` |
| CI/CD | GitHub Actions + Vercel | — | `aws-deployment.md` |
| Secrets | Secrets Manager + SSM | me-south-1 | `security.md §3` |

---

## Data Flow Summary

| Data | Write Path | Read Path | Isolation |
|------|-----------|-----------|-----------|
| User/auth | Cognito → webhook/sync → `users` table | JWT sub → `users` lookup | Global table, filtered via `tenant_members` |
| Orders/Donations/Pledges | API → `orders`/`donations`/`pledges` tables | API → RLS-filtered query | `tenant_id` + RLS |
| Catalog | API → `catalog_items` + `media_assets` | API/Storefront → RLS-filtered | `tenant_id` + RLS |
| Media files | Upload → presigned PUT → S3 `{tenant_id}/` | Presigned GET (after ownership check) | S3 prefix + app-level check |
| AI conversations | AI gateway → `ai_conversations` | API → RLS-filtered | `tenant_id` + RLS |
| AI usage | AI gateway → `ai_usage_log` + Redis counter | Dashboard → `ai_usage_log` (PG) | `tenant_id` + RLS |
| Visits/UTM | Storefront → `visits` + `utm_events` | Dashboard → RLS-filtered | `tenant_id` + RLS |
| Notifications | Celery task → SES / Telegram API | Preferences → `notification_preferences` | `tenant_id` + RLS |

---

## Cross-Cutting Concerns

| Concern | Approach | Reference |
|---------|----------|-----------|
| Tenant isolation | RLS + `SET LOCAL` | `tenancy-rls.md` |
| Authentication | Cognito JWT + Bearer header | `security.md §1`, `ADR-0003` |
| Token refresh | httpOnly cookie + hardened endpoint | `security.md §1`, `ADR-0003` |
| Authorization (roles) | `tenant_members.role` checked in FastAPI dependencies | `data-model.md` |
| Input validation | Pydantic (backend) + Zod (frontend) | `security.md §5` |
| Rate limiting | Redis counters, per-IP + per-tenant | `security.md §6` |
| Logging | Structured JSON → CloudWatch | `security.md §7` |
| Audit trail | Dedicated audit log stream | `security.md §7` |
| Error responses | RFC 7807 (`application/problem+json`) | `CLAUDE.md` |
| Pagination | Cursor-based (tenant endpoints), limit/offset (admin, MVP) | `CLAUDE.md` |
| Currency | `NUMERIC(12,3)` + `currency TEXT DEFAULT 'KWD'` | `data-model.md` |

---

## Document Index

| Doc | Purpose |
|-----|---------|
| `00-vision/README.md` | PDF → markdown mapping, explains which docs are source of truth |
| `00-vision/vision.md` | Problem, solution, target users, success metrics |
| `00-vision/product-brief.md` | Capabilities, user roles, out-of-scope |
| `00-vision/mvp-scope.md` | Milestones M1–M9, in/out of scope |
| `00-vision/mvp-build-plan-charity-masjid-kuwait.pdf` | (Reference PDF) Original MVP build plan |
| `00-vision/product-brief-ai-storefront-kuwait-v2.pdf` | (Reference PDF) Original product brief |
| `00-vision/tech-architecture-security-plan-kuwait-multitenant.pdf` | (Reference PDF) Original tech architecture & security plan |
| `01-architecture/architecture-overview.md` | This document |
| `01-architecture/tenancy-rls.md` | RLS implementation, DB roles, safety rules, migration checklist |
| `01-architecture/data-model.md` | ERD, tables, indexes, constraints, conventions |
| `01-architecture/security.md` | Auth, secrets, S3, validation, rate limiting, logging, network |
| `01-architecture/ai-architecture.md` | AI gateway, quota flow, provider abstraction, cost calculation |
| `01-architecture/aws-deployment.md` | Infra diagram, ECS, RDS, Redis, S3, CI/CD, cost estimate |
| `02-decisions/adr-0001-stack.md` | Technology stack choices (Next.js, FastAPI, Postgres, Redis, AWS) |
| `02-decisions/adr-0002-multi-tenancy-rls.md` | Why shared-schema RLS over schema-per-tenant or app-level filtering |
| `02-decisions/adr-0003-auth.md` | Cognito + Bearer/httpOnly hybrid token transport + refresh hardening |
| `02-decisions/adr-0004-ai-metering.md` | Redis quota reserve/rollback + PostgreSQL durable usage log |
| `03-playbooks/dev-setup.md` | Local dev environment setup from scratch |
| `03-playbooks/release-process.md` | How to deploy to staging and production (CI/CD flow) |
| `03-playbooks/qa-checklist.md` | Pre-production QA checklist covering auth, isolation, AI, security |
| `03-playbooks/runbook-prod.md` | Production diagnostics, common failure scenarios, rollback procedures |
| `03-playbooks/incident-response.md` | Severity levels, triage steps, post-mortem template |
| `04-api/api-overview.md` | Base URLs, auth model, pagination, error format, rate limits |
| `04-api/endpoints.md` | All REST endpoints with auth requirements, examples, error codes |
| `04-api/events-metrics.md` | Event types, CloudWatch metrics, dashboard queries, data retention |
| `05-backlog/milestones.md` | M1–M9 milestone map, dependencies, acceptance criteria, timeline |
| `05-backlog/backlog-v1.md` | 83 tasks across 9 epics with owner (Claude/Kimi) and Definition of Done |
