# Vision & Source Documents

## About This Folder

This folder contains the original vision/planning PDFs alongside the markdown docs that were derived from them. **The markdown docs are the implementation source of truth.** The PDFs are retained as reference material for context and stakeholder alignment.

If a PDF and a markdown doc contradict each other, the markdown doc wins.

## PDF → Markdown Mapping

| PDF (reference) | Markdown (source of truth) |
|-----------------|---------------------------|
| `mvp-build-plan-charity-masjid-kuwait.pdf` | `docs/05-backlog/milestones.md` — milestone map, dependencies, timeline |
| | `docs/05-backlog/backlog-v1.md` — 83 tasks across M1–M9 with owners and DoD |
| `product-brief-ai-storefront-kuwait-v2.pdf` | `docs/00-vision/product-brief.md` — capabilities, user roles, out-of-scope |
| | `docs/01-architecture/ai-architecture.md` — AI gateway, quota flow, provider abstraction |
| | `docs/04-api/api-overview.md` — API conventions, auth model, error format |
| | `docs/04-api/endpoints.md` — full endpoint reference |
| `tech-architecture-security-plan-kuwait-multitenant.pdf` | `docs/01-architecture/security.md` — auth, secrets, S3, rate limiting, logging, network |
| | `docs/02-decisions/adr-0003-auth.md` — Cognito + token transport + refresh hardening |
| | `docs/01-architecture/aws-deployment.md` — infra diagram, ECS, RDS, Redis, CI/CD, cost |

## Markdown Docs in This Folder

| File | Purpose |
|------|---------|
| `vision.md` | Problem, solution, target users, success metrics |
| `product-brief.md` | Capabilities, user roles, out-of-scope |
| `mvp-scope.md` | Milestones M1–M9, in/out of scope |
