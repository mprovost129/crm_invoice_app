# Architecture

Last reviewed: 2026-08-12

## Status and Architecture Direction

The approved target is a modular Django monolith backed by PostgreSQL. Phases 0 through 2
implement the shared foundation, identity, workspace, business onboarding, trusted
tenant boundary, CRM, catalog, and append-only activity history. Financial components remain target architecture. See
[FEATURES.md](FEATURES.md) for status.

The supported baseline is Python 3.13 and Django 5.2 LTS, currently pinned to Django 5.2.16. The LTS choice is recorded in [DECISIONS.md](DECISIONS.md).

## System Context

```text
Owner browser ----> Django web application ----> PostgreSQL
                         |       |
                         |       +-------------> Redis / worker (asynchronous work)
                         |
Customer secure link --->|---------------------> Object storage / email / payment providers

Future mobile app ------> Versioned REST API --> Same application services and database
```

The backend is authoritative. Web views, future API endpoints, background jobs, staff operations, and future mobile clients must call the same application services and calculators.

## Architectural Style

- Modular monolith with domain-focused Django applications.
- Server-rendered Django templates for V1, with progressive enhancement and limited JavaScript.
- PostgreSQL as the only supported application database.
- Explicit services for important writes and state transitions.
- Selectors/query services for tenant-scoped and optimized reads.
- Policies for membership, permissions, and plan entitlements.
- Provider adapters for email, storage, billing, and payment integrations.
- Transactional outbox for durable after-commit side effects.
- REST API introduced under `/api/v1/` only when a real client requires it.

Microservices, a separate analytics database, and duplicated browser/mobile business logic are intentionally rejected for V1.

## Current Repository Structure

```text
config/                 Django settings, URL routing, ASGI, and WSGI
  settings/base.py      Shared environment-driven settings
  settings/dev.py       Debug toolbar and development overrides
  settings/prod.py      HTTPS, Redis cache, WhiteNoise, and production overrides
core/                   Shared models, document sequences, health, middleware
users/                  Identity, registration, verification, password flows, admin
workspaces/             Workspace, membership, business, settings, tenant context
crm/                    Contacts, notes, lifecycle services, selectors, screens
catalog/                Reusable products/services, lifecycle services, screens
activity/               Append-only tenant activity events
templates/              Base, auth, onboarding, app, error, admin, shared templates
static/                 Shared CSS, JavaScript, images, and admin styling
docs/                   Product and engineering documentation
Dockerfile              Python 3.13/Gunicorn production image
docker-compose.yml      Local web, PostgreSQL 16, and Redis 7 services
Procfile                Web and release/migration commands
.github/workflows/      PostgreSQL-backed automated quality gate
README.md               Canonical Docker setup and verification workflow
```

The Phase 1 and 2 `users`, `workspaces`, `core`, `crm`, `catalog`, and `activity`
migrations are generated and apply cleanly. The next domain boundary is the estimate
aggregate.

## Target Domain Applications

| App | Responsibility |
| --- | --- |
| `core` | Shared models, money/currency utilities, document sequences, outbox, exceptions |
| `users` or `accounts` | Custom user, authentication, verification, password flows |
| `workspaces` | Workspace, membership, business, settings, tenant context |
| `crm` | Contacts, notes, client profile selectors |
| `catalog` | Reusable products and services |
| `estimates` | Estimate aggregate, calculations, acceptance, conversion entry point |
| `invoices` | Invoice aggregate, effective status, balance behavior |
| `payments` | Payment/reversal ledger and connected account state |
| `activity` | Append-only business activity |
| `communications` | Public links, file assets, snapshots, email, notifications |
| `billing` | Plans, subscriptions, usage/entitlement rules |
| `integrations` | Webhook inboxes and external-provider adapters |
| `dashboard` | Cross-domain read models and reports |
| `api` | Future versioned REST composition |

The source architecture used `accounts`; the repository standardizes on the existing `users` app name.

## Internal App Convention

Domain apps should separate concerns as follows:

- `models.py` or `models/`: persistence and local invariants.
- `services.py`: state-changing use cases and transaction boundaries.
- `selectors.py`: scoped, optimized reads.
- `policies.py`: membership, authorization, and entitlement checks.
- `validators.py`: reusable validation.
- `tasks.py`: asynchronous entry points.
- `admin.py`: safe staff operations.
- `api/`: serializers, views, and routing when API work begins.
- `tests/`: model, service, selector, web/API, tenant, and integration coverage.

Views and serializers validate transport concerns, resolve trusted context, and call services. They must not contain financial calculations, tenant assignment, or multi-model workflow orchestration.

## Model Conventions

