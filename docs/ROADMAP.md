# Roadmap

Last reviewed: 2026-08-12

## Status Legend

- **Complete:** exit gate is demonstrably satisfied.
- **In progress:** meaningful implementation exists, but the exit gate is not satisfied.
- **Not started:** no product implementation exists beyond generic foundation support.
- **Deferred:** intentionally outside initial V1.

No percentage-complete estimate is used because the repository is not yet deep enough for one to be meaningful.

## Current Position

**Milestone 7 - Launch hardening is in progress.** The first provider-independent slice
adds browser security policy, log redaction, bounded public-auth rate limits, operational
launch/provider checks, CI enforcement, and backup/restore and incident-response runbooks.
The complete PostgreSQL regression suite currently passes at 131 tests.

Exact paid pricing, Stripe product/price IDs, credentials, and provider activation remain
explicit deployment decisions and are not fabricated in seed data. Sandbox activation is
the next Stripe step; live credentials belong only in the selected hosting platform's
secret manager.

## Ordered Delivery Plan

| Phase | Priority | Status | Depends on | Exit outcome |
| --- | --- | --- | --- | --- |
| 0. Repository and quality foundation | P0 | Complete | None | Reproducible PostgreSQL app boots; checks/tests/migrations pass in CI |
| 1. Identity, workspace, and onboarding | P0 | Complete | Phase 0 | Verified owner reaches an empty tenant-safe dashboard |
| 2. CRM and catalog | P0 | Complete | Phase 1 | Business manages tenant-safe leads/clients/notes/services |
| 3. Estimate workflow | P0 | Complete | Phase 2 | Accurate estimate can be issued, viewed, accepted/declined, and preserved |
| 4. Invoice conversion and manual payments | P0 | Complete | Phase 3 | Complete manual lead-to-paid workflow passes |
| 5. Dashboard, communications, and export | P1 | Complete | Phase 4 | Owner can understand cash/work status; exports reconcile |
| 6. SaaS billing and online payments | P1 | Complete | Stable manual workflow and Phase 5 operations | Subscription and invoice payments are idempotent and separated |
| 7. Launch hardening | P0 launch gate | In progress | All enabled V1 phases | Security, restore, migration, accessibility, monitoring, and E2E gates pass |
| Post-V1 extensions | P2 | Deferred | Validated V1 and customer demand | Automation, recurrence, teams, multiple businesses, API/mobile |

P0 means required for a safe core release; P1 may be sequenced after the manual workflow but is within intended commercial V1; P2 is post-V1.

## Phase 0 - Repository and Quality Foundation

### Completed foundation

- Python 3.13 Docker image and Gunicorn entry point.
- Split base/development/production settings.
- PostgreSQL configuration and Compose service.
- Redis Compose service and production cache configuration.
- Environment-driven secrets and application identity.
- Ruff, pre-commit, pytest, and pytest-django configuration.
- Base templates/static assets and standard error pages.
- Database-aware health endpoint and request IDs.
- Baseline production HTTPS/cookie/HSTS/static settings.

### Completed exit work

1. Standardized on Django 5.2 LTS and Python 3.13.
2. Adopted UUID identifiers for project-owned models before the first migration.
3. Renamed the generic profile to `AccountProfile` and separated its responsibility from future Business/Contact models.
4. Generated, reviewed, and applied the initial migration.
5. Added CI for Ruff, formatting, migration drift, PostgreSQL migrations/tests, and production checks.
6. Added canonical Docker setup and operator commands.
7. Added fail-fast environment parsing, production secret validation, and liveness/readiness behavior.
8. Vendored checksum-verified HTMX 2.0.10 and configured CSRF request headers.
9. Built a non-root multi-stage image and health-checked Compose stack.

## Phase 1 - Identity, Workspace, and Onboarding

### Completed scope

