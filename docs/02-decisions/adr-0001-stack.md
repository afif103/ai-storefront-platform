# ADR-0001: Technology Stack

**Status**: Accepted
**Date**: 2026-02-17
**Deciders**: Rami (product owner), ChatGPT (brain/reviewer), Claude (implementor)

## Context
We need a technology stack for a multi-tenant SaaS platform targeting Kuwait SMBs. Requirements: branded storefronts, AI assistant, structured capture (orders/donations/pledges), UTM attribution, tenant isolation via RLS, KWD currency support (`NUMERIC(12,3)`).

## Decision

### Frontend
- **Next.js** (App Router, TypeScript strict mode)
- Deployed on **Vercel** (wildcard subdomains for `{slug}.yourdomain.com`, preview deploys, edge middleware)
- Zod for input validation, Tailwind CSS for styling

### Backend
- **FastAPI** (Python 3.12+, async, Pydantic v2)
- Deployed on **AWS ECS Fargate** in `me-south-1` (Bahrain)
- SQLAlchemy 2.0 (async) + Alembic for migrations
- `structlog` for structured JSON logging

### Database
- **PostgreSQL 16+** on AWS RDS
- Row-Level Security for tenant isolation
- `NUMERIC(12,3)` for KWD amounts, `TEXT + CHECK` for status/type fields

### Cache & Queues
- **Redis 7+** on AWS ElastiCache (AI quota tracking, rate limiting, Celery broker)
- **Celery** for async tasks (notifications, AI usage aggregation)

### Storage & CDN
- **S3** for tenant media (objects under `{tenant_id}/` prefix, presigned URLs only)
- **CloudFront + WAF** in front of backend ALB

### Auth
- **AWS Cognito** (see ADR-0003 for details)

### Email
- **AWS SES** for transactional email

## Alternatives Considered

| Layer | Alternative | Why Not |
|-------|-----------|---------|
| Frontend framework | Remix, SvelteKit | Next.js has largest ecosystem, best Vercel integration, team familiarity |
| Frontend deploy | ECS, Amplify | ECS adds 1-2 weeks infra work; Amplify SSR support less mature than Vercel |
| Backend framework | Django, Express | FastAPI: best async perf, native Pydantic validation, OpenAPI docs out of the box |
| Backend deploy | Lambda, EC2 | Fargate: no cold starts (unlike Lambda), no OS management (unlike EC2) |
| Database | MySQL, DynamoDB | Postgres: best RLS support, JSONB, NUMERIC precision for KWD |
| Queue | SQS, RabbitMQ | Celery + Redis: simplest for our scale, Redis already needed for cache |

## Consequences
- Two deployment targets (Vercel + AWS) — adds slight operational complexity but saves weeks of frontend infra work.
- Python backend means AI SDK integration is native (most AI providers have first-class Python SDKs).
- ECS Fargate in `me-south-1` provides data residency in the region closest to Kuwait.
- Redis serves triple duty (cache, queue broker, rate limiting) — single point of failure mitigated by ElastiCache Multi-AZ.
