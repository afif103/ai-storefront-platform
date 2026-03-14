# ECS Deploy Runbook

Step-by-step guide to deploy the backend API and Celery worker on ECS Fargate
in `ap-southeast-1`.

## 1. Prerequisites Checklist

Before any ECS work, confirm these exist:

- [ ] **VPC + subnets** (task 8.4) — private subnets for ECS tasks, NAT gateway for outbound
- [ ] **RDS PostgreSQL** (task 8.5) — accessible from ECS private subnets, `app_user` + `app_migrator` roles created via `scripts/init-db.sql`
- [ ] **ElastiCache Redis** (task 8.6) — accessible from ECS private subnets
- [ ] **S3 bucket** (task 8.7) — Block Public Access enabled
- [ ] **ECR image** (task 8.8a) — `saas-backend` repo with at least one tagged image
- [ ] **Secrets Manager entries** — all secrets from `env-contract.md` created (see section 2)
- [ ] **IAM roles** — execution role + task role created (see section 3)
- [ ] **Security groups** — ECS tasks SG allowing outbound to RDS (5432), Redis (6379), NAT (443)

## 2. Create Secrets in Secrets Manager

Create each secret as a **plaintext** string (not JSON key-value):

```bash
aws secretsmanager create-secret \
  --name /prod/database-url \
  --secret-string "postgresql+asyncpg://app_user:PASSWORD@RDS_HOST:5432/saas_db" \
  --region ap-southeast-1

# /prod/database-url-migrator is created later in section 7, after DB bootstrap.

aws secretsmanager create-secret \
  --name /prod/redis-url \
  --secret-string "redis://REDIS_HOST:6379/0" \
  --region ap-southeast-1

aws secretsmanager create-secret \
  --name /prod/secret-key \
  --secret-string "RANDOM_64_CHAR_STRING" \
  --region ap-southeast-1

aws secretsmanager create-secret \
  --name /prod/ai-api-key \
  --secret-string "sk-..." \
  --region ap-southeast-1

aws secretsmanager create-secret \
  --name /prod/ip-hash-salt \
  --secret-string "RANDOM_32_CHAR_STRING" \
  --region ap-southeast-1
```

**Secret / role mapping:**

| Secret | DB Role | Used By |
|--------|---------|---------|
| `/prod/rds-master-password` | RDS master/admin (configured at create time) | Bootstrap only (`init-db.sql`) — never used at runtime |
| `/prod/database-url-migrator` | `app_migrator` (DDL + DML) | Migration ECS task (`alembic upgrade head`) |
| `/prod/database-url` | `app_user` (DML only, RLS-enforced) | Backend + worker ECS services |

Note the ARNs — these replace the `{{SECRET_ARN_*}}` placeholders in task definitions.

## 3. Create IAM Roles

### Execution Role (`saas-ecs-execution-role`)

Trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ecs-tasks.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Attach:
- Managed policy: `arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy`
- Inline policy for secrets access:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": [
        "arn:aws:secretsmanager:ap-southeast-1:{{ACCOUNT_ID}}:secret:/prod/rds-master-password-*",
        "arn:aws:secretsmanager:ap-southeast-1:{{ACCOUNT_ID}}:secret:/prod/database-url-*",
        "arn:aws:secretsmanager:ap-southeast-1:{{ACCOUNT_ID}}:secret:/prod/database-url-migrator-*",
        "arn:aws:secretsmanager:ap-southeast-1:{{ACCOUNT_ID}}:secret:/prod/redis-url-*",
        "arn:aws:secretsmanager:ap-southeast-1:{{ACCOUNT_ID}}:secret:/prod/secret-key-*",
        "arn:aws:secretsmanager:ap-southeast-1:{{ACCOUNT_ID}}:secret:/prod/ai-api-key-*",
        "arn:aws:secretsmanager:ap-southeast-1:{{ACCOUNT_ID}}:secret:/prod/ip-hash-salt-*"
      ]
    }
  ]
}
```

### Task Role (`saas-backend-task-role`)

Trust policy: same as execution role (ecs-tasks.amazonaws.com).

Inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::{{S3_BUCKET}}/*"
    },
    {
      "Sid": "S3ListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::{{S3_BUCKET}}"
    },
    {
      "Sid": "SESAccess",
      "Effect": "Allow",
      "Action": ["ses:SendEmail", "ses:SendRawEmail"],
      "Resource": "*"
    },
    {
      "Sid": "CognitoAccess",
      "Effect": "Allow",
      "Action": "cognito-idp:InitiateAuth",
      "Resource": "arn:aws:cognito-idp:ap-southeast-1:{{ACCOUNT_ID}}:userpool/{{USER_POOL_ID}}"
    }
  ]
}
```

## 4. Create CloudWatch Log Groups

```bash
aws logs create-log-group \
  --log-group-name /ecs/saas-backend \
  --region ap-southeast-1

aws logs put-retention-policy \
  --log-group-name /ecs/saas-backend \
  --retention-in-days 90 \
  --region ap-southeast-1

aws logs create-log-group \
  --log-group-name /ecs/saas-worker \
  --region ap-southeast-1

aws logs put-retention-policy \
  --log-group-name /ecs/saas-worker \
  --retention-in-days 90 \
  --region ap-southeast-1
```

