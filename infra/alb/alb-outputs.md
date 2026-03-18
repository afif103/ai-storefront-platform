# ALB Outputs

Resource IDs produced during 8.9 P1–P3a. HTTPS live for `api.ramitestapp.top` and `origin-api.ramitestapp.top`. CloudFront and WAF are pending.

## Load Balancer

| Resource | Value |
|----------|-------|
| ALB name | `saas-alb` |
| ALB ARN | `arn:aws:elasticloadbalancing:ap-southeast-1:701893741240:loadbalancer/app/saas-alb/f6eea380f52e2210` |
| DNS name | `saas-alb-1087157138.ap-southeast-1.elb.amazonaws.com` |
| API domain | `api.ramitestapp.top` (CNAME → ALB DNS) |
| Origin hostname | `origin-api.ramitestapp.top` (CNAME → ALB DNS) — temporary public origin for CloudFront; direct access deferred to hardening packet |
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

## Listeners

| Listener | ARN | Protocol / Port | Action |
|----------|-----|-----------------|--------|
| HTTPS | `arn:aws:elasticloadbalancing:ap-southeast-1:701893741240:listener/app/saas-alb/f6eea380f52e2210/5a8f5cc1444c1536` | HTTPS / 443 | Forward to `saas-backend-tg` |
| HTTP | `arn:aws:elasticloadbalancing:ap-southeast-1:701893741240:listener/app/saas-alb/f6eea380f52e2210/611112626af0706c` | HTTP / 80 | Redirect 301 → HTTPS :443 |

## ACM Certificates

HTTPS listener has 2 certs via SNI. TLS policy: `ELBSecurityPolicy-TLS13-1-2-2021-06`.

| Cert | ARN | Region | Domain | Role |
|------|-----|--------|--------|------|
| ALB default | `arn:aws:acm:ap-southeast-1:701893741240:certificate/bdc0cd86-a705-44ba-bdf4-5020cec91932` | ap-southeast-1 | `api.ramitestapp.top` | Direct ALB access |
| ALB additional (SNI) | `arn:aws:acm:ap-southeast-1:701893741240:certificate/4081ef00-b6de-4eab-94ce-217689bb0fc2` | ap-southeast-1 | `origin-api.ramitestapp.top` | CloudFront → ALB origin |
| CloudFront viewer | `arn:aws:acm:us-east-1:701893741240:certificate/f2a7d587-2746-4bba-adfa-e4929cdfda52` | us-east-1 | `api.ramitestapp.top` | CloudFront viewer cert (not yet attached) |

## Security Group Rules

| Rule ID | SG | Direction | Port | Source/Dest | Added |
|---------|----|-----------|------|-------------|-------|
| `sgr-093eccd1660eb0ea3` | `sg-05384b882188ed6ba` (ALB) | Inbound | 80 | 0.0.0.0/0 | P1 |
| `sgr-035dcd0eb34d8db8e` | `sg-05384b882188ed6ba` (ALB) | Inbound | 443 | 0.0.0.0/0 | P2 |
| `sgr-0ad427e2fd92bf3f2` | `sg-05384b882188ed6ba` (ALB) | Outbound | 8000 | ECS SG `sg-00a63148f50fe4cbd` | P1 |
| `sgr-0001b17b47703d4cb` | `sg-00a63148f50fe4cbd` (ECS) | Inbound | 8000 | ALB SG `sg-05384b882188ed6ba` | P1 |

## Cross-references

| Downstream Task | Needs |
|-----------------|-------|
| 8.9 P2 (HTTPS) | **DONE** — HTTPS listener + ACM cert live |
| 8.9 P3a (origin prep) | **DONE** — origin hostname, regional cert, viewer cert |
| 8.9 P3b (WAF) | **DONE** — `saas-api-waf` WebACL in us-east-1, ARN `arn:aws:wafv2:us-east-1:701893741240:global/webacl/saas-api-waf/683553aa-bcaf-436b-951c-3ce9f4ff737f`, 4 rules (CommonRuleSet, SQLiRuleSet, KnownBadInputsRuleSet, rate-limit 2000/5min/IP), 1102 WCU, unattached |
| 8.9 P3c (CloudFront) | Distribution with origin `origin-api.ramitestapp.top`, attach WAF WebACL |
| 8.9 P3d (DNS cutover) | `api` CNAME → CloudFront domain |
| 8.9 P3e (ALB hardening) | Restrict ALB origin access (CloudFront prefix list and/or custom origin header) |
| 8.9 P4 (CORS) | Frontend origin(s) such as `app.ramitestapp.top` / `*.app.ramitestapp.top` for `ALLOWED_ORIGINS` |
