# Multi-Tenant SaaS Platform

Multi-tenant SaaS application with AI capabilities, built on Next.js + FastAPI + PostgreSQL.

## Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+
- Redis 7+
- Docker & Docker Compose (recommended for local dev)

## Quick Start (Docker Compose)

```bash
cp .env.example .env        # Edit with your values
docker compose up -d         # Start all services
```

Services:
| Service   | URL                        |
|-----------|----------------------------|
| Frontend  | http://localhost:3000       |
| Backend   | http://localhost:8000       |
| API Docs  | http://localhost:8000/docs  |
| Redis     | localhost:6379             |
| Postgres  | localhost:5432             |

## Manual Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head             # Run migrations
uvicorn app.main:app --reload    # Start dev server on :8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                      # Start dev server on :3000
```

### Celery Worker

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

## Environment Variables

Copy `.env.example` and fill in:

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/saas_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<generate-a-random-key>
AI_API_KEY=<your-ai-provider-key>
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name
SES_FROM_EMAIL=noreply@yourdomain.com
```

## Project Structure

```
├── backend/          # FastAPI application
├── frontend/         # Next.js application
├── infra/            # Terraform / CloudFormation
├── docs/             # Architecture, ADRs, playbooks
├── docker-compose.yml
└── CLAUDE.md         # AI agent rules
```

## Milestone Status

| Milestone | Status |
|-----------|--------|
| M1 Auth & Tenancy | Complete (Cognito mock mode for local dev) |
| M2 Storefront & Catalog | Complete (categories, products, public storefront) |
| M3–M9 | Not started |

**M2 scope delivered**: Categories, products, storefront config, media assets, presigned S3 uploads, UTM visit tracking, public storefront with branding. Full dashboard CRUD + anonymous storefront browsing. 27 integration tests (26 pass, 1 skip).

## Running Tests

```bash
# Start DB + Redis
docker compose up -d postgres redis

# Run migrations
cd backend && alembic upgrade head

# All backend tests
cd backend && pytest -q

# M2 tests only
cd backend && pytest -q -m m2

# Frontend build check
cd frontend && npm run build
```

## Key Decisions

- **Multi-tenancy**: Row-Level Security on PostgreSQL. Every request executes `SET LOCAL app.current_tenant` on the DB session.
- **Auth**: JWT tokens with tenant context. Refresh token rotation. Dev-login (mock JWT) uses access token only — no refresh cookie.
- **AI**: Metered usage with per-tenant quotas in Redis. All calls through AI gateway service.
- **Monetary**: `NUMERIC(12,3)` for KWD (3 decimal places). Products store an optional `currency` (ISO 4217); when null, `effective_currency` falls back to `tenant.default_currency`.
- **Deployment**: AWS ECS Fargate, RDS, ElastiCache, S3, CloudFront + WAF.

See `docs/` for full architecture documentation.