## 5. Create ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name saas-cluster \
  --capacity-providers FARGATE \
  --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
  --region ap-southeast-1
```

## 6. Register Task Definitions

Replace all `{{PLACEHOLDER}}` values in the JSON files, then register:

```bash
aws ecs register-task-definition \
  --cli-input-json file://infra/ecs/bootstrap-task-def.json \
  --region ap-southeast-1

aws ecs register-task-definition \
  --cli-input-json file://infra/ecs/migration-task-def.json \
  --region ap-southeast-1

aws ecs register-task-definition \
  --cli-input-json file://infra/ecs/backend-task-def.json \
  --region ap-southeast-1

aws ecs register-task-definition \
  --cli-input-json file://infra/ecs/worker-task-def.json \
  --region ap-southeast-1
```

## 7. Bootstrap Database Roles

One-off setup for task 8.5 — not a live cutover. No runtime services consume
`/prod/database-url` at this point, so it is safe to create/update secrets
before the roles exist in the database.

The bootstrap ECS task (`saas-bootstrap`) runs `scripts/bootstrap_db.py`, which
connects as the RDS master/admin user and creates `app_migrator` + `app_user`
roles. Credentials are delivered via ECS task-definition secret injection
(execution role reads from Secrets Manager).

**Step 1 — Generate URL-safe passwords:**

```bash
MIGRATOR_PASS=$(openssl rand -base64 24 | tr -d '/+=')
APP_USER_PASS=$(openssl rand -base64 24 | tr -d '/+=')
```

**Step 2 — Create/update secrets with real credentials:**

```bash
aws secretsmanager create-secret \
  --name /prod/database-url-migrator \
  --secret-string "postgresql+asyncpg://app_migrator:${MIGRATOR_PASS}@{{RDS_ENDPOINT}}:5432/saas_db" \
  --region ap-southeast-1

aws secretsmanager update-secret \
  --secret-id /prod/database-url \
  --secret-string "postgresql+asyncpg://app_user:${APP_USER_PASS}@{{RDS_ENDPOINT}}:5432/saas_db" \
  --region ap-southeast-1
```

**Step 3 — Update execution role SecretsReadPolicy** to include all 7 secret ARNs
(add `/prod/rds-master-password` and `/prod/database-url-migrator`; see section 3).

**Step 4 — Register and run bootstrap task:**

```bash
aws ecs run-task \
  --cluster saas-cluster \
  --task-definition saas-bootstrap \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[{{PRIV_APP_SUBNET_1}},{{PRIV_APP_SUBNET_2}}],securityGroups=[{{ECS_SG}}],assignPublicIp=DISABLED}" \
  --region ap-southeast-1
```

**Step 5 — Verify:**

```bash
aws ecs describe-tasks \
  --cluster saas-cluster \
  --tasks {{TASK_ARN}} \
  --region ap-southeast-1 \
  --query "tasks[0].{status:lastStatus,exitCode:containers[0].exitCode,reason:stoppedReason}"
```

Expected: `status=STOPPED`, `exitCode=0`. If `exitCode != 0`, check CloudWatch logs
at `/ecs/saas-backend` with stream prefix `bootstrap`.

## 8. Run Database Migration

Run as a one-off task (not a service). Uses `/prod/database-url-migrator`
(`app_migrator` role with DDL + DML privileges):

```bash
aws ecs run-task \
  --cluster saas-cluster \
  --task-definition saas-migration \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[{{PRIVATE_SUBNET_1}},{{PRIVATE_SUBNET_2}}],securityGroups=[{{ECS_SG}}],assignPublicIp=DISABLED}" \
  --region ap-southeast-1
```

Wait for completion and verify:

```bash
# Get the task ARN from run-task output, then:
aws ecs describe-tasks \
  --cluster saas-cluster \
  --tasks {{TASK_ARN}} \
  --region ap-southeast-1 \
  --query "tasks[0].{status:lastStatus,exitCode:containers[0].exitCode,reason:stoppedReason}"
```

Expected: `status=STOPPED`, `exitCode=0`. If `exitCode != 0`, check CloudWatch logs
at `/ecs/saas-backend` with stream prefix `migration`.

## 9. Create Backend Service

```bash
aws ecs create-service \
  --cluster saas-cluster \
  --service-name saas-backend \
  --task-definition saas-backend \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[{{PRIVATE_SUBNET_1}},{{PRIVATE_SUBNET_2}}],securityGroups=[{{ECS_SG}}],assignPublicIp=DISABLED}" \
  --deployment-configuration "minimumHealthyPercent=100,maximumPercent=200" \
  --region ap-southeast-1
