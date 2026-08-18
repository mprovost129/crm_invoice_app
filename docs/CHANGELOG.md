# Changelog

All meaningful completed changes are recorded here.

## Unreleased - Phase 7 In Progress (2026-08-12)

### Added

- Content Security Policy and related browser security headers, Subresource Integrity for
  the pinned Bootstrap assets, and HTMX configuration that disables script tags and eval.
- Central logging filter that redacts Stripe credentials, webhook signatures, passwords,
  secrets, and high-entropy public-link tokens.
- Cache-backed hourly limits for registration, verification resend, and password-reset
  email requests, plus validation and size bounds for caller-supplied request IDs.
- `launch_gate` and `provider_health_check` management commands for database, migration,
  cache, plan/subscription, ledger, communication, webhook, payment-attempt, provider, and
  deployment-configuration readiness.
- Launch checklist, incident-response guide, backup/restore rehearsal, and privacy and
  retention decision register.
- CI execution of launch, provider-health, and payment-reconciliation checks.

### Changed

- Print actions now use shared JavaScript rather than inline event handlers.
- Date-sensitive tests use each Business timezone explicitly, removing a host-midnight
  flake in overdue, expiry, and future-payment scenarios.
- Invalid acceptance, payment, reminder, reversal, void, and document-email submissions
  now retain bound values and field errors instead of redirecting away from context.
- Financial dialogs reopen after invalid submissions and focus the first invalid control;
  active application and settings navigation now exposes current-page semantics.
- Verified staff without an intentional customer-owner tenancy now route to Django Admin
  instead of entering customer onboarding and failing with a permission error.

### Verification

- 141 PostgreSQL-backed tests pass.
- Ruff lint and format, Django system checks, migration drift, production deployment
  checks, launch/provider health, and financial reconciliation pass.
- The local launch gate reports seven passes and four expected configuration warnings:
  local HTTP, console email, filesystem media, and Stripe sandbox values not yet supplied.

## Unreleased - Phase 6 Complete (2026-08-12)

### Added

- Configurable Plan and one-per-Workspace Subscription models with Free/Starter seed data,
  provider price identifiers, feature flags, usage limits, and inactive-paid-plan fallback.
- Backend enforcement for contact, business-local monthly estimate/invoice, reminder,
  reporting, export, and online-payment entitlements.
- Stripe Billing hosted subscription Checkout adapter plus separate verified platform
  webhook inbox, subscription synchronization, duplicate handling, and retry command.
- Stripe Express connected-account onboarding/readiness sync and hosted direct-charge
  invoice Checkout using separate Pay-purpose public links.
- InvoicePaymentAttempt reservation/idempotency records, exact minor-unit conversion,
  connected-account webhook validation, duplicate-safe immutable Online Payment posting,
  automatic receipt delivery, link revocation, and public payment throttling.
- Separate Connect webhook inbox/retry command and local/provider reconciliation commands
  for both SaaS subscriptions and client invoice payments.
- Phase 6 model, service, entitlement, tenant/account boundary, replay, ledger, race, and
  provider-adapter tests.

### Changed

- Registration creates the workspace's default Free Subscription atomically.
- Manual payment posting rejects an amount while a non-expired hosted checkout reserves
  the same invoice balance, preventing unsupported overpayment races.
- Invoice emails include a distinct secure payment link only when the tenant's plan and
  connected account are both ready; platform billing never writes invoice Payment rows.
- Settings expose subscription and online-payment operations while keeping final pricing
  and provider activation configurable.

### Verification

- More than 120 PostgreSQL-backed tests pass across Phases 0-6.
- Ruff, migration drift, Django checks, exact financial tests, tenant isolation, webhook
  replay/account matching, and local Stripe reconciliation pass.
- Real Stripe test-mode onboarding, signatures, Checkout, live reconciliation, and outage
  drills remain required Phase 7 staging evidence.

## Unreleased - Phase 5 Complete (2026-08-12)

### Added

- Tenant-safe dashboard cards for net paid this month, current outstanding and overdue
  receivables, and open-estimate value/count, all using established document/ledger rules.
- Needs Attention for overdue invoices, accepted estimates awaiting conversion, failed
  email, and stuck/failed outbox work, alongside recent cross-domain activity.
- Business-scoped owner Notification model and idempotent notifications for estimate
  acceptance/decline, recorded payments, overdue invoices, and delivery failures.
- Delivery-history search/status/type screens plus `outbox_health_check` and
  `sync_notifications` operator commands.
- Minimal collections, issued-invoice, current AR-aging, and estimate-performance reports.
- Tenant-safe client, all-contact, invoice, and payment CSV exports with UTF-8 BOM,
  spreadsheet-formula neutralization, no-store headers, deterministic ordering, and
  financial values that reconcile to invoice/ledger facts.
