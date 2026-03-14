#!/usr/bin/env bash
# provision-rds.sh — Create RDS PostgreSQL instance for ECS Fargate backend.
#
# Idempotent: skips resources that already exist.
# Requires: aws CLI configured with credentials for the target account.
#
# Creates:
#   - Custom parameter group (saas-pg16-params) with rds.force_ssl=1
#   - DB subnet group (saas-db-subnet-group) from two private-data subnets
#   - RDS instance (saas-db): PostgreSQL 16, db.t4g.micro, Single-AZ (MVP),
#     20 GB gp3, encrypted, deletion protection, no public access
#   - Master/admin password stored in /prod/rds-master-password
#
# Does NOT create: DB roles (app_user, app_migrator) — see init-db.sql + bootstrap task.

set -euo pipefail

# Prevent MSYS/Git Bash from converting /prod/... paths to Windows paths
export MSYS_NO_PATHCONV=1

REGION="${REGION:-ap-southeast-1}"
DB_INSTANCE_ID="${DB_INSTANCE_ID:-saas-db}"
DB_NAME="${DB_NAME:-saas_db}"
ENGINE="postgres"
ENGINE_VERSION="${ENGINE_VERSION:-16}"
INSTANCE_CLASS="${INSTANCE_CLASS:-db.t4g.micro}"
STORAGE_SIZE="${STORAGE_SIZE:-20}"
MAX_STORAGE="${MAX_STORAGE:-100}"
STORAGE_TYPE="gp3"
PARAM_GROUP_NAME="${PARAM_GROUP_NAME:-saas-pg16-params}"
PARAM_GROUP_FAMILY="postgres16"
SUBNET_GROUP_NAME="${SUBNET_GROUP_NAME:-saas-db-subnet-group}"
MASTER_USERNAME="${MASTER_USERNAME:-saas_admin}"
MASTER_SECRET_NAME="${MASTER_SECRET_NAME:-/prod/rds-master-password}"

# These must match VPC provisioning outputs (task 8.4)
PRIV_DATA_SUBNET_1="subnet-0ace4111d2f0c0e34"
PRIV_DATA_SUBNET_2="subnet-023b7e29ee06b21ae"
SG_RDS="sg-0b0457847c1bffdf5"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

