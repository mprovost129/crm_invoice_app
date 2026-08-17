# Decisions

Last reviewed: 2026-08-17

This is the architectural and product decision record. **Accepted** decisions govern V1 unless superseded by a later dated entry. **Deferred** decisions must be made before their dependency point. **Open** decisions require resolution before the stated work begins.

## D-001 - Build a Modular Django Monolith

**Status:** Accepted

**Decision:** Use one modular Django application backed by PostgreSQL, with clear domain apps and shared application services.

**Rationale:** This keeps deployment, transactions, local development, testing, and cross-domain financial workflows straightforward while preserving boundaries that can be extracted later if actual scale or team structure requires it. V1 does not justify microservice operational complexity.

## D-002 - Backend Owns All Business Rules

**Status:** Accepted

**Decision:** Web views, future API endpoints, workers, admin actions, and future mobile clients call the same backend services, policies, selectors, and calculators.

**Rationale:** Tenant, calculation, transition, and entitlement behavior must not diverge by interface. Views and serializers handle transport concerns, not financial orchestration.

## D-003 - Responsive Server-Rendered Web First

**Status:** Accepted

**Decision:** Build V1 with Django templates, progressive enhancement, HTMX where useful, and minimal focused JavaScript. After the web workflow and backend behavior stabilize, expose the same application services through a versioned REST API and build the first-party mobile clients with Flutter for iOS and Android.

**Rationale:** This is the fastest route to a reliable, understandable product without
duplicating logic. The repository uses Bootstrap and self-hosted HTMX as its current web
foundation.

## D-004 - PostgreSQL Is the Only Application Database Target

**Status:** Accepted

**Decision:** Use PostgreSQL in development, tests, and production; do not use SQLite as a temporary shortcut.

**Rationale:** Tenant constraints, row locking, concurrency-safe numbering, conversion, payment posting, indexes, and query behavior are central to correctness.

## D-005 - Separate Identity, SaaS Account, and Business Tenancy

**Status:** Accepted

**Decision:** Model `User -> Membership -> Workspace -> Business -> Business Data`. V1 exposes one owner and one active business, while the schema may support future users/businesses.

**Rationale:** A human login is not a business or subscription. Separating these concepts prevents a disruptive redesign and creates an explicit data-isolation boundary.

**Implemented (2026-08-12):** Registration creates User, Workspace, and owner Membership
atomically. Verified onboarding adds one active Business, BusinessSettings, and document
sequences. Database constraints and tenant-scoped request/service tests enforce the V1
boundary.

## D-006 - Direct Business Ownership on Domain Rows

**Status:** Accepted

**Decision:** Every business-owned record carries a direct Business foreign key. Reads begin from business-scoped querysets, and writes derive the business from trusted request context.

**Rationale:** Explicit tenancy makes isolation reviewable, indexable, testable, and enforceable. Inferring tenancy only through deep parent chains or checking ownership after a global lookup is too error-prone.

## D-007 - One Contact Model Represents Leads and Clients

**Status:** Accepted

**Decision:** Use one `Contact` entity with Lead, Client, and Archived states.

**Rationale:** The owner enters customer data once. Lead-to-client conversion changes status without copying the record or breaking its document/payment history.

**Implemented (2026-08-12):** Contact uses one UUID across Lead and Client states. Atomic
services manage promotion, archive, and restore; PostgreSQL lifecycle constraints and
tests prove notes and activity remain attached to the original record.

## D-008 - Estimate and Invoice Are Separate Aggregates

**Status:** Accepted

**Decision:** Implement separate Estimate/EstimateLineItem and Invoice/InvoiceLineItem models. Conversion creates a new invoice snapshot and preserves the estimate.

**Rationale:** Estimates and invoices have different lifecycle, audit, acceptance, payment, and legal meanings. A generic document table with a type field would create complex conditional behavior and weaken historical clarity.

## D-009 - Issued Documents Use Immutable Historical Snapshots

**Status:** Accepted

**Decision:** Copy customer, line, calculation, terms, notes, currency, and deposit data into issued documents and immutable rendering snapshots. Legitimate revisions create new versions.

**Rationale:** Later edits to business settings, contacts, products/services, prices, or tax defaults must not rewrite what a customer was sent.

**Implemented (2026-08-12):** Issuing an estimate atomically creates one canonical JSON
snapshot with a SHA-256 content digest. Snapshot and acceptance records reject updates,
and PDFs render from the snapshot rather than current CRM/catalog data.

## D-010 - Decimal and Centralized Calculation Policy

**Status:** Accepted

**Decision:** Never use floating point for financial or quantity values. Centralize the documented calculation order, discount allocation, tax-after-discount behavior, currency quantization, and provider minor-unit conversion.

