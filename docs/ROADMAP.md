# Roadmap

Last reviewed: 2026-08-12

## Status Legend

- **Complete:** exit gate is demonstrably satisfied.
- **In progress:** meaningful implementation exists, but the exit gate is not satisfied.
- **Not started:** no product implementation exists beyond generic foundation support.
- **Deferred:** intentionally outside initial V1.

No percentage-complete estimate is used because the repository is not yet deep enough for one to be meaningful.

## Current Position

**Milestone 1 - Identity, workspace, and onboarding is complete.** Registration creates
the owner tenancy atomically, verification gates onboarding, one active business receives
validated defaults and document sequences, and the verified owner reaches a tenant-safe
empty dashboard. Thirty-eight PostgreSQL-backed tests pass locally.

The recommended next milestone is Phase 2 CRM and catalog, beginning with tenant-safe
Contact and ProductService models and service boundaries.

## Ordered Delivery Plan

| Phase | Priority | Status | Depends on | Exit outcome |
| --- | --- | --- | --- | --- |
| 0. Repository and quality foundation | P0 | Complete | None | Reproducible PostgreSQL app boots; checks/tests/migrations pass in CI |
| 1. Identity, workspace, and onboarding | P0 | Complete | Phase 0 | Verified owner reaches an empty tenant-safe dashboard |
| 2. CRM and catalog | P0 | Not started | Phase 1 | Business manages tenant-safe leads/clients/notes/services |
| 3. Estimate workflow | P0 | Not started | Phase 2 | Accurate estimate can be issued, viewed, accepted/declined, and preserved |
| 4. Invoice conversion and manual payments | P0 | Not started | Phase 3 | Complete manual lead-to-paid workflow passes |
| 5. Dashboard, communications, and export | P1 | Not started | Phase 4 | Owner can understand cash/work status; exports reconcile |
| 6. SaaS billing and online payments | P1 | Not started | Stable manual workflow and Phase 5 operations | Subscription and invoice payments are idempotent and separated |
| 7. Launch hardening | P0 launch gate | Not started | All enabled V1 phases | Security, restore, migration, accessibility, monitoring, and E2E gates pass |
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
and cross-tenant tests. Phase 2 may now begin.

## Phase 2 - CRM and Catalog

Build Contact, lead/client/archive lifecycle, client list/profile/notes/activity, ProductService, search, filters, and entitlement hooks. Exit requires tenant isolation for every operation and proof that lead-to-client reuses one record.

## Phase 3 - Estimate Workflow

Build transactional document sequences, calculator, Estimate/LineItem, draft builder, issue snapshot, PDF, email, secure public view, view tracking, optional online/manual acceptance, decline, and effective expiration.

Dependencies that must be selected before completion: transactional email provider, private object storage, and PDF renderer.

## Phase 4 - Invoice Conversion and Manual Payments

Build atomic idempotent conversion, Invoice/LineItem, invoice issue/snapshot/PDF/public view, manual Payment/Reversal ledger, deposits/partial payments, derived statuses, void, receipt, and manual reminder.

The exit gate is the full manual workflow:

> Lead -> Estimate -> Acceptance -> Invoice -> Deposit -> Partial payment -> Final payment -> Paid

Online payments must not start until this gate is reliable.

## Phase 5 - Dashboard, Communications, and Export

Build financial cards, Needs Attention, activity, notifications, delivery state, search refinements, client/invoice/payment CSV exports, minimal reports, reconciliation command, and stuck-job alerts. Exit requires tenant-safe totals and exports that reconcile to the ledger.

## Phase 6 - SaaS Billing and Online Payments

Build configurable plans/subscriptions/entitlements, Stripe Billing sync, Stripe Connect onboarding, hosted invoice payments, verified webhook inbox, idempotent processing, online receipts, and provider reconciliation.

Manual payments remain independent and available.

## Phase 7 - Launch Hardening

- Full tenant-isolation regression matrix.
- Numbering, conversion, payment, and webhook concurrency/retry tests.
- Security/privacy review, rate limits, CSP, upload/storage validation, and log redaction.
- Production migration rehearsal against representative data.
- Automated backup plus demonstrated restore.
- Accessibility and responsive passes.
- Professional email/PDF/customer-link review.
- Monitoring for app, worker, database, email, outbox, and webhooks.
- Terms, privacy, export, closure, support, and incident procedures.
- Production-like end-to-end launch smoke test.

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
| Email provider | Estimate delivery |
| Object storage and PDF renderer | Issued estimate snapshot/PDF |
| Stripe account/product structure | Phase 6 |
| Hosting/worker/managed database platform | Launch rehearsal |
| Privacy, retention, and deletion policy | Real customer data |

## Progress Update Rule

Update this file when an exit criterion becomes demonstrably true, not when work merely begins. Keep detailed feature status in [FEATURES.md](FEATURES.md), completed outcomes in [CHANGELOG.md](CHANGELOG.md), and rationale in [DECISIONS.md](DECISIONS.md).
