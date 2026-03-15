# Redis Outputs

Resource IDs produced by `provision-redis.sh`.

## Replication Group

| Resource | Value | Notes |
|----------|-------|-------|
| Replication group ID | `saas-prod-redis` | |
| Primary endpoint | `master.saas-prod-redis.cmrcgf.apse1.cache.amazonaws.com` | DNS hostname |
| Port | `6379` | |
| Engine | Redis `7.1.0` | |
| Node type | `cache.t4g.micro` | MVP |
| Multi-AZ | No | MVP Single-AZ; upgrade later |
| Automatic failover | Disabled | Requires Multi-AZ + replica |

## Encryption

| Setting | Value |
|---------|-------|
| In-transit | Enabled |
| At-rest | AWS-managed KMS key |

## Network

| Resource | Value |
|----------|-------|
| Cache subnet group | `saas-redis-subnet-group` |
| Security group | `sg-033c715b2d0326f64` |
| Subnet 1 | `subnet-0ace4111d2f0c0e34` (ap-southeast-1a) |
| Subnet 2 | `subnet-023b7e29ee06b21ae` (ap-southeast-1b) |

## Secrets

| Secret | Purpose |
|--------|---------|
| `/prod/redis-url` | `rediss://` connection — API + worker |

## Backup

| Setting | Value |
|---------|-------|
| Snapshot retention | 1 day (MVP) |
| Snapshot window | 17:00-18:00 UTC |
| Maintenance window | Sun 15:00-16:00 UTC |

## Cross-references

| Downstream Task | Needs |
|-----------------|-------|
| 8.8b P3 (ECS services) | `PRIMARY_ENDPOINT` (via `/prod/redis-url` secret) |
