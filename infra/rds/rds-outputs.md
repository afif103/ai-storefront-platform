# RDS Outputs

Resource IDs produced by `provision-rds.sh`.

## Instance

| Resource | Value | Notes |
|----------|-------|-------|
| Instance ID | `saas-db` | |
| ARN | `arn:aws:rds:ap-southeast-1:701893741240:db:saas-db` | |
| Endpoint | `saas-db.c5c8amqish3n.ap-southeast-1.rds.amazonaws.com` | DNS hostname |
| Port | `5432` | |
| Engine | PostgreSQL 16 | Latest minor |
| Instance class | `db.t4g.micro` | MVP |
| Multi-AZ | No | MVP Single-AZ; upgrade later |

## Storage & Encryption

| Setting | Value |
|---------|-------|
| Storage type | gp3 |
| Allocated | 20 GB |
| Max autoscaling | 100 GB |
| Encryption at rest | AWS-managed KMS key |
| Encryption in transit | `rds.force_ssl=1` |

## Network

| Resource | Value |
|----------|-------|
| DB subnet group | `saas-db-subnet-group` |
| Security group | `sg-0b0457847c1bffdf5` |
| Subnet 1 | `subnet-0ace4111d2f0c0e34` (ap-southeast-1a) |
| Subnet 2 | `subnet-023b7e29ee06b21ae` (ap-southeast-1b) |
| Public access | No |

## Parameter Group

| Resource | Value |
|----------|-------|
| Parameter group | `saas-pg16-params` |
| Family | postgres16 |
| `rds.force_ssl` | 1 |

## Secrets

| Secret | Purpose |
|--------|---------|
| `/prod/rds-master-password` | Master/admin — bootstrap only |
| `/prod/database-url-migrator` | `app_migrator` — migration tasks |
| `/prod/database-url` | `app_user` — runtime application |

## Backup

| Setting | Value |
|---------|-------|
| Retention | 1 day (MVP); upgrade to 7 for production |
| Backup window | 16:00-17:00 UTC |
| Maintenance window | Sun 14:00-15:00 UTC |
| Deletion protection | Enabled |

## Cross-references

| Downstream Task | Needs |
|-----------------|-------|
| 8.8b P3 (ECS services) | `RDS_ENDPOINT`, `RDS_PORT` (via Secrets Manager) |
| Bootstrap task | `/prod/rds-master-password`, `RDS_ENDPOINT` |
| Migration task | `/prod/database-url-migrator` |
| Runtime services | `/prod/database-url` |