- Use a custom user model from the first migration.
- Use UUID primary keys for project-owned persisted entities and externally visible identifiers. The initial `User` and `AccountProfile` migration follows this convention.
- Use timezone-aware timestamps.
- Give every business-owned domain row a direct, required `business` foreign key.
- Use human-readable estimate/invoice numbers as separate tenant-unique fields.
- Use explicit foreign keys for core activity objects instead of generic relations.
- Use `PROTECT` for financial parents, `CASCADE` only for safely deletable draft aggregates, and `SET_NULL` for optional source references.
- Prefer `archived_at`, `voided_at`, and reversal records to destructive deletion.
- In reusable model relationships, reference `settings.AUTH_USER_MODEL`; use `get_user_model()` at runtime.

## Tenant and Authorization Boundary

Request processing resolves an authenticated user, active membership/workspace, and active business. A submitted business ID is never trusted by itself.

Every domain lookup begins from a business-scoped queryset. Creation services assign `business` from trusted request context and ignore or reject client-supplied tenant keys. Composite uniqueness, parent/child business validation, service checks, and tests provide defense in depth.

Django admin is a staff operations tool, not the customer interface. Sensitive financial actions must be explicit, tenant-aware, auditable, and protected from bulk destructive edits.

## Financial and Document Architecture

- Use `Decimal`, never `float`, for quantities, rates, discounts, taxes, and totals.
- Centralize calculation order, intermediate precision, currency quantization, and provider minor-unit conversion.
- Keep Estimate/EstimateLineItem and Invoice/InvoiceLineItem as separate concrete aggregates.
- Issue immutable rendering snapshots; later contact/catalog/settings changes must not rewrite history.
- Convert estimates through one atomic, idempotent service with row locks and a unique source-estimate constraint.
- Allocate numbers inside `transaction.atomic()` using `select_for_update()` on a per-business sequence.
- Store payments and reversals as the authoritative ledger. Cached invoice paid/balance values must be reconcilable.
- Derive Expired, Partial, Paid, and Overdue from dates and financial facts rather than editable workflow fields.

## Service and Transaction Convention

Important write services accept an authenticated actor and explicit trusted business, enforce membership/plan/state rules, perform multi-row writes atomically, lock rows when concurrency matters, create activity and outbox records, and return stable result objects.

Network calls must not occur inside database transactions. Email, PDFs, exports, webhook processing, and provider notifications run after commit through an outbox/worker path. Core financial workflows do not belong in `save()` methods or broad signals.

## Public Access and Integrations

- Public estimate/invoice URLs use at least 256 bits of random data, revocable purpose-scoped links, indexed token digests where practical, constant-time comparison, rate limits, and non-enumerating errors.
- Public viewing, acceptance, and payment are distinct permissions.
- Webhooks verify signatures against the raw request, persist unique provider event IDs before processing, return quickly, and process idempotently.
- Webhook order is not trusted; affected financial rows are locked and provider state is fetched when required.
- Stripe Billing subscription records and Stripe Connect invoice-payment records remain separate.
- The application never stores full card data.

## Web and API Conventions

- Django sessions and CSRF protection secure the server-rendered application.
- Bootstrap is currently loaded from a pinned CDN URL. HTMX 2.0.10 is checksum-verified, vendored, and self-hosted; shared JavaScript adds Django CSRF headers to HTMX requests.
- JavaScript enhances usability but does not own business rules.
- Growing lists are paginated and use deliberate `select_related`, `prefetch_related`, projections, aggregates, and measured indexes.
- A future API is versioned before external/mobile clients depend on it and applies the same tenant/policy/service rules as web views.

## Configuration and Environments

- `config.settings.base` contains shared settings and requires secrets/database configuration from environment variables.
- `config.settings.dev` enables debug behavior and the debug toolbar.
- `config.settings.prod` enables HTTPS enforcement, secure cookies, HSTS, WhiteNoise static assets, Redis caching, proxy-aware HTTPS configuration, and production host/origin parsing.
- ASGI, WSGI, the Docker image, and the Procfile default to production settings; `manage.py` and Compose local web use development settings.
- Logs currently go to console and `logs/django.log`; production should prefer centralized structured logging and must redact tokens, personal data, and payment payloads.

See [DEPLOYMENT.md](DEPLOYMENT.md) for operational procedures.

## Engineering Conventions

- Python target: 3.13.
- Formatting/linting: Ruff, 88-character line length, import sorting, pre-commit hooks.
- Tests: pytest and pytest-django against PostgreSQL.
- Environment configuration: `.env` locally; platform-managed secrets in production.
- Dependencies are pinned in `requirements.txt`; dependency/security checks belong in CI.
- Each change should be a coherent vertical slice with migrations, tenant/security impact, financial impact, tests, documentation, and rollback notes where relevant.

## Current Architecture Gaps

The Phase 2 Contact and ProductService domains use the trusted Phase 1 business context,
owner policy, scoped selectors, explicit atomic services, archive lifecycle, and
cross-tenant tests. Contact notes and activity are append-only through customer-facing
workflows. Full role policy, document snapshots, outbox/worker infrastructure, object
storage, financial calculators, and provider adapters remain later roadmap work.
