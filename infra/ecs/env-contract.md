# ECS Environment & Secrets Contract

All environment variables used by the backend application (`backend/app/core/config.py`),
classified by source and service.

## Variable Reference

| Variable | Required | Source | Used By | Notes |
|----------|----------|--------|---------|-------|
| `DATABASE_URL` | Yes | Secrets Manager | API, Worker, Migration | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | Yes | Secrets Manager | API, Worker | `redis://host:6379/0` — Celery broker + AI quota |
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

## IAM Role Responsibilities

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
scoped to the specific secret ARNs listed above.

### Task Role (`saas-backend-task-role`)

**Trust policy:** `ecs-tasks.amazonaws.com`

**Purpose:** Used by the running application code at runtime.

| Permission | Resource | Reason |
|------------|----------|--------|
| `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` | `arn:aws:s3:::{{S3_BUCKET}}/*` | Presigned URL generation + delete |
| `s3:ListBucket` | `arn:aws:s3:::{{S3_BUCKET}}` | Bucket-level operations if needed |
| `ses:SendEmail`, `ses:SendRawEmail` | `*` (or scoped to verified identity) | Email notifications |
| `cognito-idp:InitiateAuth` | User pool ARN | Token refresh flow |

**Not needed on task role:** Secrets Manager (that is the execution role's job),
ECR (execution role), CloudWatch Logs (execution role).