**Rationale:** Financial results must be deterministic across web, jobs, exports, tests, and payment providers. Scattered arithmetic causes rounding and reconciliation errors.

**Implemented (2026-08-12):** The estimate calculator uses Decimal exclusively, four-place
intermediate values, half-up currency quantization, proportional document-discount
allocation, tax after discount, and explicit minor-unit conversion.

## D-011 - Payments Are an Immutable Ledger

**Status:** Accepted

**Decision:** Store each posted payment independently; correct it through additive reversal records. Treat the ledger as authoritative and invoice paid/balance totals as reconcilable caches.

**Rationale:** Editing or deleting posted financial records destroys auditability. Ledger-based balances naturally support deposits and multiple partial payments.

**Implemented (2026-08-12):** Posted Payment rows capture immutable invoice-total and
balance-after evidence. Corrections are additive full/partial PaymentReversal rows;
services lock the affected invoice/payment, enforce non-overpayment and reversal bounds,
update cached invoice totals atomically, and expose a ledger reconciliation command.

## D-012 - Financial and Date States Are Derived

**Status:** Accepted

**Decision:** Derive Estimate Expired and Invoice Partial/Paid/Overdue from workflow state, business-local dates, and ledger balances. Do not make them independently editable workflow values.

**Rationale:** These are facts. Stored editable copies drift and require unnecessary scheduled status mutation.

**Implemented (2026-08-12):** Invoice Paid, Partial, and Overdue are computed from void
state, current balance, amount paid, due date, and the Business timezone. Overdue takes
precedence over Partial once a positive balance passes its due date.

## D-013 - Allocate Document Numbers Transactionally

**Status:** Accepted

**Decision:** Maintain per-business/per-document sequence rows; allocate under `transaction.atomic()` and `select_for_update()`, with database uniqueness on the rendered number.

**Rationale:** `count() + 1` and application-only checks fail under concurrency. Numbers need only be unique within a business, not globally.

**Implemented (2026-08-12):** Estimate issue locks the tenant's sequence row, allocates the
number, persists the issue state, and creates the snapshot in one transaction; failures
roll back both the state and sequence increment.

Invoice issue and accepted-estimate conversion now use the same transaction-locked
sequence policy and rollback behavior.

## D-014 - Important Workflows Use Explicit Services

**Status:** Accepted

**Decision:** Registration, issuing, acceptance, conversion, payment posting/reversal, reminders, connected-account changes, and subscription changes use explicit application services and transaction boundaries.

**Rationale:** Important transitions need consistent authorization, state validation, row locking, audit/outbox records, and retry behavior. Core financial workflows do not belong in `save()` hooks or broad signals.

## D-015 - Use a Transactional Outbox for External Side Effects

**Status:** Accepted for the phase requiring asynchronous work

**Decision:** Create outbox records in the same transaction as domain changes; workers send email, render PDFs, process webhooks, create exports, and run reconciliation after commit.

**Rationale:** This prevents messages for rolled-back transactions, missing jobs after successful commits, and duplicate side effects during retries. Network calls must not extend database transactions.

**Implemented foundation (2026-08-12):** Estimate email writes delivery and deduplicated
outbox rows atomically, processes after commit, records attempt/failure/completion state,
and supports command-driven retry. A dedicated production worker and retry scheduler are
still required before launch.

Invoice delivery, manual reminders, and payment receipts now use the same durable delivery
and outbox boundary with document-appropriate PDF attachments and digest-only links.

## D-016 - Separate Subscription Billing from Invoice Payments

**Status:** Accepted

**Decision:** Stripe Billing handles the platform customer's subscription; Stripe Connect handles that customer's client invoice payment. Models, identifiers, webhooks, reconciliation, and services remain separate.

**Rationale:** These payments have different merchants, beneficiaries, accounting meaning, failure modes, and support procedures. Mixing them risks serious financial errors.

## D-017 - Public Documents Use Revocable Purpose-Scoped Tokens

**Status:** Accepted

**Decision:** Use high-entropy, non-sequential public tokens, store digests where practical, and scope each link to one document and action such as view, accept, or pay.

**Rationale:** Customers should not need accounts in V1, but public access must resist guessing, enumeration, replay, and privilege escalation while supporting immediate revocation.

**Implemented (2026-08-12):** Estimate links use cryptographically random URL-safe tokens;
only SHA-256 digests are stored. View and respond purposes are distinct, links expire and
can be revoked, response links are revoked after a terminal response, and public routes
use throttling plus non-enumerating errors and privacy headers.

Invoice view links use the same security boundary and cannot be created with estimate-only
response permission.

