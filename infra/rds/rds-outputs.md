# RDS Outputs

Resource IDs produced by `provision-rds.sh`. Fill in after running the script.

## Instance

| Resource | Value | Notes |
|----------|-------|-------|
| Instance ID | `{{DB_INSTANCE_ID}}` | `saas-db` |
| ARN | `{{RDS_ARN}}` | |
| Endpoint | `{{RDS_ENDPOINT}}` | DNS hostname |
| Port | `{{RDS_PORT}}` | 5432 |
| Engine | PostgreSQL 16 | Latest minor |
| Instance class | `{{INSTANCE_CLASS}}` | `db.t4g.micro` (MVP) |
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
| DB subnet group | `{{SUBNET_GROUP_NAME}}` |
| Security group | `{{SG_RDS}}` |
| Subnet 1 | `{{PRIV_DATA_SUBNET_1}}` (AZ1) |
| Subnet 2 | `{{PRIV_DATA_SUBNET_2}}` (AZ2) |
| Public access | No |

## Parameter Group

| Resource | Value |
|----------|-------|
| Parameter group | `{{PARAM_GROUP_NAME}}` |
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
| Retention | 7 days |
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
