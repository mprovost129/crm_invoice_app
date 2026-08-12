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
| Redis | Partial | Local service and production cache exist; public-link throttling uses cache; no dedicated job broker |
| Docker image and local Compose | Implemented | Multi-stage non-root Python 3.13 image; health-checked web/PostgreSQL 16/Redis 7 |
| Gunicorn production entry | Implemented | Docker command and Procfile web process |
| Static files | Implemented | WhiteNoise manifest storage in production |
| Persistent media/object storage | Partial | Django backend is configurable and estimate PDFs use it; no private cloud provider/package selected |
| Liveness/readiness endpoints | Implemented | Process liveness plus database-backed readiness and compatibility `/health/` route |
| Request correlation ID | Implemented | Request/response `X-Request-ID` middleware |
| Logging | Partial | Console/file logging exists; not structured/centralized/redacted |
| Ruff/pre-commit | Implemented | Configuration exists |
| CI pipeline | Implemented | GitHub Actions runs Ruff, formatting, migration, PostgreSQL tests, and deploy checks |
| Application migrations | Implemented | Phase 0/1 User, Workspace, Business, settings, and sequence migrations applied |
| Background worker/outbox | Partial | Durable outbox, after-commit processing, retry command, and delivery state exist; no independently deployed worker/scheduler yet |
| Error/uptime monitoring | Not started | Provider not selected |
| Backup/restore automation | Not started | No repository procedure or evidence |

## Identity, Account, and Tenancy

| Feature | Status | Current evidence / remaining work |
| --- | --- | --- |
| Email-first custom user | Implemented | UUID custom model/manager, password hashing, admin forms |
| Account-owner profile | Implemented | UUID `AccountProfile`, explicitly not a CRM Contact or tenant Business |
| Login/logout | Implemented | Namespaced auth routes, case-insensitive email login, and routing gates |
| Password reset | Implemented | Namespaced routes/templates and expiring, password-invalidated tokens; delivery depends on email config |
| Registration | Implemented | Validated public form and atomic User/Workspace/owner Membership service |
| Email verification | Implemented | One-time token, resend path, verified timestamp, and onboarding gate |
| Google login | Deferred | Recommended after basic auth, not required for core V1 |
| Workspace and membership | Implemented | UUID models, active membership selectors, uniqueness constraints, staff admin |
| Business and business settings | Implemented | UUID models, profile/default settings, validation, protected relationships |
| One-owner/one-business V1 policy | Implemented | Partial database uniqueness plus owner-only onboarding/settings services |
| Tenant request context and scoping | Implemented | Membership-derived middleware context, scoped querysets/selectors, isolation tests |
| Business onboarding | Implemented | Verified-owner flow atomically creates Business, settings, and two sequences |
| Customer-facing app shell/dashboard | Implemented | Verified/onboarded empty dashboard and owner business-settings screen |
| Customer-centric staff admin | Implemented | Search, metrics, profile inline, related-record links |

## CRM and Catalog

| Feature | Status |
| --- | --- |
| Lead/client `Contact` model and lifecycle | Implemented |
| Client list, filters, create/edit/archive | Implemented |
| Client profile and financial summary | Partial - profile and explicit zero state exist; document/payment totals depend on later domains |
| Notes and automatic activity | Implemented for Contact and catalog lifecycle events |
| Tenant-safe client search | Implemented |
| Product/service catalog | Implemented |
| Catalog search/filter/archive | Implemented |
| Catalog-to-line snapshot behavior | Implemented |
| Custom document line items | Implemented |
| CRM/catalog entitlement hooks | Implemented - backend hooks exist; Plan/Subscription rules begin in Phase 6 |

`AccountProfile` represents supplementary application-owner metadata, not a client/contact CRM implementation.

## Estimates

| Feature | Status |
| --- | --- |
| Transaction-safe document numbering | Implemented |
| Estimate and estimate-line models | Implemented |
| Decimal calculation and currency policy | Implemented |
| Draft builder/editing/preview | Implemented |
| Discounts, tax, and deposit requirements | Implemented |
| Issue and immutable snapshot | Implemented |
| PDF/print/email delivery | Implemented - production providers remain deployment configuration |
| Secure public estimate page | Implemented |
| View tracking | Implemented |
| Optional online accept/decline | Implemented |
| Manual acceptance and evidence | Implemented |
| Derived expiration | Implemented |

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
| Email delivery tracking | Implemented for queued/sent/failed estimate delivery |
| Secure revocable public links | Implemented for estimate view/respond purposes |
| Private file assets and document snapshots | Implemented for issued estimates; production storage provider remains open |
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

Eighty-one PostgreSQL-backed tests pass. In addition to the Phase 0-2 suite, they cover
deterministic financial calculations, numbering rollback, issued-document immutability,
acceptance evidence, derived expiration, public-link security/view tracking, PDF rendering,
email outbox delivery, owner/public screens, and cross-tenant denial. Invoice/payment,
external production-provider, export, and full V1 end-to-end coverage remain future phases.

See [TEST_PLAN.md](TEST_PLAN.md) for required coverage and [ROADMAP.md](ROADMAP.md) for delivery order.
