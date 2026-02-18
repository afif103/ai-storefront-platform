# AWS Deployment Architecture

## Overview
- **Frontend**: Next.js on Vercel (wildcard subdomains, preview deploys).
- **Backend + Worker**: FastAPI + Celery on AWS ECS Fargate in `me-south-1` (Bahrain).
- **Data**: RDS PostgreSQL, ElastiCache Redis, S3.
- **Edge**: CloudFront + WAF in front of backend ALB.
- **Email**: SES.
- **Auth**: Cognito User Pool in `me-south-1`.
- **Secrets**: Secrets Manager + SSM Parameter Store.
- **CI/CD**: GitHub Actions → Vercel (frontend) + ECR → ECS (backend/worker).

---

## Infrastructure Diagram

```
                    ┌──────────────────────────────────────┐
                    │              INTERNET                  │
                    └──────┬───────────────────┬────────────┘
                           │                   │
                           ▼                   ▼
                  ┌─────────────────┐  ┌───────────────┐
                  │  Vercel Edge    │  │  CloudFront   │
                  │  (Next.js SSR)  │  │  + WAF        │
                  │  *.yourdomain   │  │  (API traffic)│
                  └─────────────────┘  └───────┬───────┘
                           │                   │
                           │  API calls        │
                           └──────┬────────────┘
                                  ▼
                        ┌──────────────────┐
                        │    ALB (HTTPS)   │
                        │  me-south-1      │
                        └────────┬─────────┘
                                 │
                   ┌─────────────┼─────────────┐
                   ▼                           ▼
          ┌─────────────────┐        ┌─────────────────┐
          │  ECS Fargate    │        │  ECS Fargate    │
          │  Backend        │        │  Celery Worker  │
          │  (FastAPI)      │        │  (notifications,│
          │  2 tasks min    │        │   AI aggregation)│
          └────────┬────────┘        └────────┬────────┘
                   │                          │
        ┌──────────┼────────────┬─────────────┤
        ▼          ▼            ▼             ▼
  ┌──────────┐ ┌──────────┐ ┌──────┐ ┌──────────────┐
  │ RDS      │ │ElastiCache│ │  S3  │ │   SES        │
  │ Postgres │ │ Redis     │ │      │ │  (email)     │
  │ Multi-AZ │ │ Multi-AZ  │ │      │ └──────────────┘
  └──────────┘ └──────────┘ └──────┘
                                       ┌──────────────┐
                                       │  Cognito     │
                                       │  User Pool   │
                                       │  me-south-1  │
                                       └──────────────┘
                                       ┌──────────────┐
                                       │  Secrets Mgr │
                                       │  + SSM       │
                                       └──────────────┘
```

---

## ECS Services

### Backend Service (FastAPI)

| Setting | Value |
|---------|-------|
| Launch type | Fargate |
| CPU / Memory | 0.5 vCPU / 1 GB (MVP; scale up as needed) |
| Desired count | 2 (Multi-AZ) |
| Auto-scaling | Target tracking: avg CPU > 70% → scale out, min 2 / max 6 |
| Health check | `GET /api/v1/health` → 200 |
| Port | 8000 |
| Image | `{account}.dkr.ecr.me-south-1.amazonaws.com/saas-backend:latest` |
| Task role | `saas-backend-task-role` (access to RDS, ElastiCache, S3, Secrets Manager, SES, Cognito) |

### Worker Service (Celery)

| Setting | Value |
|---------|-------|
| Launch type | Fargate |
| CPU / Memory | 0.5 vCPU / 1 GB |
| Desired count | 1 (scale to 2 under load) |
| Auto-scaling | SQS-based or Redis queue depth metric |
| Health check | Celery inspect ping (custom ECS health check script) |
| Image | Same image as backend, different entrypoint (`celery -A app.workers.celery_app worker`) |
| Task role | Same as backend (needs same service access) |

### Container Image Strategy
- Single Docker image for both backend and worker (different entrypoints).
- Multi-stage build: Python deps → app code → slim runtime image.
- Image pushed to ECR on every merge to `main`.

