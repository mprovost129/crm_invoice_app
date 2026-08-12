# Test Plan

Last reviewed: 2026-08-12

## Purpose

Testing must prove the product is financially correct, tenant-isolated, retry-safe, operationally recoverable, and understandable through the complete lead-to-paid workflow. Authentication, tenancy, issued documents, and payments are not complete when only their happy paths work.

## Current Test Baseline

Thirty-eight PostgreSQL-backed pytest tests pass through Phase 1:

- Custom email user is configured and has no username field.
- User creation normalizes email and hashes the password.
- Superuser creation sets required flags.
- User and AccountProfile use UUID primary keys, and AccountProfile is one-to-one with User.
- Staff admin landing page exposes customer search.
- Liveness and readiness endpoints report success, and readiness reports database failure as HTTP 503.
- Request ID is preserved on the response.
- The base application uses self-hosted HTMX rather than a runtime HTMX CDN.
- Required, CSV, boolean, and production-secret environment validation is deterministic.
- Registration atomically creates the normalized User, Workspace, and active owner Membership.
- Verification tokens are one-time, reset tokens are password-invalidated, and routing gates unverified users.
- Onboarding atomically creates Business, BusinessSettings, and estimate/invoice sequences.
- One-active-owner and one-active-business constraints reject invalid tenancy states.
- Tenant selectors, settings services, request context, and owner-only settings deny cross-tenant or underprivileged access.
- A verified owner can complete onboarding and reach the empty tenant-safe dashboard.

CRM, catalog, issued-document, financial, public-link, provider, export, and full V1
end-to-end tests do not exist yet; those follow the roadmap dependencies.

## Test Environments and Tooling

- Use pytest and pytest-django.
- Use PostgreSQL for development, CI, and test execution; do not substitute SQLite.
- Use deterministic factories/fixtures and obviously fictional seed data.
- Freeze or explicitly control current time, business timezone, and provider callbacks where relevant.
- Mock network boundaries in unit/service tests; use provider test modes in integration/staging tests.
- Run concurrency tests against a real database with separate connections/transactions.
- Track query counts for critical lists, dashboard selectors, and client profiles.
- Measure coverage as a diagnostic, not as a replacement for risk-based scenarios.

## Required Test Layers

### Model and Constraint Tests

Prove database uniqueness, checks, deletion behavior, parent/child business consistency, currency consistency, positive quantities/amounts, bounded percentages, valid lifecycle fields, and provider identifier uniqueness. Test both allowed reuse across businesses and forbidden duplicates within one business.

### Calculator Tests

Test the centralized calculator independently with exact Decimal assertions for every intermediate and final value. Include:

- Empty document behavior.
- One fixed-price line and multiple lines.
- Decimal quantities and four-place unit rates.
- Taxable and non-taxable lines.
- Percentage and fixed document discounts.
- Proportional discount allocation across taxable/non-taxable lines.
- Tax after discount.
- Percentage/fixed deposits.
- Zero tax and each supported currency precision.
- Half-unit rounding boundaries and accumulated rounding.
- Invalid negative or excessive values.
- Provider minor-unit conversion.

Expected values must be literal fixtures derived from the documented policy, not calculated in tests using the same production algorithm.

### Service Tests

For every important service, test authorized success, unauthorized actor, cross-tenant input, invalid state, validation failure, atomic rollback, activity/outbox creation, and idempotent retry where relevant.

High-risk services include registration/tenant creation, document number allocation, issuing, acceptance, estimate conversion, invoice voiding, payment posting, payment reversal, reminders, connected-account updates, subscription changes, and webhook processing.

### Selector and Query Tests

Prove correct tenant filtering, derived statuses, timezone boundaries, aggregate totals, pagination, ordering, filter/search results, prefetch/select behavior, and bounded query counts.

### Web and API Tests

Test authentication redirects, CSRF, permissions, validation messages, safe 404 behavior for foreign objects, submitted tenant-key rejection, form errors, public link purpose/revocation/expiration/rate-limit behavior, accessibility semantics, and responsive critical paths. Apply identical policy/service expectations to future API endpoints.

### Integration Tests

Cover email/provider failure, PDF/object-storage failure, transaction rollback, webhook signatures, duplicate/out-of-order events, provider timeouts, test/live credential separation, and current-state reconciliation.

### End-to-End Tests

Exercise the browser/customer/operator workflow in a production-like environment, including secure links, email/PDF output, deposit/partial/final payment, dashboard reconciliation, exports, and account operations.

## Non-Negotiable Business Rules

The suite must prove:

- One Contact transitions from Lead to Client without copying history.
- Every business-owned operation is isolated to the trusted active Business.
- Estimate and Invoice are distinct aggregates with distinct line items.
- Conversion copies a complete immutable historical snapshot.
- One Estimate creates at most one Invoice, including concurrent/retried requests.
- Document numbers are unique per Business and safe under concurrency.
- Money uses Decimal and the locked calculation order.
- Issued totals/PDF payloads do not change after source edits.
- Payments and reversals are immutable ledger entries.
- Invoice caches equal ledger-derived amount paid and balance.
- Payment/reversal amount, state, business, and currency rules are enforced.
- Partial, Paid, Overdue, and Expired are derived correctly in the Business timezone.
- Void invoices reject new payments.
- External side effects occur after commit and are not duplicated on retry.
- Public links expose only their document and permitted action.
- Plan limits are enforced by the backend.
- SaaS subscription billing never contaminates invoice-payment records.

