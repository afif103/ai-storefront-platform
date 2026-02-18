# Release Process

## When to Use
Deploying code changes to staging or production.

## Preconditions
- All tests pass on the branch (`pytest` + `npm run test`).
- PR approved and merged to `main`.
- No active incidents on the target environment.

---

## Steps

### 1. Merge to Main

```bash
# PR merged via GitHub UI (squash merge preferred)
# This triggers CI automatically
```

### 2. CI Pipeline (Automatic on Merge)

GitHub Actions runs:

```
main branch push
  ├── Backend
  │   ├── pytest (unit + integration)
  │   ├── ruff check + black --check
  │   ├── Build Docker image
  │   ├── Push to ECR (tagged: git SHA + "latest")
  │   └── Deploy to staging (auto)
  │
  └── Frontend
      └── Vercel auto-deploys to staging (preview URL)
```

### 3. Staging Verification

- [ ] Backend health check: `curl https://api-staging.yourdomain.com/api/v1/health`
- [ ] Frontend loads: `https://staging.yourdomain.com`
- [ ] Smoke test: create tenant → create catalog item → place order → check dashboard.
- [ ] AI chat: send message → verify response and quota deduction.
- [ ] Check staging logs for errors: `aws logs tail /staging/backend --since 5m`

### 4. Database Migration (If Applicable)

Migrations run automatically in CI before ECS deploy. Verify:

```bash
# Check migration status
alembic --config alembic-staging.ini current
# Should show latest revision
```

**Important**: migrations must be backwards-compatible. Old code runs against new schema during rolling deploy.

### 5. Production Deploy

Production deploy is manual (workflow dispatch):

```bash
# Via GitHub Actions UI:
# Actions → "Deploy to Production" → Run workflow → select main branch

# Or via CLI:
gh workflow run deploy-prod.yml --ref main
```

### 6. Production Verification

- [ ] Backend health check: `curl https://api.yourdomain.com/api/v1/health`
- [ ] Frontend loads on a test tenant: `https://test.yourdomain.com`
- [ ] CloudWatch: no 5xx spike in the first 5 minutes.
- [ ] ECS: all tasks running, no crash loops:
  ```bash
  aws ecs describe-services --cluster saas-prod \
    --services saas-backend saas-worker --region me-south-1 \
    --query 'services[].{name:serviceName,running:runningCount,desired:desiredCount}'
  ```

### 7. Tag the Release

```bash
git tag v$(date +%Y.%m.%d)-$(git rev-parse --short HEAD)
git push origin --tags
```

---

## Rollback

### Backend (ECS)
```bash
# Roll back to previous task definition
aws ecs update-service --cluster saas-prod --service saas-backend \
  --task-definition saas-backend:<previous-revision> --region me-south-1
```

### Frontend (Vercel)
Vercel dashboard → Deployments → select previous → "Promote to Production".

### Database
```bash
alembic downgrade -1
```
Only if migration is reversible and no data was written to new structures.

---

## Post-Release Notes
- Monitor CloudWatch dashboard for 15 minutes after production deploy.
- If any alarm fires within 15 minutes, rollback immediately and investigate.
- Update release notes in GitHub Releases if it's a significant feature.

---

## Release Cadence
- **Staging**: continuous (every merge to main).
- **Production**: 1–2 times per week, or as needed for critical fixes.
- **Hotfixes**: branch from `main`, PR, merge, deploy directly to production (skip staging soak if urgent).