---

## Database — RDS PostgreSQL

| Setting | Value |
|---------|-------|
| Engine | PostgreSQL 16 |
| Instance class | `db.t4g.medium` (MVP; 2 vCPU, 4 GB RAM) |
| Multi-AZ | Yes |
| Storage | 20 GB gp3, auto-scaling to 100 GB |
| Encryption | At rest (AWS managed key) + in transit (`require_ssl`) |
| Backup | Automated, 7-day retention |
| Parameter group | `rds.force_ssl = 1` |
| Security group | Inbound 5432 from ECS tasks SG only |

### Database Roles (created in initial migration)
- `app_user`: used by FastAPI/Celery. RLS enforced.
- `app_migrator`: used by Alembic in CI. No RLS. Never used by the application at runtime.

### Connection Pooling
- SQLAlchemy async pool: `pool_size=10`, `max_overflow=5` per ECS task.
- If connection count becomes a bottleneck: add RDS Proxy (supports IAM auth, connection multiplexing).

---

## Cache — ElastiCache Redis

| Setting | Value |
|---------|-------|
| Engine | Redis 7 |
| Node type | `cache.t4g.micro` (MVP) |
| Multi-AZ | Yes (automatic failover) |
| Encryption | In-transit + at-rest |
| Security group | Inbound 6379 from ECS tasks SG only |

### Redis Key Namespaces
| Prefix | Purpose |
|--------|---------|
| `ai:quota:*` | AI token usage counters (ADR-0004) |
| `ai:limit:*` | Per-tenant soft/hard limits |
| `ai:catalog:*` | Cached catalog summaries for AI system prompts |
| `rl:*` | Rate limiting counters |
| `celery:*` | Celery broker queues |

---

## Storage — S3

| Setting | Value |
|---------|-------|
| Bucket | `saas-media-{env}-{account-id}` |
| Region | `me-south-1` |
| Versioning | Enabled |
| Block Public Access | All blocked |
| Encryption | SSE-S3 (default) |
| Lifecycle | Move objects > 90 days old to Infrequent Access |

All objects stored under `{tenant_id}/` prefix. Access via presigned URLs only (see security.md §4).

---

## Edge — CloudFront + WAF

- CloudFront distribution in front of ALB for API traffic.
- WAF rules: see security.md §8 (AWS Managed Rules + rate-based rule).
- Custom error pages (no stack traces).
- TLS 1.2+ only.

---

## Email — SES

| Setting | Value |
|---------|-------|
| Region | `me-south-1` (or `eu-west-1` if SES not available in me-south-1; verify) |
| Sending identity | `yourdomain.com` (domain-level, not per-email) |
| DKIM | Enabled (Easy DKIM) |
| Configuration set | Tracks bounces, complaints, deliveries → CloudWatch |
| Sending rate | Start in sandbox; request production access before launch |

Transactional emails sent via Celery tasks (order confirmations, donation receipts, invites). Cognito handles its own verification/reset emails via SES automatically.

---

## Auth — Cognito

| Setting | Value |
|---------|-------|
| Region | `me-south-1` |
| User Pool | One pool, custom Next.js auth pages |
| MFA | TOTP, required for Owner/Admin in production |
| Password policy | Min 12 chars, mixed case, numbers, symbols |
| Refresh token rotation | Enabled (60s grace period) |
| App client | Confidential client (client secret in Secrets Manager) |

See ADR-0003 for full auth architecture.

---

## CI/CD Pipeline

```
GitHub push to main
  ├── Frontend (Vercel)
  │   └── Vercel auto-deploys on push (zero config)
  │
  └── Backend (GitHub Actions)
      ├── Run tests (pytest)
      ├── Run linter (ruff)
      ├── Build Docker image
      ├── Push to ECR
      ├── Run Alembic migrations (against staging/prod RDS)
      └── Update ECS service (rolling deployment)
```

