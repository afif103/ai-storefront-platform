#!/usr/bin/env bash
# provision-redis.sh — Create ElastiCache Redis for ECS Fargate backend.
#
# Idempotent: skips resources that already exist.
# Requires: aws CLI configured with credentials for the target account.
#
# Creates:
#   - ElastiCache subnet group (saas-redis-subnet-group) from two private-data subnets
#   - Replication group (saas-prod-redis): Redis 7.x, cache.t4g.micro, Single-AZ (MVP),
#     in-transit + at-rest encryption, no AUTH token
#
# Does NOT create or update: /prod/redis-url secret — do that manually after provisioning.
# Does NOT run ECS connectivity proof — do that as a separate step after secret update.

set -euo pipefail

# Prevent MSYS/Git Bash from converting /prod/... paths to Windows paths
export MSYS_NO_PATHCONV=1

REGION="${REGION:-ap-southeast-1}"
REPLICATION_GROUP_ID="${REPLICATION_GROUP_ID:-saas-prod-redis}"
ENGINE_VERSION="${ENGINE_VERSION:-7.1}"
NODE_TYPE="${NODE_TYPE:-cache.t4g.micro}"
SUBNET_GROUP_NAME="${SUBNET_GROUP_NAME:-saas-redis-subnet-group}"
SNAPSHOT_RETENTION="${SNAPSHOT_RETENTION:-1}"

# These must match VPC provisioning outputs (task 8.4).
# Re-verify against live AWS state before running.
PRIV_DATA_SUBNET_1="subnet-0ace4111d2f0c0e34"
PRIV_DATA_SUBNET_2="subnet-023b7e29ee06b21ae"
SG_REDIS="sg-033c715b2d0326f64"
SG_ECS="sg-00a63148f50fe4cbd"

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
echo "=== AWS Account: $ACCOUNT_ID | Region: $REGION ==="
echo ""

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
  --group-ids "$SG_REDIS" \
  --query "SecurityGroups[0].GroupId" --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")
if [[ "$SG_EXISTS" == "NOT_FOUND" ]]; then
  echo "  ERROR: Security group $SG_REDIS not found" >&2
  exit 1
fi
echo "  Security group $SG_REDIS: exists"

# Verify Redis SG has inbound 6379 from ECS SG
INBOUND_RULE=$(aws ec2 describe-security-group-rules \
  --filters "Name=group-id,Values=$SG_REDIS" \
  --query "SecurityGroupRules[?IsEgress==\`false\` && FromPort==\`6379\` && ToPort==\`6379\` && ReferencedGroupInfo.GroupId==\`$SG_ECS\`] | [0].SecurityGroupRuleId" \
  --output text --region "$REGION" 2>/dev/null || echo "None")
if [[ "$INBOUND_RULE" == "None" || -z "$INBOUND_RULE" ]]; then
  echo "  ERROR: No inbound 6379 rule from ECS SG ($SG_ECS) found on Redis SG ($SG_REDIS)" >&2
  echo "  This must be fixed before ECS tasks can connect to Redis" >&2
  exit 1
fi
echo "  Inbound 6379 from ECS SG ($SG_ECS): verified ($INBOUND_RULE)"

# Verify ECS SG has outbound 6379 to Redis SG
OUTBOUND_RULE=$(aws ec2 describe-security-group-rules \
  --filters "Name=group-id,Values=$SG_ECS" \
  --query "SecurityGroupRules[?IsEgress==\`true\` && FromPort==\`6379\` && ToPort==\`6379\` && ReferencedGroupInfo.GroupId==\`$SG_REDIS\`] | [0].SecurityGroupRuleId" \
  --output text --region "$REGION" 2>/dev/null || echo "None")
if [[ "$OUTBOUND_RULE" == "None" || -z "$OUTBOUND_RULE" ]]; then
  echo "  ERROR: No outbound 6379 rule to Redis SG ($SG_REDIS) found on ECS SG ($SG_ECS)" >&2
  echo "  This must be fixed before ECS tasks can connect to Redis" >&2
  exit 1
fi
echo "  Outbound 6379 to Redis SG ($SG_REDIS) from ECS SG: verified ($OUTBOUND_RULE)"

echo ""

# ---------------------------------------------------------------------------
# 1. ElastiCache Subnet Group
# ---------------------------------------------------------------------------

echo "--- ElastiCache Subnet Group ---"