```

No `--load-balancers` — ALB is added in task 8.9.

## 10. Create Worker Service

```bash
aws ecs create-service \
  --cluster saas-cluster \
  --service-name saas-worker \
  --task-definition saas-worker \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[{{PRIVATE_SUBNET_1}},{{PRIVATE_SUBNET_2}}],securityGroups=[{{ECS_SG}}],assignPublicIp=DISABLED}" \
  --region ap-southeast-1
```

## 11. Verify Deployment

### Check service stability

```bash
aws ecs describe-services \
  --cluster saas-cluster \
  --services saas-backend saas-worker \
  --region ap-southeast-1 \
  --query "services[].{name:serviceName,running:runningCount,desired:desiredCount,status:status}"
```

Expected: `running == desired` for both services, `status=ACTIVE`.

### Check backend container health

```bash
aws ecs describe-tasks \
  --cluster saas-cluster \
  --tasks $(aws ecs list-tasks --cluster saas-cluster --service-name saas-backend --query "taskArns[0]" --output text --region ap-southeast-1) \
  --region ap-southeast-1 \
  --query "tasks[0].containers[0].healthStatus"
```

Expected: `HEALTHY`. If `UNHEALTHY`, check CloudWatch logs.

### Check CloudWatch logs

Verify log streams exist and contain startup messages:

- `/ecs/saas-backend` — look for uvicorn startup line: `Uvicorn running on http://0.0.0.0:8000`
- `/ecs/saas-worker` — look for Celery startup line: `celery@... ready`

```bash
aws logs describe-log-streams \
  --log-group-name /ecs/saas-backend \
  --order-by LastEventTime \
  --descending \
  --limit 3 \
  --region ap-southeast-1

aws logs describe-log-streams \
  --log-group-name /ecs/saas-worker \
  --order-by LastEventTime \
  --descending \
  --limit 3 \
  --region ap-southeast-1
```

### Optional: ECS Exec for debugging

If deeper debugging is needed, ECS Exec can be enabled on the service to get a shell
inside a running container. This requires additional IAM permissions and is not part
of the standard verification flow.

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Task stuck in `PROVISIONING` | Subnet has no route to NAT / internet | Check route tables for private subnets |
| Task fails with `CannotPullContainerError` | ECR pull failed — execution role missing ECR permissions | Verify `AmazonECSTaskExecutionRolePolicy` is attached |
| Task fails with `ResourceNotFoundException` | Secrets Manager ARN wrong or secret does not exist | Verify secret names and ARNs match task definition |
| Container exits immediately (exit code 1) | App startup error — likely bad DATABASE_URL or REDIS_URL | Check CloudWatch logs for the traceback |
| Health check `UNHEALTHY` | DB or Redis unreachable from ECS subnet | Check security group rules: ECS SG → RDS SG on 5432, ECS SG → Redis SG on 6379 |
| Migration exit code 1 | DB connection failed or migration conflict | Check migration logs; verify `app_migrator` role exists (run `init-db.sql` bootstrap first) |
| Worker logs show `ConnectionRefusedError` | Redis not reachable | Same as health check — verify SG and Redis endpoint |

## 13. Day-2 Operations

### Update to new image

After a new image is pushed to ECR (e.g. on push to main), register new task definition
revisions with the new image, run migration, then update services.

**Step 1 — Register new revisions for all three task definitions:**

Update the `"image"` field in each JSON template to the new ECR image tag, then register:

```bash
# Edit the image in each task def JSON to the new tag, e.g.:
#   "image": "123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/saas-backend:abc1234"
# Then register new revisions:

aws ecs register-task-definition \
  --cli-input-json file://infra/ecs/migration-task-def.json \
  --region ap-southeast-1

aws ecs register-task-definition \
  --cli-input-json file://infra/ecs/backend-task-def.json \
  --region ap-southeast-1

aws ecs register-task-definition \
  --cli-input-json file://infra/ecs/worker-task-def.json \
  --region ap-southeast-1
```

**Step 2 — Run migration from the new revision:**

```bash
aws ecs run-task \
  --cluster saas-cluster \
  --task-definition saas-migration \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[{{PRIVATE_SUBNET_1}},{{PRIVATE_SUBNET_2}}],securityGroups=[{{ECS_SG}}],assignPublicIp=DISABLED}" \
  --region ap-southeast-1
```

Verify exit code 0 (see section 7).

**Step 3 — Update services to the new revision:**

```bash
aws ecs update-service \
  --cluster saas-cluster \
  --service saas-backend \
  --task-definition saas-backend \
  --region ap-southeast-1

aws ecs update-service \
  --cluster saas-cluster \
  --service saas-worker \
  --task-definition saas-worker \
  --region ap-southeast-1
```

Omitting a revision number (e.g. `saas-backend` instead of `saas-backend:5`) uses the
latest active revision, which is the one just registered.

### Add ALB (task 8.9)

When the ALB and target group are ready, update the backend service:

```bash
aws ecs update-service \
  --cluster saas-cluster \
  --service saas-backend \
  --load-balancers "targetGroupArn={{TARGET_GROUP_ARN}},containerName=backend,containerPort=8000" \
  --region ap-southeast-1
```
