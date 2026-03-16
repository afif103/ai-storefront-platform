# ECS Environment & Secrets Contract

All environment variables used by the backend application (`backend/app/core/config.py`),
classified by source and service.

## Variable Reference

| Variable | Required | Source | Used By | Notes |
|----------|----------|--------|---------|-------|
| `DATABASE_URL` | Yes | Secrets Manager (`/prod/database-url`) | API, Worker | `postgresql+asyncpg://app_user:pass@host:5432/db` (runtime, RLS-enforced) |
| `DATABASE_URL` | Yes | Secrets Manager (`/prod/database-url-migrator`) | Migration | Same env var name, different secret source. `app_migrator` role (DDL + DML). See `migration-task-def.json`. |
| `REDIS_URL` | Yes | Secrets Manager | API, Worker | `rediss://host:6379/0?ssl_cert_reqs=required` — TLS required. Celery broker + AI quota |
| `SECRET_KEY` | Yes | Secrets Manager | API | JWT signing (mock mode). Set strong value regardless. |
| `AI_API_KEY` | Yes | Secrets Manager | API, Worker | Provider API key (OpenAI/Groq/Anthropic) |
| `IP_HASH_SALT` | Yes | Secrets Manager | API | Privacy-sensitive salt for IP hashing |
| `TELEGRAM_BOT_TOKEN` | No | Secrets Manager | Worker | Omit for MVP. Add to Secrets Manager when Telegram notifications are enabled. |
| `ENVIRONMENT` | Yes | Plain env | API, Worker, Migration | `production` |
| `DEBUG` | Yes | Plain env | API, Worker | `false` |
| `COGNITO_MOCK` | Yes | Plain env | API | `false` in production |
| `AWS_REGION` | Yes | Plain env | API, Worker | `ap-southeast-1` |
| `COGNITO_REGION` | Yes | Plain env | API | `ap-southeast-1` |
| `COGNITO_USER_POOL_ID` | Yes | Plain env | API | Cognito pool ID (not a secret — public in JWKS URL) |
| `COGNITO_CLIENT_ID` | Yes | Plain env | API | OAuth2 client ID (not a secret — sent by frontend) |
| `S3_BUCKET` | Yes | Plain env | API, Worker | e.g. `saas-media-prod-123456789012` |
| `SES_SENDER_EMAIL` | Yes | Plain env | Worker | Verified SES sender address |
| `SES_REGION` | Yes | Plain env | Worker | `ap-southeast-1` |
| `ALLOWED_ORIGINS` | Yes | Plain env | API | Comma-separated. e.g. `https://app.yourdomain.com` |
| `AI_PROVIDER` | Yes | Plain env | API, Worker | `openai` (default) |
| `AI_MODEL` | Yes | Plain env | API, Worker | `gpt-4o` (default) |
| `AI_MAX_INPUT_CHARS` | No | Plain env | API | Default `2000` |
| `AI_MAX_OUTPUT_TOKENS` | No | Plain env | API | Default `1024` |

## Omitted Variables

| Variable | Reason |
|----------|--------|
| `AWS_ACCESS_KEY_ID` | Task role provides credentials via boto3 default chain. Do not set. |
| `AWS_SECRET_ACCESS_KEY` | Same as above. |
| `S3_ENDPOINT_URL` | MinIO only — local dev. Omit for real S3. |
| `S3_PUBLIC_ENDPOINT` | MinIO URL rewriting — local dev only. |

### Why omitting AWS credentials works

All three boto3 clients in the codebase use the default credential chain:

- **`storage.py`** (`s3`): passes explicit keys only if both `AWS_ACCESS_KEY_ID` and
  `AWS_SECRET_ACCESS_KEY` are non-None in settings. Both default to `None`, so on ECS
  with no env override, boto3 falls through to the task role.
- **`email_sender.py`** (`ses`): no explicit credentials — uses default chain.
- **`auth_service.py`** (`cognito-idp`): no explicit credentials — uses default chain.

## IAM Role Separation

Three IAM roles serve distinct purposes. They must not be conflated.

| Role | Used by | Purpose | Provisioned in |
|------|---------|---------|----------------|
| `github-actions-ci` | GitHub Actions CI | OIDC assume-role for ECR image push | 8.8a (exists, not touched by ECS work) |
| `saas-ecs-execution-role` | ECS agent | Bootstrap tasks: ECR pull, CloudWatch logs, inject Secrets Manager values | 8.8b P2 (fully provisioned) |
| `saas-backend-task-role` | Running app code | Runtime AWS access: S3, SES, Cognito via boto3 default credential chain | 8.8b P2 (trust policy only); runtime permissions added after S3/SES/Cognito exist |

### Execution Role (`saas-ecs-execution-role`)

**Trust policy:** `ecs-tasks.amazonaws.com`

**Purpose:** Used by the ECS agent (not the app code) to bootstrap the task.

| Permission | Reason |
|------------|--------|
| `ecr:GetAuthorizationToken` | Pull image from ECR |
| `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer` | Pull image layers |
| `logs:CreateLogStream`, `logs:PutLogEvents` | Write container logs to CloudWatch |
| `secretsmanager:GetSecretValue` on specific ARNs | Inject secrets into container env at start |

Attach `AmazonECSTaskExecutionRolePolicy` (managed) + inline policy for Secrets Manager
scoped to the specific secret ARNs created in `provision-ecs-prereqs.sh`.

### Task Role (`saas-backend-task-role`)

**Trust policy:** `ecs-tasks.amazonaws.com`

**Purpose:** Used by the running application code at runtime.

**Current state:** Shared ECS task role (`saas-backend-task-role`) now has inline S3 object-access policy (`S3MediaAccess`). Only backend code currently uses S3; worker remains unchanged functionally. Remaining runtime permissions are deferred until the target resources exist.

| Permission | Resource | Reason | Status |
|------------|----------|--------|--------|
| `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` | `arn:aws:s3:::saas-media-prod-701893741240/*` | Presigned URL generation + delete | **Attached** (inline `S3MediaAccess` on shared task role) |
| `ses:SendEmail`, `ses:SendRawEmail` | `*` (or scoped to verified identity) | Email notifications | Deferred until SES identity exists |
| `cognito-idp:InitiateAuth` | User pool ARN | Token refresh flow | Deferred until Cognito pool exists |

**Not needed on task role:** Secrets Manager (execution role's job),
ECR (execution role), CloudWatch Logs (execution role).
