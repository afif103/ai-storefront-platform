#!/usr/bin/env bash
# provision-vpc.sh — Create VPC and networking prerequisites for ECS Fargate.
#
# Idempotent: skips resources that already exist.
# Requires: aws CLI configured with credentials for the target account.
#
# Creates:
#   - VPC (saas-vpc, 10.0.0.0/16) with DNS support + DNS hostnames
#   - 6 subnets across 2 AZs:
#       public-1/2 (10.0.0.0/24, 10.0.1.0/24)
#       private-app-1/2 (10.0.10.0/24, 10.0.11.0/24)
#       private-data-1/2 (10.0.20.0/24, 10.0.21.0/24)
#   - Internet Gateway (saas-igw) attached to VPC
#   - NAT Gateway (saas-nat) in public-1 with Elastic IP
#   - 3 route tables: 1 public, 2 private (per-AZ)
#   - S3 Gateway VPC Endpoint on private route tables
#   - 4 security groups: ALB, ECS tasks, RDS, Redis
#
# Does NOT create: RDS, ElastiCache, S3 bucket, ECS services, ALB.

set -euo pipefail

# Prevent MSYS/Git Bash from converting /prod/... paths to Windows paths
export MSYS_NO_PATHCONV=1

REGION="ap-southeast-1"
VPC_CIDR="10.0.0.0/16"
VPC_NAME="saas-vpc"

# Subnet CIDRs (public / private-app / private-data x 2 AZs)
PUBLIC_1_CIDR="10.0.0.0/24"
PUBLIC_2_CIDR="10.0.1.0/24"
PRIVATE_APP_1_CIDR="10.0.10.0/24"
PRIVATE_APP_2_CIDR="10.0.11.0/24"
PRIVATE_DATA_1_CIDR="10.0.20.0/24"
PRIVATE_DATA_2_CIDR="10.0.21.0/24"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Apply standard tags to a resource.
tag_resource() {
  local resource_id="$1" name="$2"
  aws ec2 create-tags --resources "$resource_id" \
    --tags "Key=Name,Value=$name" "Key=Project,Value=saas" "Key=Environment,Value=production" \
    --region "$REGION"
}

# Look up a resource by Name tag. Returns ID or "NOT_FOUND".
find_by_name() {
  local resource_type="$1" name="$2"
  local result
  result=$(aws ec2 describe-tags \
    --filters "Name=resource-type,Values=$resource_type" \
              "Name=key,Values=Name" \
              "Name=value,Values=$name" \
    --query "Tags[0].ResourceId" --output text \
    --region "$REGION" 2>/dev/null || echo "None")
  if [[ "$result" == "None" || -z "$result" ]]; then
    echo "NOT_FOUND"
  else
    echo "$result"
  fi
}

# Create or find a subnet. Prints ID to stdout, status to stderr.
create_subnet() {
  local name="$1" cidr="$2" az="$3"
  local subnet_id
  subnet_id=$(find_by_name "subnet" "$name")
  if [[ "$subnet_id" != "NOT_FOUND" ]]; then
    echo "  SKIP $name (already exists: $subnet_id)" >&2
    echo "$subnet_id"
    return
  fi
  subnet_id=$(aws ec2 create-subnet \
    --vpc-id "$VPC_ID" \
    --cidr-block "$cidr" \
    --availability-zone "$az" \
    --query "Subnet.SubnetId" --output text \
    --region "$REGION")
  tag_resource "$subnet_id" "$name"
  echo "  CREATED $name ($subnet_id) in $az" >&2
  echo "$subnet_id"
}

# Create or find a route table. Returns ID only. Does NOT associate subnets.
# Prints ID to stdout, status to stderr.
create_route_table() {
  local vpc_id="$1" name="$2"
  local rt_id
  rt_id=$(find_by_name "route-table" "$name")
  if [[ "$rt_id" != "NOT_FOUND" ]]; then
    echo "  SKIP $name (already exists: $rt_id)" >&2
    echo "$rt_id"
    return
  fi
  rt_id=$(aws ec2 create-route-table \
    --vpc-id "$vpc_id" \
    --query "RouteTable.RouteTableId" --output text \
    --region "$REGION")
  tag_resource "$rt_id" "$name"
  echo "  CREATED $name ($rt_id)" >&2
  echo "$rt_id"
}

