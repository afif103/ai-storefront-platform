# Events & Metrics

## Overview
The platform emits structured events for analytics, billing, and audit purposes. Events are logged to PostgreSQL (durable) and optionally to CloudWatch (operational).

---

## Event Types

### 1. Visit Events

Captured when a visitor lands on a tenant storefront.

| Field | Type | Source |
|-------|------|--------|
| `tenant_id` | UUID | Resolved from storefront slug |
| `session_id` | UUID | Generated client-side per visitor session |
| `ip_hash` | TEXT | SHA-256(IP + rotating salt) |
| `user_agent` | TEXT | Request header |
| `utm_source` | TEXT | Query param |
| `utm_medium` | TEXT | Query param |
| `utm_campaign` | TEXT | Query param |
| `utm_content` | TEXT | Query param |
| `utm_term` | TEXT | Query param |
| `landed_at` | TIMESTAMPTZ | Server time |

**Table**: `visits`
**Trigger**: `POST /storefront/{slug}/visit`

### 2. Conversion Events

Captured when a visit leads to an order, donation, or pledge.

| Field | Type | Source |
|-------|------|--------|
| `tenant_id` | UUID | From storefront context |
| `visit_id` | UUID FK | Links to the originating visit |
| `event_type` | TEXT | `order`, `donation`, or `pledge` |
| `event_ref_id` | UUID | ID of the order/donation/pledge record |
| `created_at` | TIMESTAMPTZ | Server time |

**Table**: `utm_events`
**Trigger**: created automatically when an order/donation/pledge is submitted with a `utm_visit_id`.

### 3. AI Usage Events

Captured on every successful AI provider call.

| Field | Type | Source |
|-------|------|--------|
| `tenant_id` | UUID | From request context |
| `user_id` | UUID (nullable) | Null for anonymous storefront visitors |
| `conversation_id` | UUID FK | Links to `ai_conversations` |
| `model` | TEXT | Provider model identifier |
| `tokens_in` | INT | From provider response |
| `tokens_out` | INT | From provider response |
| `cost_usd` | NUMERIC(10,6) | Calculated from pricing config |
| `created_at` | TIMESTAMPTZ | Server time |

**Table**: `ai_usage_log`
**Trigger**: AI gateway, after successful provider call (see `ai-architecture.md`).

### 4. Audit Events

Captured on admin-significant actions. Logged to a dedicated CloudWatch log stream (`/{env}/audit`).

| Field | Type | Notes |
|-------|------|-------|
| `event` | TEXT | Event name (see table below) |
| `tenant_id` | UUID | Null for platform-level events |
| `actor_user_id` | UUID | Who performed the action |
| `target` | TEXT | What was affected (e.g., `user:uuid`, `order:uuid`) |
| `details` | JSON | Event-specific data (old/new values, changed fields) |
| `ip_hash` | TEXT | Actor's hashed IP |
| `timestamp` | TIMESTAMPTZ | Server time |
| `request_id` | TEXT | Correlates with application logs |

**Audit event types**:

| Event | Trigger |
|-------|---------|
| `tenant.created` | New tenant created |
| `tenant.suspended` | Super admin suspends tenant |
| `tenant.reactivated` | Super admin reactivates tenant |
| `member.invited` | Team member invited |
| `member.joined` | Invited member accepts |
| `member.removed` | Member removed from tenant |
| `member.role_changed` | Role updated (includes old + new role) |
| `storefront.updated` | Storefront config changed |
| `order.status_changed` | Order status transition |
| `donation.status_changed` | Donation status transition |
| `pledge.status_changed` | Pledge status transition |
| `ai.quota_exhausted` | Tenant hits hard AI quota limit |
| `ai.soft_limit_reached` | Tenant hits soft AI quota limit (first occurrence per month) |
| `auth.refresh_used` | Refresh token used (success/failure, for anomaly detection) |
| `export.requested` | Data export triggered |

---

## Metrics

### Application Metrics (CloudWatch Custom Metrics)

Emitted from the backend via `structlog` → CloudWatch Logs → Metric Filters, or via CloudWatch `put_metric_data`.

