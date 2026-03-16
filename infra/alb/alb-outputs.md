# ALB Outputs

Resource IDs produced during 8.9 P1. HTTP-only state — HTTPS, CloudFront, and WAF are pending.

## Load Balancer

| Resource | Value |
|----------|-------|
| ALB name | `saas-alb` |
| ALB ARN | `arn:aws:elasticloadbalancing:ap-southeast-1:701893741240:loadbalancer/app/saas-alb/f6eea380f52e2210` |
| DNS name | `saas-alb-1087157138.ap-southeast-1.elb.amazonaws.com` |
| Scheme | internet-facing |
| Region | `ap-southeast-1` |

## Target Group

| Resource | Value |
|----------|-------|
| Name | `saas-backend-tg` |
| ARN | `arn:aws:elasticloadbalancing:ap-southeast-1:701893741240:targetgroup/saas-backend-tg/857fc97297a6a88a` |
| Target type | ip |
| Protocol / Port | HTTP / 8000 |
| Health check | `GET /api/v1/health`, interval 30s, healthy 2, unhealthy 3 |

## Listener

| Resource | Value |
|----------|-------|
| Listener ARN | `arn:aws:elasticloadbalancing:ap-southeast-1:701893741240:listener/app/saas-alb/f6eea380f52e2210/611112626af0706c` |
| Protocol / Port | HTTP / 80 |
| Action | Forward to `saas-backend-tg` |

## Security Group Rules (added in P1)

| Rule ID | SG | Direction | Port | Source/Dest |
|---------|----|-----------|------|-------------|
| `sgr-093eccd1660eb0ea3` | `sg-05384b882188ed6ba` (ALB) | Inbound | 80 | 0.0.0.0/0 |
| `sgr-0ad427e2fd92bf3f2` | `sg-05384b882188ed6ba` (ALB) | Outbound | 8000 | ECS SG `sg-00a63148f50fe4cbd` |
| `sgr-0001b17b47703d4cb` | `sg-00a63148f50fe4cbd` (ECS) | Inbound | 8000 | ALB SG `sg-05384b882188ed6ba` |

## Cross-references

| Downstream Task | Needs |
|-----------------|-------|
| 8.9 P2 (HTTPS) | ALB ARN for HTTPS :443 listener + ACM cert |
| 8.9 P3 (CloudFront) | ALB DNS as origin |
| 8.9 P4 (CORS) | ALB DNS or final domain for `ALLOWED_ORIGINS` |