- Email-first custom user and manager.
- Custom admin forms and customer-centric support admin.
- Django login/logout/password-reset routing and templates.
- User/core foundation tests.
- Registration and email verification.
- Workspace, Membership, Business, BusinessSettings, and DocumentSequence models/migrations.
- Atomic registration service creating the owner tenancy hierarchy.
- Business onboarding/defaults and settings screens.
- One-active-business V1 policy.
- Active workspace/business request context.
- Tenant-scoped query/policy helpers and isolation test utilities.
- Empty authenticated dashboard and Phase 1 smoke test.

The Phase 1 boundary is proven by database constraints plus request, selector, service,
and cross-tenant tests. That boundary now supports the completed Phase 2 domains.

## Phase 2 - CRM and Catalog

### Completed scope

- Contact with database-constrained Lead, Client, and Archived lifecycle.
- Tenant-scoped list, search, filters, create, edit, archive, and restore workflows.
- Same-record lead-to-client promotion with preserved notes and history.
- Contact profile with contact data, future-financial zero state, durable notes, and activity.
- ProductService catalog with types, units/custom units, non-negative rates, taxability, and archive/restore.
- Owner policy, scoped selectors, explicit atomic services, and future entitlement hooks.
- Append-only activity for Contact and ProductService creation, edits, notes, and status changes.
- PostgreSQL constraints plus service and web cross-tenant denial tests.

The Phase 2 exit gate is satisfied. Completed Phases 3 and 4 depend on Contact and
ProductService while copying their values into separate document lines and immutable
issued-document snapshots.

## Phase 3 - Estimate Workflow

### Completed scope

- Transaction-locked tenant numbering and a centralized Decimal/half-up calculator.
- Draft estimate and line-item builder with discounts, tax-after-discount, deposits,
  notes, terms, dates, custom lines, and copied catalog values.
- Atomic issue transition with immutable canonical snapshot and append-only activity.
- ReportLab PDF renderer, configurable Django storage, attachment delivery, and reusable
  checksum-addressed file metadata.
- Durable email delivery/outbox records, after-commit processing, and retry command.
- High-entropy purpose-scoped public links stored only as SHA-256 digests, with expiry,
  revocation, throttling, no-referrer/no-index headers, and non-enumerating errors.
- View tracking, business-local derived expiration, optional online accept/decline, and
  immutable manual/online acceptance evidence.
- PostgreSQL constraints plus calculator, rollback, isolation, public-link, delivery,
  PDF, service, and web workflow tests.

ReportLab is the selected renderer. Django's email and storage interfaces are the provider
boundaries; actual production transactional-email and private object-storage services
remain deployment choices required before real customer documents are sent.

## Phase 4 - Invoice Conversion and Manual Payments

### Completed scope

- Atomic, idempotent, concurrent-safe accepted-estimate conversion that reuses the issued
  historical snapshot and promotes the same lead record to Client.
- Direct invoice builder, separate Invoice/InvoiceLineItem aggregate, row-locked numbering,
  immutable issue snapshot, owner lifecycle screens, PDF/email, and secure public view.
- Immutable manual Payment and additive PaymentReversal ledger with atomic paid/balance
  caches, deposits, partial/final payments, derived Paid/Partial/Overdue, and safe voiding.
- Durable invoice/reminder/receipt email delivery, payment receipts, activity history,
  client financial summary, and a reconciliation management command.
- PostgreSQL rollback/concurrency/isolation tests plus rendered invoice/receipt visual QA.

The exit gate is proven by an automated full manual workflow:

> Lead -> Estimate -> Acceptance -> Invoice -> Deposit -> Partial payment -> Final payment -> Paid

Online payments must not start until this gate is reliable.

## Phase 5 - Dashboard, Communications, and Export

### Completed scope

- Ledger-backed cards for net paid this month, outstanding/overdue receivables, and open
  estimates, plus Needs Attention and recent tenant activity.
- Idempotent owner notifications for acceptance, decline, payments, overdue invoices, and
  delivery failure; read handling remains tenant-scoped.
