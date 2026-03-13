#!/usr/bin/env bash
# provision-ecs-prereqs.sh — Create ECS runtime prerequisites in AWS.
#
# Idempotent: skips resources that already exist.
# Requires: aws CLI configured with credentials for the target account.
#
# Creates:
#   - ECS cluster (saas-cluster)
#   - CloudWatch log groups (/ecs/saas-backend, /ecs/saas-worker)
#   - IAM execution role (saas-ecs-execution-role) — fully provisioned
#   - IAM task role (saas-backend-task-role) — trust policy only, no runtime permissions
#   - Secrets Manager secrets (5) — placeholder values for DATABASE_URL, REDIS_URL;
#     real random values for SECRET_KEY, IP_HASH_SALT; placeholder for AI_API_KEY
#
# Does NOT create: ECS services, task definitions, ALB, VPC, RDS, Redis, S3.

set -euo pipefail

REGION="ap-southeast-1"
CLUSTER_NAME="saas-cluster"
LOG_GROUP_BACKEND="/ecs/saas-backend"
LOG_GROUP_WORKER="/ecs/saas-worker"
LOG_RETENTION_DAYS=90
EXEC_ROLE_NAME="saas-ecs-execution-role"
TASK_ROLE_NAME="saas-backend-task-role"
SECRET_NAMES=(
  "/prod/database-url"
  "/prod/redis-url"
  "/prod/secret-key"
  "/prod/ai-api-key"
  "/prod/ip-hash-salt"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

generate_random_base64() {
  local bytes="$1"
  if command -v openssl &>/dev/null; then
    openssl rand -base64 "$bytes"
  elif command -v python3 &>/dev/null; then
    python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes($bytes)).decode())"
  elif command -v python &>/dev/null; then
    python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes($bytes)).decode())"
  else
    echo "ERROR: No openssl or python found for random generation" >&2
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Pre-flight: print account ID and region
# ---------------------------------------------------------------------------

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
echo "=== AWS Account: $ACCOUNT_ID | Region: $REGION ==="
echo ""

# ---------------------------------------------------------------------------
# 1. Secrets Manager — create secrets with placeholder/random values
# ---------------------------------------------------------------------------

echo "--- Secrets Manager ---"

declare -A SECRET_ARNS

SECRET_KEY_VALUE=$(generate_random_base64 48)
IP_HASH_SALT_VALUE=$(generate_random_base64 24)

declare -A SECRET_VALUES=(
  ["/prod/database-url"]="postgresql+asyncpg://placeholder:placeholder@localhost:5432/saas_db"
  ["/prod/redis-url"]="redis://placeholder:6379/0"
  ["/prod/secret-key"]="$SECRET_KEY_VALUE"
  ["/prod/ai-api-key"]="placeholder-update-before-deploy"
  ["/prod/ip-hash-salt"]="$IP_HASH_SALT_VALUE"
)

for secret_name in "${SECRET_NAMES[@]}"; do
  existing_arn=$(aws secretsmanager describe-secret \
    --secret-id "$secret_name" \
    --query ARN --output text \
    --region "$REGION" 2>/dev/null || echo "NOT_FOUND")

  if [[ "$existing_arn" != "NOT_FOUND" ]]; then
    echo "  SKIP $secret_name (already exists)"
    SECRET_ARNS["$secret_name"]="$existing_arn"
  else
    create_output=$(aws secretsmanager create-secret \
      --name "$secret_name" \
      --secret-string "${SECRET_VALUES[$secret_name]}" \
      --region "$REGION" \
      --query ARN --output text)
    echo "  CREATED $secret_name"
    SECRET_ARNS["$secret_name"]="$create_output"
  fi
done

echo ""

# ---------------------------------------------------------------------------
# 2. ECS Cluster
# ---------------------------------------------------------------------------

echo "--- ECS Cluster ---"

cluster_status=$(aws ecs describe-clusters \
  --clusters "$CLUSTER_NAME" \
  --query "clusters[0].status" --output text \
  --region "$REGION" 2>/dev/null || echo "MISSING")

if [[ "$cluster_status" == "ACTIVE" ]]; then
  echo "  SKIP $CLUSTER_NAME (already exists, ACTIVE)"
else
  aws ecs create-cluster \
    --cluster-name "$CLUSTER_NAME" \
    --capacity-providers FARGATE \
    --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
    --region "$REGION" \
    --query "cluster.status" --output text
  echo "  CREATED $CLUSTER_NAME"
fi

echo ""

# ---------------------------------------------------------------------------
# 3. CloudWatch Log Groups
# ---------------------------------------------------------------------------

echo "--- CloudWatch Log Groups ---"

