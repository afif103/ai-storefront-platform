# Redis Outputs

Resource IDs produced by `provision-redis.sh`. Fill in after running the script.

## Replication Group

| Resource | Value | Notes |
|----------|-------|-------|
| Replication group ID | `{{REPL_GROUP_ID}}` | |
| Primary endpoint | `{{PRIMARY_ENDPOINT}}` | DNS hostname |
| Port | `6379` | |
| Engine | Redis `{{VERSION}}` | |
| Node type | `{{NODE_TYPE}}` | MVP |
| Multi-AZ | No | MVP Single-AZ; upgrade later |

## Encryption

| Setting | Value |
|---------|-------|
| In-transit | Enabled |
| At-rest | AWS-managed KMS key |

## Network

| Resource | Value |
|----------|-------|
| Cache subnet group | `{{SUBNET_GROUP}}` |
| Security group | `{{SG_REDIS}}` |
| Subnet 1 | `{{PRIV_DATA_1}}` (AZ1) |
| Subnet 2 | `{{PRIV_DATA_2}}` (AZ2) |

## Secrets

| Secret | Purpose |
|--------|---------|
| `/prod/redis-url` | `rediss://` connection — API + worker |

## Cross-references

| Downstream Task | Needs |
|-----------------|-------|
| 8.8b P3 (ECS services) | `PRIMARY_ENDPOINT` (via `/prod/redis-url` secret) |
| ECS connectivity proof | `/prod/redis-url` injected into one-off task |