### Deployment Strategy
- **Backend**: ECS rolling update. `minimumHealthyPercent=100`, `maximumPercent=200`. New tasks start, pass health check, old tasks drain.
- **Frontend**: Vercel atomic deploys. Instant rollback via Vercel dashboard.
- **Database migrations**: run as a pre-deploy step in CI. Alembic `upgrade head` against the target environment. Migrations must be backwards-compatible (old code runs against new schema during rolling deploy).

### Environment Promotion
```
feature branch → PR preview (Vercel) + staging backend
main → staging auto-deploy
staging → production (manual promotion via GitHub Actions workflow dispatch)
```

---

## Networking

### VPC Layout (`me-south-1`)
| Subnet | Purpose | AZs |
|--------|---------|-----|
| Public subnets | ALB, NAT Gateway | 2 AZs |
| Private subnets (app) | ECS tasks | 2 AZs |
| Private subnets (data) | RDS, ElastiCache | 2 AZs |

### Security Groups
| SG | Inbound | Outbound |
|----|---------|----------|
| `sg-alb` | 443 from CloudFront IPs (or 0.0.0.0/0) | ECS tasks SG on 8000 |
| `sg-ecs` | 8000 from ALB SG | RDS SG on 5432, Redis SG on 6379, S3/SES/Cognito via NAT + VPC endpoints |
| `sg-rds` | 5432 from ECS SG | None |
| `sg-redis` | 6379 from ECS SG | None |

### VPC Endpoints (cost optimisation, avoids NAT for AWS services)
- `com.amazonaws.me-south-1.s3` (Gateway)
- `com.amazonaws.me-south-1.ecr.api` + `ecr.dkr` (Interface)
- `com.amazonaws.me-south-1.secretsmanager` (Interface)
- `com.amazonaws.me-south-1.logs` (Interface — CloudWatch Logs)

---

## Cost Estimate (MVP, Monthly)

| Service | Spec | Est. Cost |
|---------|------|-----------|
| ECS Fargate (backend, 2 tasks) | 0.5 vCPU / 1 GB × 2 × 730h | ~$35 |
| ECS Fargate (worker, 1 task) | 0.5 vCPU / 1 GB × 1 × 730h | ~$18 |
| RDS PostgreSQL | db.t4g.medium, Multi-AZ, 20 GB | ~$70 |
| ElastiCache Redis | cache.t4g.micro, Multi-AZ | ~$25 |
| S3 | < 10 GB, low request volume | ~$1 |
| CloudFront + WAF | Low traffic MVP | ~$10 |
| SES | < 10k emails/month | ~$1 |
| Cognito | < 50k MAU (free tier) | $0 |
| Secrets Manager | < 20 secrets | ~$8 |
| NAT Gateway | 1 AZ (MVP; 2 for prod) | ~$35 |
| Vercel (frontend) | Pro plan | ~$20 |
| **Total** | | **~$223/mo** |

---

## Checklist

- [ ] VPC created with public, private-app, private-data subnets in 2 AZs.
- [ ] Security groups configured per table above.
- [ ] VPC endpoints for S3, ECR, Secrets Manager, CloudWatch Logs.
- [ ] RDS PostgreSQL provisioned with Multi-AZ, encryption, `require_ssl`.
- [ ] ElastiCache Redis provisioned with Multi-AZ, in-transit encryption.
- [ ] S3 bucket with Block Public Access, versioning, lifecycle rule.
- [ ] ECR repository created; Docker image builds and pushes successfully.
- [ ] ECS cluster with backend + worker services running.
- [ ] ALB with HTTPS listener, health check on `/api/v1/health`.
- [ ] CloudFront distribution + WAF rules attached.
- [ ] SES domain identity verified, DKIM configured.
- [ ] Cognito User Pool configured per ADR-0003.
- [ ] Secrets Manager populated with all secrets (see security.md §3).
- [ ] GitHub Actions workflow: test → build → push ECR → migrate → deploy ECS.
- [ ] Vercel project linked to frontend repo, wildcard subdomain configured.
- [ ] CloudWatch log groups created for backend and worker.
- [ ] CloudWatch alarms: CPU > 80%, RDS connections > 80%, 5xx error rate > 1%.