# Ensure a subnet is associated with a route table. Idempotent:
# skips if the subnet is already associated with the target RT.
ensure_rt_association() {
  local rt_id="$1" subnet_id="$2"
  local current_rt
  current_rt=$(aws ec2 describe-route-tables \
    --filters "Name=association.subnet-id,Values=$subnet_id" \
    --query "RouteTables[0].RouteTableId" --output text \
    --region "$REGION" 2>/dev/null || echo "None")
  if [[ "$current_rt" == "$rt_id" ]]; then
    echo "  Association $subnet_id -> $rt_id (already correct)" >&2
    return
  fi
  # If subnet has an explicit association to a different RT, replace it
  if [[ "$current_rt" != "None" && -n "$current_rt" && "$current_rt" != "$rt_id" ]]; then
    local assoc_id
    assoc_id=$(aws ec2 describe-route-tables \
      --route-table-ids "$current_rt" \
      --query "RouteTables[0].Associations[?SubnetId=='$subnet_id'].RouteTableAssociationId | [0]" \
      --output text --region "$REGION" 2>/dev/null || echo "None")
    if [[ "$assoc_id" != "None" && -n "$assoc_id" ]]; then
      aws ec2 replace-route-table-association \
        --association-id "$assoc_id" \
        --route-table-id "$rt_id" \
        --region "$REGION" --output text > /dev/null
      echo "  Association $subnet_id -> $rt_id (replaced from $current_rt)" >&2
      return
    fi
  fi
  # No explicit association yet — create one
  aws ec2 associate-route-table \
    --route-table-id "$rt_id" \
    --subnet-id "$subnet_id" \
    --region "$REGION" --output text > /dev/null
  echo "  Association $subnet_id -> $rt_id (created)" >&2
}

# Create or find a security group. Revokes default allow-all egress on every run.
# Prints ID to stdout, status to stderr.
create_sg() {
  local vpc_id="$1" name="$2" description="$3"
  local sg_id
  sg_id=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$vpc_id" "Name=group-name,Values=$name" \
    --query "SecurityGroups[0].GroupId" --output text \
    --region "$REGION" 2>/dev/null || echo "None")
  if [[ "$sg_id" != "None" && -n "$sg_id" ]]; then
    aws ec2 revoke-security-group-egress \
      --group-id "$sg_id" \
      --ip-permissions '[{"IpProtocol":"-1","FromPort":-1,"ToPort":-1,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]' \
      --region "$REGION" > /dev/null 2>&1 || true
    echo "  SKIP $name (already exists: $sg_id) — default egress enforced" >&2
    echo "$sg_id"
    return
  fi
  sg_id=$(aws ec2 create-security-group \
    --group-name "$name" \
    --description "$description" \
    --vpc-id "$vpc_id" \
    --query "GroupId" --output text \
    --region "$REGION")
  tag_resource "$sg_id" "$name"
  aws ec2 revoke-security-group-egress \
    --group-id "$sg_id" \
    --ip-permissions '[{"IpProtocol":"-1","FromPort":-1,"ToPort":-1,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]' \
    --region "$REGION" > /dev/null 2>&1 || true
  echo "  CREATED $name ($sg_id) — default egress revoked" >&2
  echo "$sg_id"
}

# Helper: add ingress from another SG (idempotent)
add_ingress() {
  local sg_id="$1" port="$2" source_sg="$3"
  local perms="[{\"IpProtocol\":\"tcp\",\"FromPort\":$port,\"ToPort\":$port,\"UserIdGroupPairs\":[{\"GroupId\":\"$source_sg\"}]}]"
  aws ec2 authorize-security-group-ingress \
    --group-id "$sg_id" \
    --ip-permissions "$perms" \
    --region "$REGION" 2>/dev/null || true
}