- Search refinements and paginated database-queryset filters for derived document states.
- Delivery status/search screens, stuck/failed outbox detection, and a command suitable for
  operational alerting.
- Minimal collections, issued-invoice, accounts-receivable aging, and estimate-performance
  reports.
- BOM-compatible, formula-injection-hardened client/contact, invoice, and payment CSV
  exports whose financial fields reconcile to invoice caches and net ledger values.

The Phase 5 exit gate is satisfied by tenant-boundary, exact-total, reversal, export,
notification, delivery-health, and web tests.

## Phase 6 - SaaS Billing and Online Payments

Completed application scope:

- Configurable Plan/Subscription records, Free/Starter seeds, status-aware backend feature
  enforcement, active-contact limits, and business-local monthly document limits.
- Stripe Billing Checkout adapter and subscription/checkout webhook synchronization.
- Stripe Express onboarding and readiness tracking for direct charges owned by each
  connected service business.
- Separate pay-purpose public links and hosted Checkout for the exact locked invoice
  balance; successful provider events create one immutable online Payment and receipt.
- Separate signature-verified Billing and Connect webhook inboxes, unique provider event
  IDs, row-locked processors, failed-event retention, and bounded retry commands.
- Manual-payment exclusion while an online checkout is active, exact minor-unit conversion,
  connected-account matching, link revocation after payment, throttling, and local/provider
  reconciliation commands.

Provider activation remains operational work: set final pricing, Stripe product/price IDs,
test/live credentials, and both webhook destinations, then complete staging reconciliation.

Manual payments remain independent and available.

## Phase 7 - Launch Hardening

### Completed launch-hardening slice

- CSP and browser security headers, pinned third-party asset integrity, and HTMX script/eval
  restrictions.
- Central log filtering for credentials, webhook signatures, passwords, and public tokens;
  untrusted request IDs are bounded and validated.
- Cache-backed registration, verification-resend, and password-reset request limits.
- `launch_gate` and `provider_health_check` commands covering dependencies, migrations,
  plans, subscriptions, reconciliation, delivery/webhook state, and environment readiness.
- CI execution of launch, provider-health, and financial-reconciliation checks.
- Provider-independent launch checklist, incident response, backup/restore rehearsal, and
  privacy/retention decision runbooks.
- Regression tests made deterministic at the business timezone boundary.

### Remaining exit work

- Complete the full tenant-isolation matrix and production-like browser E2E pass.
- Activate and exercise Stripe test mode, including onboarding, Checkout, webhooks,
  replay/order behavior, reconciliation, and outage drills.
- Rehearse production migrations against representative data.
- Configure automated backups and demonstrate an isolated restore using the runbook.
- Complete accessibility, responsive, customer email/PDF/link, and support-flow reviews.
- Select and configure production email, private storage, background processing,
  centralized monitoring, and hosting services.
- Approve and publish legal notices, retention/closure policy, and customer support terms.

## Post-V1 Roadmap

1. Automatic reminders.
2. Recurring invoices.
3. Additional users and tested roles.
4. Multiple active businesses.
5. Stronger/versioned API and public API policy.
6. Native mobile app.
7. Advanced reports, integrations, customization, and automations driven by evidence.

## Dependency Decisions

| Decision | Needed before |
| --- | --- |
| Final customer-facing component styling beyond Bootstrap/HTMX | Broad product screens |
| Transactional email provider | Production launch (Django email adapter is implemented) |
| Private object storage provider | Production launch (Django storage adapter is implemented) |
| Stripe account/product structure | Phase 6 |
| Hosting/worker/managed database platform | Launch rehearsal |
| Privacy, retention, and deletion policy | Real customer data |

## Progress Update Rule

Update this file when an exit criterion becomes demonstrably true, not when work merely begins. Keep detailed feature status in [FEATURES.md](FEATURES.md), completed outcomes in [CHANGELOG.md](CHANGELOG.md), and rationale in [DECISIONS.md](DECISIONS.md).
