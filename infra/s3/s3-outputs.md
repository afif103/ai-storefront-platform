# S3 Outputs

Resource IDs produced by `provision-s3.sh`.

## Bucket

| Resource | Value | Notes |
|----------|-------|-------|
| Bucket name | `{{BUCKET_NAME}}` | |
| Region | `{{REGION}}` | |
| ARN | `arn:aws:s3:::{{BUCKET_NAME}}` | |

## Settings

| Setting | Value |
|---------|-------|
| Block Public Access | All 4 ON |
| Versioning | Enabled |
| Encryption | SSE-S3 (AES256) |
| Lifecycle | Transition to STANDARD_IA after 90 days |

## Cross-references

| Downstream Task | Needs |
|-----------------|-------|
| Task-role S3 policy | Bucket ARN for `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` |
| Backend task def | `S3_BUCKET` env var |
| CORS configuration | Allowed origins (after frontend domain is known) |
