# Feature Inventory

Last reviewed: 2026-08-12

## Status Legend

- **Implemented:** production code exists for the stated behavior.
- **Partial:** useful foundation exists, but the intended feature/acceptance boundary is incomplete.
- **Not started:** no meaningful product implementation exists.
- **Deferred:** intentionally outside initial V1.
- **Decision needed:** implementation should wait for an explicit choice.

This inventory distinguishes generic starter capabilities from actual CRM/invoicing functionality.

## Foundation and Operations

| Feature | Status | Current evidence / remaining work |
| --- | --- | --- |
| Django project and environment settings | Implemented | Base/dev/prod settings exist and are environment-driven |
| PostgreSQL application database | Implemented | Required by settings and local Compose |
| Redis | Partial | Local service and production cache exist; no worker/outbox use |
| Docker image and local Compose | Implemented | Multi-stage non-root Python 3.13 image; health-checked web/PostgreSQL 16/Redis 7 |
| Gunicorn production entry | Implemented | Docker command and Procfile web process |
| Static files | Implemented | WhiteNoise manifest storage in production |
| Persistent media/object storage | Partial | Backend is configurable; no cloud backend/package selected |
| Liveness/readiness endpoints | Implemented | Process liveness plus database-backed readiness and compatibility `/health/` route |
| Request correlation ID | Implemented | Request/response `X-Request-ID` middleware |
| Logging | Partial | Console/file logging exists; not structured/centralized/redacted |
| Ruff/pre-commit | Implemented | Configuration exists |
| CI pipeline | Implemented | GitHub Actions runs Ruff, formatting, migration, PostgreSQL tests, and deploy checks |
| Application migrations | Implemented | Initial UUID User/AccountProfile migration generated and applied |
| Background worker/outbox | Not started | Redis alone does not implement asynchronous work |
| Error/uptime monitoring | Not started | Provider not selected |
| Backup/restore automation | Not started | No repository procedure or evidence |

## Identity, Account, and Tenancy

| Feature | Status | Current evidence / remaining work |
| --- | --- | --- |
| Email-first custom user | Implemented | UUID custom model/manager, password hashing, admin forms |
| Account-owner profile | Implemented | UUID `AccountProfile`, explicitly not a CRM Contact or tenant Business |
| Login/logout | Implemented | Django auth URLs and login template |
| Password reset | Implemented | Django auth URLs and reset templates; delivery depends on email config |
| Registration | Not started | No public registration view/form/service |
| Email verification | Not started | No field/workflow/provider integration |
| Google login | Deferred | Recommended after basic auth, not required for core V1 |
| Workspace and membership | Not started | Models/context/policies absent |
| Business and business settings | Not started | Models/onboarding/settings absent |
| One-owner/one-business V1 policy | Not started | Requires tenancy models/services |
| Tenant request context and scoping | Not started | Critical blocker for all domain apps |
| Business onboarding | Not started | No onboarding flow |
| Customer-facing app shell/dashboard | Partial | Generic base/nav/home only |
| Customer-centric staff admin | Implemented | Search, metrics, profile inline, related-record links |

## CRM and Catalog

| Feature | Status |
| --- | --- |
| Lead/client `Contact` model and lifecycle | Not started |
| Client list, filters, create/edit/archive | Not started |
| Client profile and financial summary | Not started |
| Notes and automatic activity | Not started |
| Tenant-safe client search | Not started |
| Product/service catalog | Not started |
| Catalog search/filter/archive | Not started |
| Catalog-to-line snapshot behavior | Not started |
| Custom document line items | Not started |

`AccountProfile` represents supplementary application-owner metadata, not a client/contact CRM implementation.

## Estimates

| Feature | Status |
| --- | --- |
| Transaction-safe document numbering | Not started |
| Estimate and estimate-line models | Not started |
| Decimal calculation and currency policy | Not started |
| Draft builder/editing/preview | Not started |
| Discounts, tax, and deposit requirements | Not started |
| Issue and immutable snapshot | Not started |
| PDF/print/email delivery | Not started |
| Secure public estimate page | Not started |
| View tracking | Not started |
| Optional online accept/decline | Not started |
| Manual acceptance and evidence | Not started |
| Derived expiration | Not started |

## Invoices and Payments

| Feature | Status |
| --- | --- |
| Atomic idempotent estimate conversion | Not started |
| Invoice and invoice-line models | Not started |
| Direct invoice builder | Not started |
| Invoice snapshots/PDF/public view/email | Not started |
| Manual payment ledger | Not started |
| Deposits and partial payments | Not started |
| Cached paid/balance totals | Not started |
| Derived Partial/Paid/Overdue states | Not started |
| Payment reversals | Not started |
| Void invoice workflow | Not started |
| Manual reminder and receipt | Not started |
| Reconciliation command | Not started |

## Dashboard, Communications, and Trust

| Feature | Status |
| --- | --- |
| Paid/outstanding/overdue/open-estimate cards | Not started |
| Needs Attention and Recent Activity | Not started |
| Internal notifications | Not started |
| Email delivery tracking | Not started |
| Secure revocable public links | Not started |
| Private file assets and document snapshots | Not started |
| Minimal reports | Not started |
| Client/invoice/payment CSV export | Not started |
| Terms and privacy pages | Not started |
| Data export/account closure procedure | Not started |

## Commercial Integrations

| Feature | Status |
| --- | --- |
| Configurable plans and subscriptions | Not started |
| Free/Starter entitlement policies | Not started |
| Usage counters/reconciliation | Not started |
| Stripe Billing | Not started |
| Stripe Connect onboarding | Not started |
| Online invoice payment | Not started |
| Verified webhook inbox | Not started |
| Idempotent webhook processor | Not started |
| Provider reconciliation | Not started |

## User Experience

| Feature | Status | Notes |
| --- | --- | --- |
| Responsive base templates | Partial | Bootstrap shell exists; product screens do not |
| Accessible messages/error pages | Partial | Shared templates exist; full accessibility pass pending |
| HTMX foundation | Implemented | Self-hosted verified HTMX 2.0.10 with Django CSRF header integration |
| Product branding/design system | Decision needed | Current UI is generic starter styling |
| Search and pagination conventions | Not started | Apply per growing domain list |
| Mobile application | Deferred | Responsive web and stable backend first |

## Explicitly Deferred Product Features

- Recurring invoices and automatic reminder schedules.
- Multiple active businesses and business add-ons.
- Multiple users, roles, and permissions.
- Multiple contacts per customer.
- Full client portal accounts.
- Project management/task systems.
- Public API access, native mobile app, and advanced integrations.
- General accounting, expenses, bank feeds, tax filing, payroll, inventory, and purchasing.
- Advanced automation, custom fields, and complex reports.

## Current Test Evidence

Twenty-one PostgreSQL-backed foundation tests pass. They cover the custom UUID user/account profile, email normalization/password hashing, superuser flags, admin search, liveness/readiness including database failure, request IDs, self-hosted HTMX, and environment/production-secret validation. No tenant, CRM, document, financial, provider, or V1 end-to-end test exists yet.

See [TEST_PLAN.md](TEST_PLAN.md) for required coverage and [ROADMAP.md](ROADMAP.md) for delivery order.