| Metric | Namespace | Dimensions | Unit |
|--------|-----------|------------|------|
| `api.request.count` | `SaaS/Backend` | `endpoint`, `method`, `status_code` | Count |
| `api.request.latency` | `SaaS/Backend` | `endpoint`, `method` | Milliseconds |
| `api.error.count` | `SaaS/Backend` | `endpoint`, `status_code` | Count |
| `ai.request.count` | `SaaS/AI` | `tenant_id`, `model` | Count |
| `ai.tokens.total` | `SaaS/AI` | `tenant_id`, `direction` (in/out) | Count |
| `ai.cost.total` | `SaaS/AI` | `tenant_id` | USD (float) |
| `ai.quota.utilization` | `SaaS/AI` | `tenant_id` | Percent |
| `order.created` | `SaaS/Business` | `tenant_id` | Count |
| `donation.created` | `SaaS/Business` | `tenant_id` | Count |
| `pledge.created` | `SaaS/Business` | `tenant_id` | Count |
| `visit.count` | `SaaS/Business` | `tenant_id`, `utm_source` | Count |
| `worker.task.count` | `SaaS/Worker` | `task_name`, `status` (success/failure) | Count |
| `worker.task.latency` | `SaaS/Worker` | `task_name` | Milliseconds |

### AWS Infrastructure Metrics (Built-in)

| Service | Key Metrics | Alarm Threshold |
|---------|-------------|-----------------|
| ECS | CPUUtilization, MemoryUtilization | > 80% |
| RDS | DatabaseConnections, ReadLatency, WriteLatency, FreeStorageSpace | Connections > 80% max, storage < 5 GB |
| ElastiCache | CurrConnections, EngineCPUUtilization, Evictions | Evictions > 0 |
| ALB | HTTPCode_Target_5XX_Count, TargetResponseTime | 5xx > 10/min, latency P95 > 500ms |
| CloudFront | 4xxErrorRate, 5xxErrorRate | > 5% |

---

## Dashboard Queries

### Conversion Rate by Channel (Tenant Dashboard)

```sql
-- Conversion rate = orders / visits per UTM source
SELECT
    v.utm_source,
    COUNT(DISTINCT v.id) AS visits,
    COUNT(DISTINCT ue.id) AS conversions,
    ROUND(COUNT(DISTINCT ue.id)::numeric / NULLIF(COUNT(DISTINCT v.id), 0), 4) AS rate
FROM visits v
LEFT JOIN utm_events ue ON ue.visit_id = v.id
WHERE v.landed_at >= date_trunc('month', CURRENT_DATE)
GROUP BY v.utm_source
ORDER BY conversions DESC;
-- RLS ensures this only returns current tenant's data
```

### AI Cost per Tenant (Admin Dashboard)

```sql
SELECT
    tenant_id,
    DATE_TRUNC('month', created_at) AS month,
    SUM(tokens_in) AS total_tokens_in,
    SUM(tokens_out) AS total_tokens_out,
    SUM(cost_usd) AS total_cost_usd
FROM ai_usage_log
GROUP BY tenant_id, month
ORDER BY month DESC, total_cost_usd DESC;
-- Super admin query: no RLS (global table access via admin endpoint)
```

### Monthly Revenue Summary (Platform Admin)

```sql
SELECT
    t.id AS tenant_id,
    t.name,
    p.name AS plan_name,
    p.price_amount,
    p.currency,
    COUNT(DISTINCT tm.user_id) AS active_members
FROM tenants t
JOIN plans p ON t.plan_id = p.id
LEFT JOIN tenant_members tm ON tm.tenant_id = t.id AND tm.status = 'active'
WHERE t.is_active = true
GROUP BY t.id, t.name, p.name, p.price_amount, p.currency;
```

---

## Data Retention

| Data | Retention | Rationale |
|------|-----------|-----------|
| `visits` | 12 months | Analytics. Archive older data to S3 if needed. |
| `utm_events` | 12 months | Tied to visits lifecycle |
| `ai_usage_log` | 24 months | Billing disputes, cost analysis |
| `ai_conversations` | 6 months | Storage cost. Older conversations archived to S3 JSONL. |
| Audit logs (CloudWatch) | 90 days | Configurable. Export to S3 for long-term if compliance requires. |
| Application logs | 30 days | Operational debugging only |