## D-026 - ReportLab and Framework Provider Adapters for Phase 3

**Status:** Accepted 2026-08-12

**Decision:** Pin ReportLab 5.0.0 for server-side estimate, invoice, and receipt PDFs. Use Django's email and
default-storage interfaces as the Phase 3 provider boundaries rather than coupling domain
services to a specific transactional-email or object-storage vendor.

**Rationale:** ReportLab produces consistent PDFs directly from immutable snapshots and
payment evidence.
Django's adapters keep local testing reliable and let deployment select private storage
and transactional email without rewriting document workflows. Provider selection and
credentials remain launch operations decisions, not domain-model concerns.

**Implemented for Phase 4 (2026-08-12):** Invoice PDFs use the immutable issued snapshot
for document identity and line/totals history while adding current paid/balance/status
facts. Their cache key combines the snapshot digest with that live payment state. Payment
receipt PDFs render from immutable payment snapshots. Representative invoice and receipt
pages were rendered through Poppler and visually verified.

## D-018 - V1 Is Not Accounting or ERP Software

**Status:** Accepted

**Decision:** Exclude general ledger, bank reconciliation, expenses, payroll, tax filing, inventory, purchase orders, and related ERP scope.

**Rationale:** The product's value is the service-business lead-to-paid workflow. Accounting/ERP scope would materially delay it and create legal/compliance expectations the product is not intended to meet.

## D-019 - Manual Workflow Precedes Automation and Online Payments

**Status:** Accepted

**Decision:** Prove manual acceptance, conversion, payment, reminder, receipt, and reconciliation before automatic reminders, recurring invoices, or online payment processing.

**Rationale:** Automation and providers add scheduling, retries, timezones, webhooks, duplicate delivery, and support complexity. They should automate a correct workflow, not conceal an incomplete one.

## D-020 - Plan Definitions and Limits Are Configurable

**Status:** Accepted

**Decision:** Store pricing/features/limits in plan configuration and enforce entitlements on the backend. Treat proposed price points and the Free active-client limit as hypotheses.

**Rationale:** Commercial packaging will change with validation. Hard-coded pricing and template-only checks make changes unsafe and easy to bypass.

## D-021 - Lifecycle-Safe Deletion

**Status:** Accepted

**Decision:** Allow hard deletion only for safe drafts without downstream history. Archive contacts, void issued invoices, preserve sent estimates, and reverse posted payments.

**Rationale:** Ordinary CRUD deletion is inappropriate for customer-visible and financial records.

## D-022 - Framework Version Baseline

**Status:** Accepted 2026-08-12

**Decision:** Standardize Phase 0 on Python 3.13 and Django 5.2 LTS, initially pinned to Django 5.2.16.

**Rationale:** Django 5.2 supports Python 3.13 and receives security/data-loss fixes through April 2028. Django 6.0's extended support ends in April 2027. The longer-supported LTS is the safer foundation for a new financial workflow product, and the latest confirmed 5.2 security patch was selected.

## D-023 - Domain Identifier Strategy

**Status:** Accepted 2026-08-12

**Decision:** Use UUID primary keys for all project-owned persisted entities, beginning with User and AccountProfile in the initial migration. Django/framework-owned tables retain their native identifiers.

**Rationale:** UUIDs fit the external identifier and tenant-safety architecture, avoid a later primary-key conversion, and remove sequential project identifiers before real data exists.

## D-024 - Account Profile Is Not a Business or CRM Contact

**Status:** Accepted 2026-08-12

**Decision:** Rename the generic `CustomerProfile` to `AccountProfile` before the first migration. Limit it to supplementary login-owner/support metadata. Business identity belongs to the future Business model; client/customer data belongs to Contact.

**Rationale:** The original name collided with product language and could encourage domain data to be stored at the wrong boundary. The explicit name/responsibility prevents that drift while preserving useful staff support metadata.

## D-025 - Self-Host Stable HTMX 2.x

**Status:** Accepted 2026-08-12

**Decision:** Vendor HTMX 2.0.10 under application static assets, verify its SHA-384 digest against the official published integrity value, and provide shared Django CSRF header integration.

**Rationale:** HTMX is the approved V1 enhancement layer. Self-hosting a pinned stable asset avoids runtime CDN availability and supply-chain drift without introducing a Node build pipeline during Phase 0.

## D-027 - Operational Read Models and Exports Share Ledger Definitions

**Status:** Accepted 2026-08-12

**Decision:** Calculate collected cash as posted payments minus reversals in the selected
business-local period. Calculate current accounts receivable from non-draft, non-void
invoice balance caches that are continuously reconcilable to the immutable ledger. Use
these same definitions in dashboard cards, reports, client summaries, and CSV exports.

