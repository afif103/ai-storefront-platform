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
| M3 Structured Capture | Complete |
| M3.5 Conversion UI | Complete |
| M4 AI Assistant | Complete |
| M4.2 Storefront Chat | Complete |
| M5 Attribution & Dashboard | Complete |
| M5b Inventory / Stock v1 | Complete |
| M5c Inventory Movements & Stock Ops | Complete (P1–P4) |
| M6 Admin Panel (P1) | Complete (platform admin + suspension) |
| M6 Admin Panel (P2) | Complete (role change + CSV export) |
| M6 Admin Panel (P3) | Complete (usage summary + RLS policies) |
| M6 Admin Panel (P4) | Complete (super admin tenant list UI) |
| M7 Notifications (P1–P4) | Complete (preferences, email/Telegram, dispatch, donation receipt) |
| M8 Infrastructure (8.1–8.8b) | Complete (Docker, CI, VPC, RDS, Redis, S3, ECR, ECS) |
| M8 Infrastructure (8.9) | In progress (ALB + HTTPS + CloudFront + WAF deployed; DNS cutover remaining) |
| M8 Infrastructure (8.10) | In progress (live demo deployed; custom domain remaining) |
| M6 P5+, M7 P5+, M8.11–8.13, M9 | Not started |

**M2**: Categories, products, storefront config, media assets, presigned S3 uploads, UTM visit tracking, public storefront with branding. Full dashboard CRUD + anonymous storefront browsing.

**M3**: Orders, donations, pledges tables + public submit endpoints + admin status transitions (with `audit_events` logging) + tenant-scoped numbering (ORD/DON/PLG-00001). 84 integration tests.

**M3.5**: Storefront conversion UI — cart/checkout, donate, and pledge pages. Dashboard list views with status transition controls.

**M4**: Dashboard AI assistant (`/dashboard/assistant`) with per-tenant quota enforcement, rate limiting, and usage logging. Provider abstraction (OpenAI default, Groq supported). All calls through `ai_gateway.py`.

**M4.2**: Public buyer-facing storefront chat endpoint (`POST /storefront/{slug}/ai/chat`) + floating chat bubble widget. Session-based rate limit (10 msgs / 5 min). Read-only — no order/donation/pledge creation.

**M5**: Event-based analytics (visitor/session/event tracking, UTM attribution, funnel conversion rates, daily series). Dashboard analytics page with KPI cards + funnel table + daily activity. CSV export.

**M5b**: Product inventory fields (`track_inventory`, `stock_qty`). Atomic stock decrement on order submit. 409 on insufficient stock. Public `in_stock` flag. Storefront out-of-stock UI.

**M5c**: Stock movement audit trail (`stock_movements` table). Cancel-restore with idempotency. Dashboard restock + movement history. Per-product low-stock threshold with amber alerts. Analytics CSV export.

**M7**: Notification preferences (email/Telegram toggles per tenant). SES email + Telegram Bot API services. Celery task dispatch on order/donation creation. Donation receipt email to donor.

**M8**: AWS infrastructure in `ap-southeast-1`. VPC with private subnets + NAT. RDS PostgreSQL (encrypted, SSL-forced). ElastiCache Redis (TLS). S3 with Block Public Access. ECR + GitHub Actions image push. ECS Fargate cluster with backend + worker services. ALB with HTTPS (ACM cert). CloudFront distribution with WAF (4 managed rules). Live demo on Vercel + ECS.

## Live Demo

| Component | URL |
|-----------|-----|
| Storefront | `https://ai-storefront-platform.vercel.app/store/rami-demo-store` |
| Dashboard | `https://ai-storefront-platform.vercel.app/dashboard` (dev-login required) |

Demo state: 1 primary demo tenant (`rami-demo-store`, 3 products, AI chat enabled via Groq Llama 3.3 70B) + 2 seed tenants visible in Admin → Tenants. Analytics page populated with sample event data. Backend running on ECS Fargate (`saas-backend:6`).

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

## Local AI Setup

The AI assistant requires a provider API key. Configure in your `.env` (never `.env.example`):

```
AI_PROVIDER=openai          # "openai" (default) or "groq"
AI_API_KEY=your-key-here    # NEVER commit real keys
AI_MODEL=gpt-4o             # or gpt-4o-mini, llama-3.3-70b-versatile (Groq)
AI_MAX_INPUT_CHARS=4000
AI_MAX_OUTPUT_TOKENS=400
```

**Key safety**: `.env.example` must only contain placeholders. If a real key is ever committed, rotate it immediately in the provider dashboard.

See `docs/` for full architecture documentation.
