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

## Key Decisions

- **Multi-tenancy**: Row-Level Security on PostgreSQL. Every request executes `SET LOCAL app.current_tenant` on the DB session.
- **Auth**: JWT tokens with tenant context. Refresh token rotation.
- **AI**: Metered usage with per-tenant quotas in Redis. All calls through AI gateway service.
- **Monetary**: KWD amounts stored as `NUMERIC(12,3)`.
- **Deployment**: AWS ECS Fargate, RDS, ElastiCache, S3, CloudFront + WAF.

See `docs/` for full architecture documentation.