SNG_EXISTS=$(aws elasticache describe-cache-subnet-groups \
  --cache-subnet-group-name "$SUBNET_GROUP_NAME" \
  --query "CacheSubnetGroups[0].CacheSubnetGroupName" --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")

if [[ "$SNG_EXISTS" != "NOT_FOUND" ]]; then
  echo "  SKIP $SUBNET_GROUP_NAME (already exists)"
else
  aws elasticache create-cache-subnet-group \
    --cache-subnet-group-name "$SUBNET_GROUP_NAME" \
    --cache-subnet-group-description "SaaS private data subnets for ElastiCache" \
    --subnet-ids "$PRIV_DATA_SUBNET_1" "$PRIV_DATA_SUBNET_2" \
    --tags "Key=Name,Value=$SUBNET_GROUP_NAME" "Key=Project,Value=saas" "Key=Environment,Value=production" \
    --region "$REGION" --output text > /dev/null
  echo "  CREATED $SUBNET_GROUP_NAME ($PRIV_DATA_SUBNET_1, $PRIV_DATA_SUBNET_2)"
fi

echo ""

# ---------------------------------------------------------------------------
# 2. Replication Group
# ---------------------------------------------------------------------------

echo "--- Replication Group ---"

RG_EXISTS=$(aws elasticache describe-replication-groups \
  --replication-group-id "$REPLICATION_GROUP_ID" \
  --query "ReplicationGroups[0].ReplicationGroupId" --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")

if [[ "$RG_EXISTS" != "NOT_FOUND" ]]; then
  echo "  SKIP $REPLICATION_GROUP_ID (already exists)"
else
  echo "  Creating $REPLICATION_GROUP_ID (Single-AZ MVP, $NODE_TYPE, Redis $ENGINE_VERSION)..."
  echo "  This will take approximately 5-10 minutes."

  aws elasticache create-replication-group \
    --replication-group-id "$REPLICATION_GROUP_ID" \
    --replication-group-description "SaaS Redis - Single-AZ MVP" \
    --engine redis \
    --engine-version "$ENGINE_VERSION" \
    --cache-node-type "$NODE_TYPE" \
    --num-node-groups 1 \
    --replicas-per-node-group 0 \
    --cache-subnet-group-name "$SUBNET_GROUP_NAME" \
    --security-group-ids "$SG_REDIS" \
    --transit-encryption-enabled \
    --at-rest-encryption-enabled \
    --snapshot-retention-limit "$SNAPSHOT_RETENTION" \
    --snapshot-window "17:00-18:00" \
    --preferred-maintenance-window "sun:15:00-sun:16:00" \
    --tags "Key=Name,Value=$REPLICATION_GROUP_ID" "Key=Project,Value=saas" "Key=Environment,Value=production" \
    --region "$REGION" --output text > /dev/null

  echo "  CREATED $REPLICATION_GROUP_ID — waiting for availability..."
fi

# Always wait for replication group to be available
echo "  Waiting for replication group to become available..."
aws elasticache wait replication-group-available \
  --replication-group-id "$REPLICATION_GROUP_ID" \
  --region "$REGION"
echo "  Replication group is available"

echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

# Fetch primary endpoint
PRIMARY_ENDPOINT=$(aws elasticache describe-replication-groups \
  --replication-group-id "$REPLICATION_GROUP_ID" \
  --query "ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.Address" --output text \
  --region "$REGION")
PRIMARY_PORT=$(aws elasticache describe-replication-groups \
  --replication-group-id "$REPLICATION_GROUP_ID" \
  --query "ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.Port" --output text \
  --region "$REGION")
TRANSIT_ENCRYPTION=$(aws elasticache describe-replication-groups \
  --replication-group-id "$REPLICATION_GROUP_ID" \
  --query "ReplicationGroups[0].TransitEncryptionEnabled" --output text \
  --region "$REGION")
ATREST_ENCRYPTION=$(aws elasticache describe-replication-groups \
  --replication-group-id "$REPLICATION_GROUP_ID" \
  --query "ReplicationGroups[0].AtRestEncryptionEnabled" --output text \
  --region "$REGION")

echo "=== ElastiCache Provisioning Complete ==="
echo ""
echo "Resources created/verified:"
echo "  Replication group: $REPLICATION_GROUP_ID"
echo "  Primary endpoint:  $PRIMARY_ENDPOINT"
echo "  Port:              $PRIMARY_PORT"
echo "  Engine:            Redis $ENGINE_VERSION"
echo "  Node type:         $NODE_TYPE"
echo "  Multi-AZ:          No (MVP — upgrade later by adding replica + enabling automatic failover)"
echo "  In-transit encrypt: $TRANSIT_ENCRYPTION"
echo "  At-rest encrypt:   $ATREST_ENCRYPTION"
echo "  Subnet group:      $SUBNET_GROUP_NAME"
echo "  Security group:    $SG_REDIS"
echo "  Snapshot:          ${SNAPSHOT_RETENTION}-day retention, 17:00-18:00 UTC"
echo ""
echo "Next steps:"
echo "  1. Update /prod/redis-url in Secrets Manager:"
echo "     rediss://$PRIMARY_ENDPOINT:$PRIMARY_PORT/0"
echo "  2. Run ECS connectivity proof (one-off task with REDIS_URL from secret)"
echo "  3. Fill in infra/redis/redis-outputs.md with values above"
