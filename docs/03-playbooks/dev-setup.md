# Dev Setup Playbook

## When to Use
New developer joining the project, or setting up a fresh machine.

## Preconditions
- Git access to the repository.
- Docker Desktop installed and running.
- Python 3.12+, Node.js 20+, npm installed.
- AWS CLI configured (for Secrets Manager access in staging; not needed for pure local dev).

---

## Steps

### 1. Clone and Configure

```bash
git clone git@github.com:your-org/multi-tenant-saas.git
cd multi-tenant-saas
cp .env.example .env
```

Edit `.env` with local values:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/saas_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=local-dev-secret-change-me
COGNITO_USER_POOL_ID=<from-staging-or-local-mock>
COGNITO_CLIENT_ID=<from-staging-or-local-mock>
COGNITO_REGION=me-south-1
AI_API_KEY=<your-personal-dev-key>
S3_BUCKET=saas-media-dev
AWS_REGION=me-south-1
```

### 2. Start Infrastructure (Docker Compose)

```bash
docker compose up -d postgres redis
```

Wait for healthy:
```bash
docker compose ps  # Both should show "healthy"
```

### 3. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 4. Run Migrations

```bash
alembic upgrade head
```

Verify:
```bash
# Should list all tables including tenants, users, orders, etc.
psql postgresql://postgres:postgres@localhost:5432/saas_db -c "\dt"
```

### 5. Seed Dev Data (Optional)

```bash
python -m app.scripts.seed_dev_data
```

Creates: 2 test tenants, 3 users, sample catalog items, orders, donations.

### 6. Start Backend

```bash
uvicorn app.main:app --reload --port 8000
```

Verify: `http://localhost:8000/docs` → Swagger UI loads.

### 7. Start Celery Worker

```bash
# In a separate terminal, same venv
celery -A app.workers.celery_app worker --loglevel=info
```

### 8. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Verify: `http://localhost:3000` → app loads.

### 9. Verify End-to-End

```bash
# Health check
curl http://localhost:8000/api/v1/health
# Expected: {"status": "ok", "db": "ok", "redis": "ok"}
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `alembic upgrade head` fails with "role does not exist" | Run `psql -c "CREATE ROLE app_user LOGIN PASSWORD 'app_user';"` then retry |
| Redis connection refused | Check `docker compose ps` — Redis may not be running |
| Cognito JWT verification fails locally | Use `COGNITO_MOCK=true` in `.env` to skip JWT verification in dev |
| Port 8000 already in use | `lsof -i :8000` to find the process, kill it, or use `--port 8001` |
| Frontend can't reach backend | Check `NEXT_PUBLIC_API_URL=http://localhost:8000` in frontend `.env.local` |

---

## Rollback
Not applicable (local setup). If things are broken beyond repair:
```bash
docker compose down -v   # Destroys volumes (DB data)
rm -rf backend/.venv frontend/node_modules
# Start from Step 2
```

---

## Post-Setup Notes
- Run `pytest` before pushing any code.
- Run `ruff check .` and `black --check .` for lint/format.
- Frontend: `npm run lint` and `npm run test`.
- See `release-process.md` for how to deploy changes.