**Rationale:** Parallel definitions of paid, outstanding, or overdue values would cause
screens, files, and operational checks to disagree. Central selectors and exact Decimal
assertions make discrepancies visible instead of silently presenting conflicting totals.

**Consequences:** Historical collection reports assign payments by `paid_on` and reversals
by their recorded reversal timestamp. Receivables and aging are intentionally current
operational views, not reconstructed historical accounting statements. CSV output is
tenant-scoped, UTF-8 BOM compatible, non-cacheable, and neutralizes spreadsheet formulas.

## D-028 - Stripe Express Direct Charges for Client Invoice Payments

**Status:** Accepted 2026-08-12

**Decision:** Use hosted Stripe Checkout with direct charges on one Express connected
account per Business. The connected service business owns the client charge and receives
the funds. Do not collect an application fee in V1. Use the platform Stripe account only
for the workspace's SaaS subscription. Terminate Billing and Connect events at separate
signed endpoints and persist them in separate inbox models.

**Rationale:** The service business is the seller to its client; the application is SaaS,
not a marketplace merchant. Direct charges align charge ownership, connected-account
branding, refunds/disputes, and funds with that relationship while preserving D-016's
strict accounting separation.

**Consequences:** Direct-charge PaymentIntent/Checkout objects must be queried in the
connected-account context. A top-level webhook account ID must match the tenant's stored
connection before ledger mutation. The browser redirect never confirms payment; only a
verified provider event can create an Online Payment. Final Connect liability settings,
countries, payment methods, platform terms, and live activation require launch review.

## D-029 - Keep Launch Controls Provider-Independent

**Status:** Accepted 2026-08-12

**Decision:** Implement security headers, sensitive-data log filtering, bounded public-auth
rate limits, application/provider health commands, and operational runbooks without tying
them to a specific hosting, monitoring, email, storage, or backup vendor. Keep Stripe test
and live credentials strictly environment-managed and separate; sandbox configuration may
be used locally, while live values are installed only in the chosen production platform's
secret manager.

**Rationale:** Provider selection should not delay controls that can be proven inside the
application. A stable command/runbook contract also reduces migration cost if vendors
change and gives any future platform explicit health, alert, backup, and rollback hooks.

**Consequences:** Deployment is not complete merely because the repository commands pass.
The selected platform must schedule and alert on them, provide tested database/media
backups, centralize redacted logs, and supply production services. Stripe sandbox and live
webhooks, keys, prices, and evidence must never be mixed.

## D-030 - Flutter Is the First-Party Mobile Client

**Status:** Accepted 2026-08-16

**Decision:** Retain Django templates and HTMX for the responsive web application. Build
the later iOS and Android applications from one Flutter/Dart codebase against a versioned
Django REST API. Django remains authoritative for tenancy, entitlements, calculations,
number allocation, document lifecycle, payments, and audit-sensitive state changes.

**Rationale:** Web-first delivery validates the workflow quickly, while Flutter provides
one maintainable mobile client without duplicating financial rules. A client-driven API
phase keeps the contract focused on proven use cases instead of speculative endpoints.

**Consequences:** Do not replace the working server-rendered web application with Flutter
Web. Before mobile mutation endpoints ship, define authentication/token revocation,
versioning, idempotency keys, optimistic concurrency, pagination, error envelopes, and
offline/retry behavior, and prove them with contract and tenant-isolation tests.

## D-031 - Ship the Neutral Visual Baseline Before Final Branding

**Status:** Accepted 2026-08-17

**Decision:** Implement the approved web visual component system now using its neutral
slate surfaces, restrained primary blue, system typography, desktop sidebar, mobile
offcanvas navigation, and shared responsive components. Do not delay usable product UI
for a final logo, product name, or custom brand palette.

**Rationale:** Navigation, hierarchy, accessibility, responsive behavior, and financial
clarity can be proven independently of final identity work. Semantic tokens make later
branding changes localized rather than a template rewrite.

**Consequences:** Treat the current identity as provisional. Final branding must replace
semantic identity tokens and approved assets without changing workflow or component
structure. The neutral implementation still requires interactive desktop/tablet/phone
and accessibility review before launch.

## Deferred Provider and Product Decisions

The following are intentionally deferred until their dependency point: final product name/domain and brand assets, hosting platform, transactional email provider, object storage provider, error-monitoring provider, exact paid pricing/discounts and launch timing, Stripe product/price IDs and live-account configuration, Premium differentiation/timing, automatic reminder rules, recurring invoice rules, and privacy/retention policy.

Record each final choice here with date, alternatives, rationale, and consequences.
