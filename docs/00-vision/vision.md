# Vision

## Problem
Kuwait SMBs selling through WhatsApp and Instagram have no structured way to capture orders, track donations/pledges, or attribute conversions. They juggle spreadsheets, lose messages, and can't measure what's working.

## Solution
A multi-tenant platform giving each business a branded storefront with an AI assistant that captures orders, donations, and pledges in structured form — with UTM-based attribution so owners see exactly which campaigns convert.

## Target Users
- Kuwait SMBs selling products/services via WhatsApp/Instagram.
- Masjid and charity projects collecting donations and pledges.
- Teams of 2–30 users per tenant.

## Core Value Propositions
1. **Branded storefront** — each tenant gets a customisable storefront, no code required.
2. **AI assistant** — conversational AI handles enquiries, captures orders/donations/pledges into structured records.
3. **Structured capture** — orders, donations, and pledges stored with full audit trail, not lost in chat threads.
4. **KPI attribution** — UTM tracking on every link so tenants see which channels and campaigns drive conversions.
5. **Real isolation** — tenant data separated at the DB level via PostgreSQL RLS. Zero cross-tenant leakage.
6. **Usage-based AI** — metered AI with per-tenant quotas. Pay for what you use.

## Success Metrics (Year 1)
| Metric | Target |
|--------|--------|
| Tenants onboarded | 50+ |
| MRR | KWD 3,000 |
| Storefront → order conversion rate | ≥ 5% |
| AI budget compliance (tenants within quota) | ≥ 95% |
| P95 API latency | < 300 ms |
| Uptime | 99.5% |
| Tenant data leak incidents | 0 |
