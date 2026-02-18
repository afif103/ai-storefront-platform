# Production Runbook

## When to Use
Production environment is degraded, erroring, or down. This is the first doc to open during an incident.

## Preconditions
- AWS Console access with appropriate IAM permissions.
- `aws` CLI configured for `me-south-1`.
- Access to CloudWatch dashboards and log groups.
- `gh` CLI for GitHub Actions if redeployment needed.

---

## Quick Diagnostics

### 1. Check Service Health

```bash
# Backend health check
curl https://api.yourdomain.com/api/v1/health

# ECS service status
aws ecs describe-services \
  --cluster saas-prod \
  --services saas-backend saas-worker \
  --region me-south-1 \
  --query 'services[].{name:serviceName,running:runningCount,desired:desiredCount,status:status}'
```

### 2. Check Recent Logs

```bash
# Backend logs (last 30 min)
aws logs tail /prod/backend --since 30m --region me-south-1

# Worker logs
aws logs tail /prod/worker --since 30m --region me-south-1

# Filter for errors only
aws logs tail /prod/backend --since 30m --region me-south-1 \
  --filter-pattern '{ $.level = "ERROR" }'
```

### 3. Check Key Metrics

- **CloudWatch Dashboard**: `SaaS-Prod-Overview`
  - ECS CPU/memory utilisation
  - RDS connections, read/write latency
  - ALB 5xx count, target response time
  - Redis memory, evictions

---

## Common Scenarios

### Scenario A: Backend 5xx Spike

**Symptoms**: ALB 5xx alarm, health check failures.

**Steps**:
1. Check ECS task count: are tasks running?
   ```bash
   aws ecs list-tasks --cluster saas-prod --service-name saas-backend --region me-south-1
   ```
2. Check task logs for crash/OOM:
   ```bash
   aws logs tail /prod/backend --since 10m --region me-south-1 --filter-pattern 'ERROR'
   ```
3. If OOM: increase task memory in task definition, redeploy.
4. If crash loop: check most recent deployment — rollback if needed (see Rollback section).
5. If DB connection errors: check RDS — see Scenario C.

### Scenario B: Database Connection Exhaustion

**Symptoms**: `too many connections` errors in logs, API latency spike.

**Steps**:
1. Check RDS connection count:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/RDS --metric-name DatabaseConnections \
     --dimensions Name=DBInstanceIdentifier,Value=saas-prod-db \
     --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 60 --statistics Maximum --region me-south-1
   ```
2. If connections are at max: scale down ECS tasks temporarily to release connections, then investigate which tasks are leaking.
3. Long-term: add RDS Proxy or reduce `pool_size` per task.

### Scenario C: RDS Failover / Unavailable

**Symptoms**: All DB queries fail, health check returns `{"db": "error"}`.

**Steps**:
1. Check RDS status:
   ```bash
   aws rds describe-db-instances --db-instance-identifier saas-prod-db \
     --region me-south-1 --query 'DBInstances[0].DBInstanceStatus'
   ```
2. If `failing-over`: wait (typically 1-2 minutes for Multi-AZ failover). Tasks will reconnect automatically.
3. If `stopped` or `storage-full`: escalate immediately.

### Scenario D: Redis Unavailable

**Symptoms**: Rate limiting not working, AI quota checks failing, Celery tasks stalled.

**Steps**:
1. Check ElastiCache status:
   ```bash
   aws elasticache describe-replication-groups \
     --replication-group-id saas-prod-redis --region me-south-1
   ```
2. If failover in progress: wait. ElastiCache Multi-AZ failover is automatic.
3. After recovery: run quota reconciliation task to rebuild Redis counters from `ai_usage_log`:
   ```bash
   # Trigger via Celery
   curl -X POST https://api.yourdomain.com/api/v1/admin/tasks/reconcile-ai-quotas \
     -H "Authorization: Bearer <super-admin-token>"
   ```

### Scenario E: AI Provider Outage

**Symptoms**: AI chat returning errors, `ai_gateway` logs show provider timeouts.

**Steps**:
1. Check provider status page (Anthropic / OpenAI).
2. If provider is down: the AI gateway returns a user-friendly fallback message. No action needed unless prolonged.
3. If prolonged (>30 min): switch provider via SSM config if alternate provider is configured:
   ```bash
   aws ssm put-parameter --name /prod/ai/provider --value "openai" \
     --type String --overwrite --region me-south-1
   ```
   Then restart backend tasks to pick up new config.

### Scenario F: Celery Worker Stuck / Not Processing

**Symptoms**: Notifications not sending, AI aggregation tasks piling up.

**Steps**:
1. Check worker logs:
   ```bash
   aws logs tail /prod/worker --since 10m --region me-south-1
   ```
2. Check Redis queue depth:
   ```bash
   redis-cli -h <elasticache-endpoint> LLEN celery
   ```
3. If worker is crash-looping: check ECS task events, force new deployment:
   ```bash
   aws ecs update-service --cluster saas-prod --service saas-worker \
     --force-new-deployment --region me-south-1
   ```

---

## Rollback

### Backend Rollback (ECS)

```bash
# List recent task definitions
aws ecs list-task-definitions --family-prefix saas-backend \
  --sort DESC --max-items 5 --region me-south-1

# Update service to previous task definition
aws ecs update-service --cluster saas-prod --service saas-backend \
  --task-definition saas-backend:<previous-revision> --region me-south-1
```

### Database Rollback (Alembic)

```bash
# Check current revision
alembic current

# Downgrade one step
alembic downgrade -1
```

**Warning**: only run DB rollback if the migration is backwards-compatible and no data has been written to new columns/tables.

### Frontend Rollback (Vercel)

Use Vercel dashboard → Deployments → select previous deployment → "Promote to Production". Instant, no CLI needed.

---

## Post-Incident Notes
- After every production incident, create a brief post-mortem (see `incident-response.md`).
- Update this runbook with any new scenarios encountered.
- Check if monitoring/alarms need to be added or adjusted.