- Composite indexes for delivery/outbox operational queries and Phase 5 dashboard,
  reporting, export, notification, health, and tenant-isolation tests.

### Changed

- Estimate and invoice search now includes customer email and phone.
- Derived Expired, Partial, Paid, and Overdue list filters remain database QuerySets so
  pagination does not load the entire tenant dataset.
- The owner dashboard now preserves CRM/catalog quick access while adding financial and
  operational visibility.

### Verification

- One hundred thirteen tests pass against PostgreSQL 16.
- Dashboard/report totals and all financial CSV columns are covered by exact Decimal
  assertions including partial reversal behavior and foreign-tenant exclusion.
- Ruff lint, migration generation/application/drift, Django checks, ledger reconciliation,
  communication health, production deploy checks, and diff integrity pass locally.

## Unreleased - Phase 4 Complete (2026-08-12)

### Added

- Separate tenant-owned Invoice and InvoiceLineItem aggregate with direct draft creation,
  row-locked numbering, immutable issue snapshots, PDF/email delivery, secure public view,
  view tracking, derived status, and reasoned void workflow.
- Atomic idempotent accepted-estimate conversion that prevents concurrent duplicates,
  copies historical issued values without CRM/catalog re-entry, preserves the source
  Estimate, revokes response links, and promotes the same Lead record to Client.
- Immutable Payment and additive PaymentReversal ledger with invoice-total and
  balance-after evidence, deposits and any number of partial payments, atomic cached
  paid/balance updates, overpayment/future-date/reversal bounds, and tenant isolation.
- Manual invoice reminders and payment-receipt PDFs/emails through the durable outbox,
  plus invoice/payment activity events and invoice-aware client financial summaries.
- `reconciliation_check` management command comparing invoice caches to net posted ledger
  values, owner invoice/payment screens, read-only support admin, Phase 4 migrations, and
  representative invoice/receipt PDF QA tooling.

### Changed

- Communications snapshots, public links, file assets, and email delivery now enforce
  exactly one type-aligned Estimate, Invoice, or Payment target.
- Invoice PDF caching now keys on immutable snapshot content plus live paid, balance, and
  effective-status facts so unchanged requests reuse assets and payment changes generate
  a new accurate rendering.

### Verification

- One hundred three tests pass against PostgreSQL 16, including the automated manual exit
  path from Lead through Estimate, Acceptance, Invoice, Deposit, Partial payment, Final
  payment, and Paid.
- Ruff lint/format, Django checks, migration drift/application, reconciliation, and
  production deploy checks pass locally.
- Representative invoice and receipt PDFs were rendered to PNG with Poppler and visually
  inspected; tables, totals, notes, hierarchy, and page boundaries have no clipping,
  overlap, or broken glyphs.

## Unreleased - Phase 3 Complete (2026-08-12)

### Added

- Tenant-owned Estimate, EstimateLineItem, and immutable EstimateAcceptance models with
  database constraints and business-local derived expiration.
- Centralized Decimal calculator with half-up rounding, proportional discount allocation,
  tax-after-discount, deposit calculation, and provider minor-unit conversion.
- Owner estimate builder, line editing, atomic issue workflow, transaction-locked numbering,
  immutable JSON snapshots, list/search/status views, print/PDF, and manual acceptance.
- ReportLab 5.0.0 estimate PDFs generated from immutable snapshots and stored through
  Django's configurable storage backend with checksummed FileAsset metadata.
- Durable estimate-email delivery and outbox records, after-commit processing, PDF
  attachment delivery, failure state, and retry management command.
- High-entropy, digest-only, purpose-scoped public links with expiry/revocation,
  non-enumerating errors, rate limiting, view tracking, online accept/decline, and privacy
  headers.
- Estimate activity events, migrations, read-only support administration, navigation, and
  focused PDF layout QA tooling.

### Verification

- Eighty-one tests pass against PostgreSQL 16.
- Ruff lint/format, Django checks, migration drift, migration application, and production
  deploy checks pass locally.
- A representative estimate PDF was rendered to PNG and visually inspected; numeric
  columns, totals, notes, terms, and page footer fit without clipping or overlap.

## Unreleased - Phase 2 Complete (2026-08-12)

### Added

- Tenant-owned Contact model with database-constrained Lead, Client, and Archived lifecycle states.
- Contact list/search/status filters, create/edit/profile screens, same-record lead promotion, and archive/restore actions.
- Protected authored ContactNote records and append-only ActivityEvent history for contact and catalog workflows.
- Tenant-owned ProductService catalog with product/service type, standard/custom units, non-negative default rate, taxability, and active/archive lifecycle.
- Catalog search/type/status filters, create/edit/archive/restore screens, and owner-only navigation.
- Scoped selectors, explicit atomic write services, owner policy resolution, and stable backend entitlement hooks for future Plan rules.
- Safe staff administration for Contacts, notes, catalog items, and read-only activity events.
- Phase 2 CRM, catalog, and activity migrations plus cross-tenant service/web tests.