## Tenant-Isolation Matrix

For each business-owned resource, test list, retrieve, create, update, archive/void, allowed delete, search, filter, export, foreign-key attachment, and custom actions.

Resources include BusinessSettings, Contact, ProductService, Estimate/LineItem/Acceptance, Invoice/LineItem, Payment/Reversal, ActivityEvent, PublicDocumentLink, DocumentSnapshot, FileAsset, EmailDelivery, ConnectedAccount, and exports.

Each operation must assert:

1. Own-business behavior succeeds or fails for the correct business reason.
2. Another business's object is invisible and unchanged.
3. Submitted foreign business/parent IDs are rejected or replaced with trusted context.
4. Errors do not reveal foreign-object existence.
5. Staff jobs and background tasks require explicit tenant context.
6. Public tokens remain limited to their document and purpose.

## Critical Acceptance Scenarios

1. **Registration/onboarding:** normalized unique user, verified email, one workspace/owner/business, settings/sequences, tenant-safe empty dashboard.
2. **Lead reuse:** one Contact retains estimates, invoices, payments, notes, and activity after status changes to Client.
3. **Estimate calculation:** mixed taxability, discount, tax, and deposit produce exact stored intermediate/final totals.
4. **Acceptance flexibility:** online acceptance stores true public evidence; manual acceptance records its actual external method/actor.
5. **Idempotent conversion:** duplicate/concurrent requests create exactly one Invoice and preserve Estimate history.
6. **Partial payment:** deposit updates ledger, amount paid, balance, client summary, and Partial state consistently.
7. **Final payment:** exact final payment reaches zero balance, derives Paid, and queues one receipt after commit.
8. **Overdue:** unpaid non-void invoice becomes Overdue after the business-local due date without manual state edits.
9. **Reversal:** original Payment remains; reversal is bounded/auditable and increases balance exactly.
10. **Webhook replay/order:** repeated or out-of-order verified events do not duplicate provider or ledger effects.
11. **Historical accuracy:** later business/contact/catalog/tax edits do not change issued document snapshots/PDFs.
12. **Export trust:** export contains only active-business data and reconciles to application totals.

## Financial Matrix

At minimum, cover payments smaller than, equal to, and greater than balance; multiple partial payments; failed online payment; duplicate event; full/partial reversal; reversal overflow; void invoice; past-due unpaid/paid invoice; concurrent payment posting; cross-currency input; and ledger-to-cache reconciliation.

Every financial assertion checks source ledger rows, cached aggregates, effective status, activity, outbox side effects, and rollback behavior.

## Security and Privacy Tests

- Login/reset/public-link rate limits and non-enumerating responses.
- CSRF and session invalidation.
- Secure cookie/proxy/HTTPS behavior in production settings.
- High-entropy public tokens, digest comparison, purpose, expiration, and revocation.
- Webhook raw-body signature verification.
- Upload type/size rules and private storage access.
- No full card data, tokens, credentials, or sensitive provider payloads in models/logs/errors.
- Export, account closure, archive/void/reversal, and retention behavior.
- Staff/admin restrictions on financial edits and destructive bulk actions.

## Reliability and Performance Tests

- Concurrent document numbering and estimate conversion.
- Concurrent/retried payment posting and webhook processing.
- Outbox retry, poison/stuck job visibility, and idempotent consumers.
- Dashboard/list query counts with representative seed volume.
- Pagination of every growing list.
- PDF, export, and email work is asynchronous and does not hold long transactions.
- Reconciliation reports discrepancies and never silently repairs financial history.
- Health/readiness detects database failure; future worker/provider health is monitored separately.

## Accessibility and Presentation QA

- Keyboard access to critical flows and visible focus.
- Correct labels, errors, headings, button/link semantics, and announcements.
- Phone, tablet, and desktop layouts for primary screens.
- Customer emails, secure pages, printed documents, and PDFs are readable and professionally branded.
- PDF snapshots contain correct client/business data, lines, totals, dates, terms, notes, paid/balance values, and no clipping/overflow.

## Migration, Backup, and Deployment Tests

- `makemigrations --check --dry-run` reports no model drift.
- Migrations apply from an empty database and from the latest production-like schema/data.
- Forward and backward application compatibility is tested for expand/contract changes.
- Production migration rehearsal records duration and lock impact.
- Automated backup completes, restore creates a usable isolated database, and reconciliation/smoke tests pass on restored data.
- Post-deploy smoke verifies health, auth, tenant context, core write/read, worker/outbox, email/provider test path as appropriate.

## Pull Request Gate

Every coherent change must identify business outcome, migrations, tenant/security impact, financial impact, tests, screenshots for UI work, and rollback/recovery notes for risky changes. Ruff, formatting, migration drift, and relevant tests must pass. Authentication, tenancy, calculations, numbering, conversion, payments/reversals, webhooks, deletion, and entitlements require extra review.

## Release Gate

Release requires all enabled feature acceptance tests, the tenant matrix, concurrency/retry suites, reconciliation, migration rehearsal, verified backup restore, security/accessibility checks, and a production-like end-to-end workflow to pass. Known failures in tenant isolation or financial integrity block release.
