# Product Brief

## What We're Building
A multi-tenant SaaS platform for Kuwait SMBs and charity/masjid projects that unifies storefront, AI assistant, and structured data capture into one product.

## Key Capabilities

### 1. Tenant Onboarding
- Self-serve signup → create organisation → invite team members.
- Tenant isolation via RLS from moment of creation.
- Subscription tier selection (Free / Starter / Pro) with KWD billing (`NUMERIC(12,3)`).

### 2. Branded Storefront
- Tenant-configurable storefront (logo, colours, categories, product/service listings).
- Public URL per tenant: `https://{slug}.yourdomain.com` (custom domain support planned for later).
- UTM parameter capture on all inbound links for attribution.

### 3. AI Assistant
- Conversational AI that answers product questions, guides users through orders/donations.
- Runs through AI gateway with per-tenant quota checks (Redis) before every call.
- All token usage logged for billing and transparency.

### 4. Structured Capture
- **Orders**: product, quantity, customer info, payment status.
- **Donations**: donor, amount (KWD), campaign, receipt flag.
- **Pledges**: pledgor, amount, fulfilment date, status tracking.
- All records tenant-scoped, searchable, exportable.

### 5. Attribution & KPIs
- UTM params (source, medium, campaign, content, term) stored per visit/conversion.
- Dashboard showing: visits → conversions by channel, top campaigns, AI cost per tenant.

## User Roles
| Role | Permissions |
|------|------------|
| Super Admin | Platform-wide management (not tenant-scoped) |
| Tenant Owner | Full control of their tenant: billing, team, settings |
| Tenant Admin | Manage storefront, view all orders/donations, configure AI |
| Tenant Member | View orders/donations assigned to them, use AI assistant |

## Out of Scope (MVP)
- Payment gateway integration (MVP supports pledge + manual payment instructions + optional payment link; full KNET/cards via PSP in v1.1+).
- Native mobile app.
- Multi-language AI (English + Arabic planned for v1.1).
- Webhooks / third-party integrations.