# Helper: add ingress from CIDR (idempotent)
add_ingress_cidr() {
  local sg_id="$1" port="$2" cidr="$3"
  local perms="[{\"IpProtocol\":\"tcp\",\"FromPort\":$port,\"ToPort\":$port,\"IpRanges\":[{\"CidrIp\":\"$cidr\"}]}]"
  aws ec2 authorize-security-group-ingress \
    --group-id "$sg_id" \
    --ip-permissions "$perms" \
    --region "$REGION" 2>/dev/null || true
}

# Helper: add egress to another SG (idempotent)
add_egress() {
  local sg_id="$1" port="$2" dest_sg="$3"
  local perms="[{\"IpProtocol\":\"tcp\",\"FromPort\":$port,\"ToPort\":$port,\"UserIdGroupPairs\":[{\"GroupId\":\"$dest_sg\"}]}]"
  aws ec2 authorize-security-group-egress \
    --group-id "$sg_id" \
    --ip-permissions "$perms" \
    --region "$REGION" 2>/dev/null || true
}

# Helper: add egress to CIDR (idempotent)
add_egress_cidr() {
  local sg_id="$1" port="$2" cidr="$3"
  local perms="[{\"IpProtocol\":\"tcp\",\"FromPort\":$port,\"ToPort\":$port,\"IpRanges\":[{\"CidrIp\":\"$cidr\"}]}]"
  aws ec2 authorize-security-group-egress \
    --group-id "$sg_id" \
    --ip-permissions "$perms" \
    --region "$REGION" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
echo "=== AWS Account: $ACCOUNT_ID | Region: $REGION ==="
echo ""

# Discover first two AVAILABLE AZs
AZ1=$(aws ec2 describe-availability-zones \
  --region "$REGION" \
  --filters "Name=state,Values=available" \
  --query "AvailabilityZones[0].ZoneName" --output text)
AZ2=$(aws ec2 describe-availability-zones \
  --region "$REGION" \
  --filters "Name=state,Values=available" \
  --query "AvailabilityZones[1].ZoneName" --output text)
echo "AZs: $AZ1, $AZ2"
echo ""

# ---------------------------------------------------------------------------
# 1. VPC
# ---------------------------------------------------------------------------

echo "--- VPC ---"

VPC_ID=$(find_by_name "vpc" "$VPC_NAME")
if [[ "$VPC_ID" != "NOT_FOUND" ]]; then
  echo "  SKIP $VPC_NAME (already exists: $VPC_ID)"
else
  VPC_ID=$(aws ec2 create-vpc \
    --cidr-block "$VPC_CIDR" \
    --query "Vpc.VpcId" --output text \
    --region "$REGION")
  tag_resource "$VPC_ID" "$VPC_NAME"
  echo "  CREATED $VPC_NAME ($VPC_ID)"
fi

# Enable DNS support and DNS hostnames (idempotent)
aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-support '{"Value":true}' --region "$REGION"
aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-hostnames '{"Value":true}' --region "$REGION"
echo ""

# ---------------------------------------------------------------------------
# 2. Subnets
# ---------------------------------------------------------------------------

echo "--- Subnets ---"

PUBLIC_1_ID=$(create_subnet "saas-public-1" "$PUBLIC_1_CIDR" "$AZ1")
PUBLIC_2_ID=$(create_subnet "saas-public-2" "$PUBLIC_2_CIDR" "$AZ2")
PRIV_APP_1_ID=$(create_subnet "saas-private-app-1" "$PRIVATE_APP_1_CIDR" "$AZ1")
PRIV_APP_2_ID=$(create_subnet "saas-private-app-2" "$PRIVATE_APP_2_CIDR" "$AZ2")
PRIV_DATA_1_ID=$(create_subnet "saas-private-data-1" "$PRIVATE_DATA_1_CIDR" "$AZ1")
PRIV_DATA_2_ID=$(create_subnet "saas-private-data-2" "$PRIVATE_DATA_2_CIDR" "$AZ2")

# Enforce map-public-ip-on-launch for public subnets (idempotent)
aws ec2 modify-subnet-attribute \
  --subnet-id "$PUBLIC_1_ID" --map-public-ip-on-launch --region "$REGION"
aws ec2 modify-subnet-attribute \
  --subnet-id "$PUBLIC_2_ID" --map-public-ip-on-launch --region "$REGION"
echo "  Enforced map-public-ip-on-launch on public subnets"

echo ""

# ---------------------------------------------------------------------------
# 3. Internet Gateway
# ---------------------------------------------------------------------------

echo "--- Internet Gateway ---"

IGW_ID=$(find_by_name "internet-gateway" "saas-igw")
if [[ "$IGW_ID" != "NOT_FOUND" ]]; then
  echo "  SKIP saas-igw (already exists: $IGW_ID)"
  # Verify it is attached to the target VPC
  ATTACHED_VPC=$(aws ec2 describe-internet-gateways \
    --internet-gateway-ids "$IGW_ID" \
    --query "InternetGateways[0].Attachments[?State=='available'].VpcId | [0]" \
    --output text --region "$REGION" 2>/dev/null || echo "None")
  if [[ "$ATTACHED_VPC" == "$VPC_ID" ]]; then
    echo "  Verified: attached to $VPC_ID"
  elif [[ "$ATTACHED_VPC" == "None" || -z "$ATTACHED_VPC" ]]; then
    echo "  WARNING: saas-igw exists but is detached — attaching to $VPC_ID"
    aws ec2 attach-internet-gateway \
      --internet-gateway-id "$IGW_ID" \
      --vpc-id "$VPC_ID" \
      --region "$REGION"
    echo "  Attached saas-igw to $VPC_ID"
  else
    echo "  ERROR: saas-igw is attached to a different VPC ($ATTACHED_VPC), not $VPC_ID" >&2
    exit 1
  fi
else
  IGW_ID=$(aws ec2 create-internet-gateway \
    --query "InternetGateway.InternetGatewayId" --output text \
    --region "$REGION")
  tag_resource "$IGW_ID" "saas-igw"
  aws ec2 attach-internet-gateway \
    --internet-gateway-id "$IGW_ID" \
    --vpc-id "$VPC_ID" \
    --region "$REGION"
  echo "  CREATED saas-igw ($IGW_ID) -> attached to $VPC_ID"
fi

echo ""

# ---------------------------------------------------------------------------
# 4. NAT Gateway (single, in public-1 for MVP)
# ---------------------------------------------------------------------------

echo "--- NAT Gateway ---"

NAT_ID=$(find_by_name "natgateway" "saas-nat")
if [[ "$NAT_ID" != "NOT_FOUND" ]]; then
  echo "  SKIP saas-nat (already exists: $NAT_ID)"
  # Retrieve EIP allocation ID for summary
  EIP_ALLOC=$(aws ec2 describe-nat-gateways \
    --nat-gateway-ids "$NAT_ID" \
    --query "NatGateways[0].NatGatewayAddresses[0].AllocationId" \
    --output text --region "$REGION" 2>/dev/null || echo "unknown")
else
  # Allocate Elastic IP
  EIP_ALLOC=$(aws ec2 allocate-address \
    --domain vpc \
    --query "AllocationId" --output text \
    --region "$REGION")
  tag_resource "$EIP_ALLOC" "saas-nat-eip"
  echo "  Allocated EIP: $EIP_ALLOC"

  NAT_ID=$(aws ec2 create-nat-gateway \
    --subnet-id "$PUBLIC_1_ID" \
    --allocation-id "$EIP_ALLOC" \
    --query "NatGateway.NatGatewayId" --output text \
    --region "$REGION")
  tag_resource "$NAT_ID" "saas-nat"
  echo "  CREATED saas-nat ($NAT_ID)"
fi

# Always wait for NAT to be available (covers both new and existing-but-pending)
echo "  Waiting for NAT Gateway to become available..."
aws ec2 wait nat-gateway-available \
  --nat-gateway-ids "$NAT_ID" \
  --region "$REGION"
echo "  NAT Gateway is available"

echo ""

# ---------------------------------------------------------------------------
# 5. Route Tables
# ---------------------------------------------------------------------------

echo "--- Route Tables ---"

# Create route tables (no associations yet)
RT_PUBLIC=$(create_route_table "$VPC_ID" "saas-rt-public")
RT_PRIV_1=$(create_route_table "$VPC_ID" "saas-rt-private-1")
RT_PRIV_2=$(create_route_table "$VPC_ID" "saas-rt-private-2")

# Enforce all subnet -> route table associations on every run
echo "  Enforcing subnet associations..."
ensure_rt_association "$RT_PUBLIC" "$PUBLIC_1_ID"
ensure_rt_association "$RT_PUBLIC" "$PUBLIC_2_ID"
ensure_rt_association "$RT_PRIV_1" "$PRIV_APP_1_ID"
ensure_rt_association "$RT_PRIV_1" "$PRIV_DATA_1_ID"
ensure_rt_association "$RT_PRIV_2" "$PRIV_APP_2_ID"
ensure_rt_association "$RT_PRIV_2" "$PRIV_DATA_2_ID"

# Public route: 0.0.0.0/0 -> IGW (create or replace to correct drift)
aws ec2 create-route \
  --route-table-id "$RT_PUBLIC" \
  --destination-cidr-block "0.0.0.0/0" \
  --gateway-id "$IGW_ID" \
  --region "$REGION" 2>/dev/null || \
aws ec2 replace-route \
  --route-table-id "$RT_PUBLIC" \
  --destination-cidr-block "0.0.0.0/0" \
  --gateway-id "$IGW_ID" \
  --region "$REGION"
echo "  Enforced 0.0.0.0/0 -> $IGW_ID on $RT_PUBLIC"

# Private routes: 0.0.0.0/0 -> NAT (create or replace; both AZs share single NAT for MVP)
aws ec2 create-route \
  --route-table-id "$RT_PRIV_1" \
  --destination-cidr-block "0.0.0.0/0" \
  --nat-gateway-id "$NAT_ID" \
  --region "$REGION" 2>/dev/null || \
aws ec2 replace-route \
  --route-table-id "$RT_PRIV_1" \
  --destination-cidr-block "0.0.0.0/0" \
  --nat-gateway-id "$NAT_ID" \
  --region "$REGION"
echo "  Enforced 0.0.0.0/0 -> $NAT_ID on $RT_PRIV_1"

aws ec2 create-route \
  --route-table-id "$RT_PRIV_2" \
  --destination-cidr-block "0.0.0.0/0" \
  --nat-gateway-id "$NAT_ID" \
  --region "$REGION" 2>/dev/null || \
aws ec2 replace-route \
  --route-table-id "$RT_PRIV_2" \
  --destination-cidr-block "0.0.0.0/0" \
  --nat-gateway-id "$NAT_ID" \
  --region "$REGION"
echo "  Enforced 0.0.0.0/0 -> $NAT_ID on $RT_PRIV_2"

echo ""

# ---------------------------------------------------------------------------
# 6. S3 Gateway VPC Endpoint
# ---------------------------------------------------------------------------

echo "--- S3 Gateway VPC Endpoint ---"

S3_ENDPOINT_ID=$(aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=$VPC_ID" \
            "Name=service-name,Values=com.amazonaws.$REGION.s3" \
            "Name=vpc-endpoint-type,Values=Gateway" \
  --query "VpcEndpoints[0].VpcEndpointId" --output text \
  --region "$REGION" 2>/dev/null || echo "None")

if [[ "$S3_ENDPOINT_ID" != "None" && -n "$S3_ENDPOINT_ID" ]]; then
  echo "  SKIP S3 Gateway endpoint (already exists: $S3_ENDPOINT_ID)"
else
  S3_ENDPOINT_ID=$(aws ec2 create-vpc-endpoint \
    --vpc-id "$VPC_ID" \
    --service-name "com.amazonaws.$REGION.s3" \
    --route-table-ids "$RT_PRIV_1" "$RT_PRIV_2" \
    --query "VpcEndpoint.VpcEndpointId" --output text \
    --region "$REGION")
  tag_resource "$S3_ENDPOINT_ID" "saas-s3-endpoint"
  echo "  CREATED S3 Gateway endpoint ($S3_ENDPOINT_ID)"
fi

# Enforce route table associations on every run (idempotent — adding already-associated RTs is a no-op)
aws ec2 modify-vpc-endpoint \
  --vpc-endpoint-id "$S3_ENDPOINT_ID" \
  --add-route-table-ids "$RT_PRIV_1" "$RT_PRIV_2" \
  --region "$REGION" --output text > /dev/null
echo "  Enforced S3 endpoint route tables: $RT_PRIV_1, $RT_PRIV_2"

echo ""

# ---------------------------------------------------------------------------
# 7. Security Groups
# ---------------------------------------------------------------------------

echo "--- Security Groups ---"

SG_ALB=$(create_sg "$VPC_ID" "saas-sg-alb" "ALB - public HTTP/HTTPS ingress")
SG_ECS=$(create_sg "$VPC_ID" "saas-sg-ecs" "ECS tasks - private app tier")
SG_RDS=$(create_sg "$VPC_ID" "saas-sg-rds" "RDS - private data tier")
SG_REDIS=$(create_sg "$VPC_ID" "saas-sg-redis" "Redis - private data tier")

echo ""
echo "--- Security Group Rules ---"

# ALB: inbound 80/443 from internet, outbound 8000 to ECS
add_ingress_cidr "$SG_ALB" 80 "0.0.0.0/0"
add_ingress_cidr "$SG_ALB" 443 "0.0.0.0/0"
add_egress "$SG_ALB" 8000 "$SG_ECS"
echo "  saas-sg-alb: ingress 80,443 from 0.0.0.0/0; egress 8000 -> ECS"

# ECS: inbound 8000 from ALB, outbound 5432->RDS, 6379->Redis, 443->internet
add_ingress "$SG_ECS" 8000 "$SG_ALB"
add_egress "$SG_ECS" 5432 "$SG_RDS"
add_egress "$SG_ECS" 6379 "$SG_REDIS"
add_egress_cidr "$SG_ECS" 443 "0.0.0.0/0"
echo "  saas-sg-ecs: ingress 8000 from ALB; egress 5432->RDS, 6379->Redis, 443->internet"

# RDS: inbound 5432 from ECS only
add_ingress "$SG_RDS" 5432 "$SG_ECS"
echo "  saas-sg-rds: ingress 5432 from ECS"

# Redis: inbound 6379 from ECS only
add_ingress "$SG_REDIS" 6379 "$SG_ECS"
echo "  saas-sg-redis: ingress 6379 from ECS"

echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo "=== VPC Provisioning Complete ==="
echo ""
echo "Resources created/verified:"
echo "  VPC:            $VPC_ID ($VPC_CIDR)"
echo "  AZs:            $AZ1, $AZ2"
echo "  Subnets:"
echo "    public-1:     $PUBLIC_1_ID ($PUBLIC_1_CIDR, $AZ1)"
echo "    public-2:     $PUBLIC_2_ID ($PUBLIC_2_CIDR, $AZ2)"
echo "    priv-app-1:   $PRIV_APP_1_ID ($PRIVATE_APP_1_CIDR, $AZ1)"
echo "    priv-app-2:   $PRIV_APP_2_ID ($PRIVATE_APP_2_CIDR, $AZ2)"
echo "    priv-data-1:  $PRIV_DATA_1_ID ($PRIVATE_DATA_1_CIDR, $AZ1)"
echo "    priv-data-2:  $PRIV_DATA_2_ID ($PRIVATE_DATA_2_CIDR, $AZ2)"
echo "  IGW:            $IGW_ID"
echo "  NAT Gateway:    $NAT_ID"
echo "  NAT EIP:        $EIP_ALLOC"
echo "  Route tables:"
echo "    public:       $RT_PUBLIC"
echo "    private-1:    $RT_PRIV_1 ($AZ1)"
echo "    private-2:    $RT_PRIV_2 ($AZ2)"
echo "  S3 Endpoint:    $S3_ENDPOINT_ID"
echo "  Security groups:"
echo "    ALB:          $SG_ALB"
echo "    ECS:          $SG_ECS"
echo "    RDS:          $SG_RDS"
echo "    Redis:        $SG_REDIS"
echo ""
echo "Next steps:"
echo "  1. Provision RDS PostgreSQL in private-data subnets (task 8.5)"
echo "  2. Provision ElastiCache Redis in private-data subnets (task 8.6)"
echo "  3. Create S3 bucket (task 8.7)"
echo "  4. Deploy ECS services (task 8.8b P3)"