for log_group in "$LOG_GROUP_BACKEND" "$LOG_GROUP_WORKER"; do
  existing=$(aws logs describe-log-groups \
    --log-group-name-prefix "$log_group" \
    --query "logGroups[?logGroupName=='$log_group'].logGroupName" \
    --output text --region "$REGION" 2>/dev/null || echo "")

  if [[ "$existing" == "$log_group" ]]; then
    echo "  SKIP $log_group (already exists)"
  else
    aws logs create-log-group \
      --log-group-name "$log_group" \
      --region "$REGION"
    echo "  CREATED $log_group"
  fi

  aws logs put-retention-policy \
    --log-group-name "$log_group" \
    --retention-in-days "$LOG_RETENTION_DAYS" \
    --region "$REGION"
done

echo ""

# ---------------------------------------------------------------------------
# 4. IAM Execution Role (saas-ecs-execution-role)
#    - ECR pull + CloudWatch logs (managed policy)
#    - Secrets Manager read on the 5 real secret ARNs (inline policy)
# ---------------------------------------------------------------------------

echo "--- IAM Execution Role: $EXEC_ROLE_NAME ---"

ECS_TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ecs-tasks.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}'

existing_exec_role=$(aws iam get-role \
  --role-name "$EXEC_ROLE_NAME" \
  --query "Role.Arn" --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$existing_exec_role" != "NOT_FOUND" ]]; then
  echo "  SKIP role creation (already exists)"
else
  aws iam create-role \
    --role-name "$EXEC_ROLE_NAME" \
    --assume-role-policy-document "$ECS_TRUST_POLICY" \
    --query "Role.Arn" --output text
  echo "  CREATED role"
fi

# Attach managed policy (idempotent)
aws iam attach-role-policy \
  --role-name "$EXEC_ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" 2>/dev/null || true
echo "  Managed policy AmazonECSTaskExecutionRolePolicy attached"

# Build inline secrets policy from real ARNs
SECRETS_RESOURCE_ARNS=""
for secret_name in "${SECRET_NAMES[@]}"; do
  arn="${SECRET_ARNS[$secret_name]}"
  if [[ -n "$SECRETS_RESOURCE_ARNS" ]]; then
    SECRETS_RESOURCE_ARNS="$SECRETS_RESOURCE_ARNS,"
  fi
  SECRETS_RESOURCE_ARNS="$SECRETS_RESOURCE_ARNS\"$arn\""
done

SECRETS_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": [$SECRETS_RESOURCE_ARNS]
    }
  ]
}
EOF
)

aws iam put-role-policy \
  --role-name "$EXEC_ROLE_NAME" \
  --policy-name "SecretsReadPolicy" \
  --policy-document "$SECRETS_POLICY"
echo "  Inline policy SecretsReadPolicy applied (5 real secret ARNs)"

echo ""

# ---------------------------------------------------------------------------
# 5. IAM Task Role (saas-backend-task-role)
#    - Trust policy only. Runtime permissions (S3, SES, Cognito) deferred
#      until those resources exist.
# ---------------------------------------------------------------------------

echo "--- IAM Task Role: $TASK_ROLE_NAME ---"

existing_task_role=$(aws iam get-role \
  --role-name "$TASK_ROLE_NAME" \
  --query "Role.Arn" --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$existing_task_role" != "NOT_FOUND" ]]; then
  echo "  SKIP role creation (already exists)"
else
  aws iam create-role \
    --role-name "$TASK_ROLE_NAME" \
    --assume-role-policy-document "$ECS_TRUST_POLICY" \
    --query "Role.Arn" --output text
  echo "  CREATED role (trust policy only)"
fi

echo "  NOTE: No runtime permissions attached yet."
echo "        Add S3/SES/Cognito policies after those resources are provisioned."

echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo "=== P2 Provisioning Complete ==="
echo ""
echo "Resources created/verified:"
echo "  Cluster:    $CLUSTER_NAME"
echo "  Log groups: $LOG_GROUP_BACKEND, $LOG_GROUP_WORKER"
echo "  Exec role:  $EXEC_ROLE_NAME"
echo "  Task role:  $TASK_ROLE_NAME (trust policy only)"
echo "  Secrets:    ${SECRET_NAMES[*]}"
echo ""
echo "Next steps:"
echo "  1. Populate /prod/database-url and /prod/redis-url with real values after 8.5/8.6"
echo "  2. Populate /prod/ai-api-key with real provider key before AI features go live"
echo "  3. Add S3/SES/Cognito inline policy to $TASK_ROLE_NAME after those resources exist"
echo "  4. Replace {{PLACEHOLDER}} values in task definition JSONs with real ARNs"
echo "  5. Register task definitions and proceed to P3 (migration + services)"