generate_password() {
  if command -v openssl > /dev/null 2>&1; then
    openssl rand -base64 24 | tr -d '/+=' | head -c 32
  elif command -v python3 > /dev/null 2>&1; then
    python3 -c "import secrets; print(secrets.token_urlsafe(24)[:32], end='')"
  elif command -v python > /dev/null 2>&1; then
    python -c "import secrets; print(secrets.token_urlsafe(24)[:32], end='')"
  else
    echo "ERROR: No password generator available (need openssl, python3, or python)" >&2
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
echo "=== AWS Account: $ACCOUNT_ID | Region: $REGION ==="
echo ""

# Verify VPC resources exist
echo "--- Pre-flight checks ---"

for subnet in "$PRIV_DATA_SUBNET_1" "$PRIV_DATA_SUBNET_2"; do
  SUBNET_STATE=$(aws ec2 describe-subnets \
    --subnet-ids "$subnet" \
    --query "Subnets[0].State" --output text \
    --region "$REGION" 2>/dev/null || echo "NOT_FOUND")
  if [[ "$SUBNET_STATE" != "available" ]]; then
    echo "  ERROR: Subnet $subnet not available (state: $SUBNET_STATE)" >&2
    exit 1
  fi
  echo "  Subnet $subnet: available"
done

SG_EXISTS=$(aws ec2 describe-security-groups \
  --group-ids "$SG_RDS" \
  --query "SecurityGroups[0].GroupId" --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")
if [[ "$SG_EXISTS" == "NOT_FOUND" ]]; then
  echo "  ERROR: Security group $SG_RDS not found" >&2
  exit 1
fi
echo "  Security group $SG_RDS: exists"

# Verify SG has inbound 5432 rule from ECS SG
SG_ECS="sg-00a63148f50fe4cbd"
INBOUND_RULE=$(aws ec2 describe-security-group-rules \
  --filters "Name=group-id,Values=$SG_RDS" \
  --query "SecurityGroupRules[?IsEgress==\`false\` && FromPort==\`5432\` && ToPort==\`5432\` && ReferencedGroupInfo.GroupId==\`$SG_ECS\`] | [0].SecurityGroupRuleId" \
  --output text --region "$REGION" 2>/dev/null || echo "None")
if [[ "$INBOUND_RULE" == "None" || -z "$INBOUND_RULE" ]]; then
  echo "  WARNING: No inbound 5432 rule from ECS SG ($SG_ECS) found on RDS SG" >&2
  echo "  This must be fixed before ECS tasks can connect to the database" >&2
else
  echo "  Inbound 5432 from ECS SG ($SG_ECS): verified"
fi

echo ""

# ---------------------------------------------------------------------------
# 1. Custom Parameter Group
# ---------------------------------------------------------------------------

echo "--- Parameter Group ---"

PG_EXISTS=$(aws rds describe-db-parameter-groups \
  --db-parameter-group-name "$PARAM_GROUP_NAME" \
  --query "DBParameterGroups[0].DBParameterGroupName" --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")

if [[ "$PG_EXISTS" != "NOT_FOUND" ]]; then
  echo "  SKIP $PARAM_GROUP_NAME (already exists)"
else
  aws rds create-db-parameter-group \
    --db-parameter-group-name "$PARAM_GROUP_NAME" \
    --db-parameter-group-family "$PARAM_GROUP_FAMILY" \
    --description "SaaS PostgreSQL 16 — force SSL" \
    --tags "Key=Name,Value=$PARAM_GROUP_NAME" "Key=Project,Value=saas" "Key=Environment,Value=production" \
    --region "$REGION" --output text > /dev/null
  echo "  CREATED $PARAM_GROUP_NAME"
fi

# Enforce rds.force_ssl=1 on every run
aws rds modify-db-parameter-group \
  --db-parameter-group-name "$PARAM_GROUP_NAME" \
  --parameters "ParameterName=rds.force_ssl,ParameterValue=1,ApplyMethod=pending-reboot" \
  --region "$REGION" --output text > /dev/null
echo "  Enforced rds.force_ssl=1"

echo ""

# ---------------------------------------------------------------------------
# 2. DB Subnet Group
# ---------------------------------------------------------------------------

echo "--- DB Subnet Group ---"

SNG_EXISTS=$(aws rds describe-db-subnet-groups \
  --db-subnet-group-name "$SUBNET_GROUP_NAME" \
  --query "DBSubnetGroups[0].DBSubnetGroupName" --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")

if [[ "$SNG_EXISTS" != "NOT_FOUND" ]]; then
  echo "  SKIP $SUBNET_GROUP_NAME (already exists)"
else
  aws rds create-db-subnet-group \
    --db-subnet-group-name "$SUBNET_GROUP_NAME" \
    --db-subnet-group-description "SaaS private data subnets for RDS" \
    --subnet-ids "$PRIV_DATA_SUBNET_1" "$PRIV_DATA_SUBNET_2" \
    --tags "Key=Name,Value=$SUBNET_GROUP_NAME" "Key=Project,Value=saas" "Key=Environment,Value=production" \
    --region "$REGION" --output text > /dev/null
  echo "  CREATED $SUBNET_GROUP_NAME ($PRIV_DATA_SUBNET_1, $PRIV_DATA_SUBNET_2)"
fi

echo ""

# ---------------------------------------------------------------------------
# 3. Master/Admin Password
# ---------------------------------------------------------------------------

echo "--- Master Password ---"

MASTER_SECRET_EXISTS=$(aws secretsmanager describe-secret \
  --secret-id "$MASTER_SECRET_NAME" \
  --query "Name" --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")

if [[ "$MASTER_SECRET_EXISTS" != "NOT_FOUND" ]]; then
  echo "  SKIP $MASTER_SECRET_NAME (already exists)"
  MASTER_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id "$MASTER_SECRET_NAME" \
    --query "SecretString" --output text \
    --region "$REGION")
else
  MASTER_PASSWORD=$(generate_password)
  aws secretsmanager create-secret \
    --name "$MASTER_SECRET_NAME" \
    --secret-string "$MASTER_PASSWORD" \
    --description "RDS master/admin password — bootstrap only, never used at runtime" \
    --tags "Key=Project,Value=saas" "Key=Environment,Value=production" \
    --region "$REGION" --output text > /dev/null
  echo "  CREATED $MASTER_SECRET_NAME (password generated and stored)"
fi

echo ""

# ---------------------------------------------------------------------------
# 4. RDS Instance
# ---------------------------------------------------------------------------

echo "--- RDS Instance ---"

DB_EXISTS=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query "DBInstances[0].DBInstanceIdentifier" --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")

if [[ "$DB_EXISTS" != "NOT_FOUND" ]]; then
  echo "  SKIP $DB_INSTANCE_ID (already exists)"
else
  echo "  Creating $DB_INSTANCE_ID (Single-AZ MVP, $INSTANCE_CLASS, $STORAGE_SIZE GB gp3)..."
  echo "  This will take approximately 10-15 minutes."

  aws rds create-db-instance \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --db-instance-class "$INSTANCE_CLASS" \
    --engine "$ENGINE" \
    --engine-version "$ENGINE_VERSION" \
    --master-username "$MASTER_USERNAME" \
    --master-user-password "$MASTER_PASSWORD" \
    --db-name "$DB_NAME" \
    --allocated-storage "$STORAGE_SIZE" \
    --max-allocated-storage "$MAX_STORAGE" \
    --storage-type "$STORAGE_TYPE" \
    --storage-encrypted \
    --no-multi-az \
    --db-subnet-group-name "$SUBNET_GROUP_NAME" \
    --vpc-security-group-ids "$SG_RDS" \
    --db-parameter-group-name "$PARAM_GROUP_NAME" \
    --backup-retention-period 7 \
    --preferred-backup-window "16:00-17:00" \
    --preferred-maintenance-window "sun:14:00-sun:15:00" \
    --no-publicly-accessible \
    --deletion-protection \
    --copy-tags-to-snapshot \
    --tags "Key=Name,Value=$DB_INSTANCE_ID" "Key=Project,Value=saas" "Key=Environment,Value=production" \
    --region "$REGION" --output text > /dev/null

  echo "  CREATED $DB_INSTANCE_ID — waiting for availability..."
fi

# Always wait for instance to be available
echo "  Waiting for RDS instance to become available..."
aws rds wait db-instance-available \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --region "$REGION"
echo "  RDS instance is available"

echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

# Fetch endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query "DBInstances[0].Endpoint.Address" --output text \
  --region "$REGION")
RDS_PORT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query "DBInstances[0].Endpoint.Port" --output text \
  --region "$REGION")
RDS_ARN=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query "DBInstances[0].DBInstanceArn" --output text \
  --region "$REGION")

echo "=== RDS Provisioning Complete ==="
echo ""
echo "Resources created/verified:"
echo "  Instance:         $DB_INSTANCE_ID"
echo "  ARN:              $RDS_ARN"
echo "  Endpoint:         $RDS_ENDPOINT"
echo "  Port:             $RDS_PORT"
echo "  Engine:           PostgreSQL $ENGINE_VERSION"
echo "  Instance class:   $INSTANCE_CLASS"
echo "  Storage:          $STORAGE_SIZE GB $STORAGE_TYPE (max $MAX_STORAGE GB)"
echo "  Multi-AZ:         No (MVP — upgrade later with: aws rds modify-db-instance --multi-az)"
echo "  Encryption:       At rest (AWS-managed key) + in transit (rds.force_ssl=1)"
echo "  DB name:          $DB_NAME"
echo "  Master user:      $MASTER_USERNAME (bootstrap only)"
echo "  Master secret:    $MASTER_SECRET_NAME"
echo "  Param group:      $PARAM_GROUP_NAME"
echo "  Subnet group:     $SUBNET_GROUP_NAME"
echo "  Security group:   $SG_RDS"
echo "  Backup:           7-day retention, 16:00-17:00 UTC"
echo "  Deletion protect: Enabled"
echo ""
echo "Next steps:"
echo "  1. Run one-off ECS bootstrap task as $MASTER_USERNAME to create app_user + app_migrator (init-db.sql)"
echo "  2. Create /prod/database-url-migrator in Secrets Manager (app_migrator credentials)"
echo "  3. Run one-off ECS migration task using /prod/database-url-migrator (alembic upgrade head)"
echo "  4. Update /prod/database-url in Secrets Manager (app_user credentials)"
echo "  5. Force new ECS deployment for backend service(s)"
echo "  6. Smoke test /api/v1/health"