### Verification

- Fifty-two tests pass against PostgreSQL 16.
- Ruff lint/format, Django checks, migration drift/application, and production deploy checks pass locally.

## Unreleased - Phase 1 Complete (2026-08-12)

### Added

- Public registration with password validation and case-insensitive normalized email uniqueness.
- One-time email verification and resend flow, verified-user routing gates, and namespaced login/logout/password-reset paths.
- Atomic registration service creating a UUID Workspace and active owner Membership with the User.
- UUID Workspace, Membership, Business, and BusinessSettings tenancy models with protected relationships and database constraints for one active owner and one active business in V1.
- Verified-owner onboarding that atomically creates the Business, editable defaults, and per-business estimate/invoice DocumentSequence rows.
- Tenant request middleware, context processor, scoped querysets/selectors, verified/tenant/owner view mixins, and an empty authenticated dashboard.
- Owner-only business profile/default settings screen and read-only sequence administration.
- Phase 1 migrations and PostgreSQL-backed tests for identity, onboarding, constraints, request gates, settings, and cross-tenant isolation.

### Changed

- Email login and persistence now normalize the complete address consistently.
- Password-reset emails use the configured site identity and reset links expire after the configured timeout or any password change.
- Application navigation now reflects anonymous, verification, onboarding, and active-business states.

### Verification

- Thirty-eight tests pass against PostgreSQL 16.
- Ruff lint/format, Django checks, migration drift, migrations, and production deploy checks pass locally.

## Unreleased - Phase 0 Complete (2026-08-12)

### Added

- Email-first UUID `users.User` model with normalized unique email login, password hashing, staff/superuser flags, display-name helpers, and a migration-safe custom manager.
- Explicit user creation/change admin forms that do not assume a username field.
- UUID one-to-one `AccountProfile` for supplementary owner/support information, explicitly separated from future Business and CRM Contact entities.
- Customer-centric Django admin landing page with customer search, account metrics, profile editing, and links to related project records.
- `users/README.md` documenting `settings.AUTH_USER_MODEL` and `get_user_model()` conventions.
- Optional abstract `core.TimeStampedModel`.
- Separate process liveness and database readiness endpoints, with `/health/` retained as a readiness-compatible route.
- `X-Request-ID` correlation middleware.
- Environment-driven application identity, site URL, support email, language, timezone, email, database, upload limits, media storage, hosts, and trusted origins.
- Development/production settings split.
- Production HTTPS redirect, HSTS, secure cookies, referrer policy, content-type protection, Redis cache, WhiteNoise static storage, and optional trusted proxy handling.
- Generic Bootstrap base template, navigation, messages, footer, auth templates, and standard 400/403/404/500 pages.
- Multi-stage, non-root Docker image; health-checked local Compose stack for Django/PostgreSQL/Redis; Gunicorn process; and migration release command.
- Ruff configuration and Ruff pre-commit hooks.
- GitHub Actions quality gate for Ruff, formatting, migration drift/application, PostgreSQL tests, and production configuration.
- Canonical Docker setup and quality-gate instructions in the root README.
- Initial UUID User/AccountProfile migration, generated by Django 5.2.16 and applied successfully to PostgreSQL 16.
- Checksum-verified, self-hosted HTMX 2.0.10 plus shared Django CSRF header handling.
- Twenty-one passing PostgreSQL-backed tests for user/admin, UUIDs, health failure behavior, request IDs, HTMX inclusion, and environment validation.
- Product, scope, architecture, data model, roadmap, feature, decision, test, deployment, and changelog documentation derived from the approved planning documents and current code.

### Changed

- Standardized the project on Python 3.13 and Django 5.2.16 LTS for the longer April 2028 security-support window.
- Docker `collectstatic` uses build-only configuration so image creation is not coupled to runtime secrets.
- Shared templates use generic application identity instead of a hard-coded product name.
- Production host/origin parsing, email timeout, server email, upload limits, and configurable media backend were hardened.

### Known Incomplete Areas at Phase 0

- Registration, email verification, tenancy, business onboarding, and the empty authenticated app are completed in Phase 1 above.
- No CRM, catalog, estimate, invoice, payment, communication, billing, integration, export, or reporting domain implementation.
- No background worker/outbox, persistent production object storage selection, monitoring provider, automated backup, or restore evidence.

## Changelog Policy

- Add user-visible product outcomes, schema changes, important security/operational work, provider changes, and material architecture changes.
- Do not list formatting-only edits, dependency noise without impact, or work merely planned.
- Link architectural/product rationale to [DECISIONS.md](DECISIONS.md).
- Record migrations and any operator actions required for deployment.
- Once releases begin, use dated semantic-version headings and keep `Unreleased` at the top.
