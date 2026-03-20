#!/usr/bin/env bash
# provision-s3.sh — Create S3 bucket for tenant media storage.
#
# Idempotent: skips bucket creation if it already exists.
# Requires: aws CLI configured with credentials for the target account.
#
# Creates:
#   - S3 bucket with Block Public Access, versioning, SSE-S3 encryption,
#     lifecycle rule (transition to IA after 90 days), and CORS for
#     presigned PUT uploads from the Vercel frontend.
#
# Does NOT create or update: task-role S3 policy, ECS task definitions,
# or /prod/* secrets.

set -euo pipefail

# Prevent MSYS/Git Bash from converting paths to Windows paths
export MSYS_NO_PATHCONV=1

REGION="${REGION:-ap-southeast-1}"
ACCOUNT_ID="${ACCOUNT_ID:-701893741240}"
BUCKET_NAME="${BUCKET_NAME:-saas-media-prod-${ACCOUNT_ID}}"

echo "=== S3 Bucket Provisioning ==="
echo "  Bucket:  $BUCKET_NAME"
echo "  Region:  $REGION"
echo ""

# ─── 1. Create bucket (idempotent) ───────────────────────────────────────────

echo "--- Bucket ---"
if aws s3api head-bucket --bucket "$BUCKET_NAME" --region "$REGION" 2>/dev/null; then
  echo "  SKIP bucket (already exists: $BUCKET_NAME)"
else
  aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$REGION" \
    --create-bucket-configuration "LocationConstraint=$REGION" \
    --output text > /dev/null
  echo "  CREATED bucket: $BUCKET_NAME"
fi

# ─── 2. Block Public Access (all 4 settings ON) ─────────────────────────────

echo "--- Block Public Access ---"
aws s3api put-public-access-block \
  --bucket "$BUCKET_NAME" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  --region "$REGION"
echo "  APPLIED Block Public Access (all 4 settings ON)"

# ─── 3. Enable Versioning ────────────────────────────────────────────────────

echo "--- Versioning ---"
aws s3api put-bucket-versioning \
  --bucket "$BUCKET_NAME" \
  --versioning-configuration "Status=Enabled" \
  --region "$REGION"
echo "  APPLIED versioning: Enabled"

# ─── 4. Enable SSE-S3 Default Encryption ─────────────────────────────────────

echo "--- Encryption ---"
aws s3api put-bucket-encryption \
  --bucket "$BUCKET_NAME" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }' \
  --region "$REGION"
echo "  APPLIED encryption: SSE-S3 (AES256)"

# ─── 5. Lifecycle Rule: Transition to IA after 90 days ───────────────────────

echo "--- Lifecycle ---"
aws s3api put-bucket-lifecycle-configuration \
  --bucket "$BUCKET_NAME" \
  --lifecycle-configuration '{
    "Rules": [{
      "ID": "transition-to-ia-90d",
      "Status": "Enabled",
      "Filter": {},
      "Transitions": [{
        "Days": 90,
        "StorageClass": "STANDARD_IA"
      }]
    }]
  }' \
  --region "$REGION"
echo "  APPLIED lifecycle: transition to STANDARD_IA after 90 days"

# ─── 6. CORS for presigned PUT uploads from Vercel frontend ────────────────

FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-https://ai-storefront-platform.vercel.app}"

echo "--- CORS ---"
aws s3api put-bucket-cors \
  --bucket "$BUCKET_NAME" \
  --cors-configuration '{
    "CORSRules": [{
      "AllowedOrigins": ["'"$FRONTEND_ORIGIN"'"],
      "AllowedMethods": ["PUT"],
      "AllowedHeaders": ["Content-Type"],
      "MaxAgeSeconds": 3600
    }]
  }' \
  --region "$REGION"
echo "  APPLIED CORS: PUT from $FRONTEND_ORIGIN"

# ─── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo "=== S3 Provisioning Complete ==="
echo "  Bucket:             $BUCKET_NAME"
echo "  Region:             $REGION"
echo "  Block Public Access: all ON"
echo "  Versioning:         Enabled"
echo "  Encryption:         SSE-S3 (AES256)"
echo "  Lifecycle:          STANDARD_IA after 90 days"
echo "  CORS:               PUT from $FRONTEND_ORIGIN"
echo ""
echo "Next steps:"
echo "  1. Verify settings: run P2 verification commands"
echo "  2. Add S3 inline policy to saas-backend-task-role (later packet)"
echo "  3. Add S3_BUCKET env var to backend task definition (later packet)"
