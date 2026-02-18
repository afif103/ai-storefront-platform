# CLAUDE.md — Project Rules & Non-Negotiables

## Project Overview
Multi-tenant SaaS platform with AI capabilities.
Stack: Next.js (frontend) + FastAPI (backend) + PostgreSQL (RDS) + Redis + Celery + AWS ECS Fargate.

## Non-Negotiables

### Multi-Tenancy
- Every table that holds tenant data MUST have a `tenant_id UUID NOT NULL` column.
- Every API request MUST resolve `tenant_id` from the authenticated JWT and execute `SET LOCAL app.current_tenant = '<tenant-uuid>';` on the DB session before any query. This is done in middleware so route handlers never need to set it manually.
- Row-Level Security (RLS) policies MUST be enabled on all tenant-scoped tables. No exceptions.
- Never use `SECURITY DEFINER` functions unless explicitly approved in an ADR.

### Security
- All secrets in AWS Secrets Manager (preferred) or SSM SecureString. Never in code, env files committed to git, or client bundles.
- CORS origins are explicit allowlists — no wildcards in production.
- All user input is validated with Pydantic models (backend) and Zod schemas (frontend).
- SQL queries use parameterised statements only. No f-strings or string concatenation for SQL.
- S3 objects MUST be stored under `{tenant_id}/` prefix. Presigned URLs are the only access method and MUST only be generated after verifying tenant ownership of the object.

### AI Integration
- Every AI call MUST check the tenant's quota in Redis BEFORE dispatching.
- Token usage MUST be logged to `ai_usage_log` table with `tenant_id`, `user_id`, `model`, `tokens_in`, `tokens_out`, `cost_usd`, `created_at`.
- AI calls go through a single gateway service (`app/services/ai_gateway.py`) — never call provider SDKs directly from route handlers.

### Code Style
- Backend: Python 3.12+, strict type hints, ruff for linting, black for formatting.
- Frontend: TypeScript strict mode, ESLint + Prettier, no `any` types.
- Tests: pytest (backend), vitest (frontend). Minimum 80% coverage on new code.
- Commit messages: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`).

### Database
- Alembic for all migrations. Never hand-edit the DB schema in production.
- Every migration must be reversible (provide `downgrade()`).
- Indexes required on all `tenant_id` columns and any column used in WHERE/JOIN.
- Monetary amounts (KWD) use `NUMERIC(12,3)` — three decimal places to match KWD subdivision.

### API Design
- RESTful, versioned under `/api/v1/`.
- Pagination: cursor-based for public/tenant-facing list endpoints. Admin endpoints may use limit/offset during MVP if needed.
- Error responses follow RFC 7807 (`application/problem+json`).

## File Layout (Backend)
```
backend/
├── app/
│   ├── api/v1/          # Route handlers
│   ├── core/            # Config, security, middleware
│   ├── db/              # Session, base model, migrations
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic request/response
│   ├── services/        # Business logic
│   └── workers/         # Celery tasks
├── tests/
├── alembic/
└── pyproject.toml
```

## File Layout (Frontend)
```
frontend/
├── src/
│   ├── app/             # Next.js App Router pages
│   ├── components/      # Shared UI components
│   ├── lib/             # API client, utils
│   ├── hooks/           # Custom React hooks
│   └── types/           # TypeScript types
├── public/
└── package.json
```

## Commands
```bash
# Backend
cd backend && uvicorn app.main:app --reload          # Dev server
cd backend && pytest                                  # Tests
cd backend && alembic upgrade head                    # Run migrations

# Frontend
cd frontend && npm run dev                            # Dev server
cd frontend && npm run test                           # Tests
cd frontend && npm run build                          # Production build

# Workers
cd backend && celery -A app.workers.celery_app worker --loglevel=info
```
