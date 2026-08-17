# Product Scope

Last reviewed: 2026-08-16

This document records the complete intended product boundary. It describes approved V1 behavior and deliberate post-V1 extensions; it does not imply that a feature is implemented. Current implementation status is tracked in [FEATURES.md](FEATURES.md).

## V1 Objective

Deliver a responsive web application that allows one owner to operate one service business through the complete lead-to-paid workflow without needing accounting knowledge.

## V1 Users and Account Boundary

- Email/password user account with secure sessions, verification, login/logout, and password reset.
- One SaaS workspace, one owner membership, and one active business in V1.
- Business data belongs to the business, not directly to the login identity.
- The schema may support future memberships and businesses, but the V1 product must not expose unfinished multi-user or multi-business behavior.

## V1 Functional Scope

### Registration and Onboarding

- Registration with name, email, and password.
- Email verification and password-reset flows.
- Lightweight onboarding for business identity, address, contact details, optional website/logo, currency, tax, payment terms, document prefixes, and starting numbers.
- Creation of workspace, owner membership, business, business settings, and document sequences.
- Editable business and account settings after onboarding.

### CRM and Client Records

- One `Contact` entity with Lead, Client, and Archived states; no separate lead table.
- One contact name, company, email, phone, postal address, notes, and status in V1.
- Tenant-scoped list, search, filters, create, edit, archive, and restore behavior.
- Client profile with contact information, financial summary, estimates, invoices, payments, activity, and notes.
- Automatic activity history for important document and payment events.
- Financially referenced contacts are archived rather than deleted.

### Products and Services

- Reusable product/service catalog with name, description, type, unit, default rate, taxability, and active state.
- Suggested units including each, hour, day, service, square foot, linear foot, and custom.
- Search, filtering, editing, activation, and archival.
- Custom estimate/invoice lines that do not require a catalog record.
- Snapshot catalog values into document line items so later catalog edits do not rewrite history.

### Estimates

- Tenant-unique estimate numbering with configurable prefix and starting number.
- Client, dates, line items, quantities, rates, tax, document discount, totals, deposit requirement, notes, and terms.
- Draft, Sent, Viewed, Accepted, Declined, Expired, and Converted effective states.
- Percentage or fixed document discount.
- No, percentage, or fixed deposit requirement.
- Draft editing and deterministic backend calculations.
- Preview, print, professional PDF, email, and secure public link.
- Customer view without an account.
- Optional online Accept/Decline actions.
- Manual acceptance with method and actor when acceptance occurs by email, phone, in person, or another channel.
- Immutable acceptance evidence and issued-document snapshots.
- Expiration derived from state, expiration date, business-local date, and timezone.

### Estimate-to-Invoice Conversion

- One explicit atomic conversion action.
- Validate authorization, tenant, estimate state, and required acceptance.
- Prevent duplicate or concurrent conversion.
- Copy contact identity/address, line items, currency, calculations, discount, tax, notes, terms, and deposit requirement into a new invoice snapshot.
- Preserve the original estimate unchanged.
- Allocate the invoice number in the same transaction.
- Create activity/outbox records and trigger external work only after commit.

### Invoices

- Direct invoice creation and estimate-derived invoice creation.
- Tenant-unique invoice numbering with configurable prefix and starting number.
- Client snapshot, issue/due dates, line items, discounts, taxes, subtotal, total, amount paid, balance due, notes, and terms.
- Draft, Sent, Viewed, Partial, Paid, Overdue, and Void effective states.
- Preview, print, professional PDF, email, and secure public link.
- Public view showing total, paid amount, balance, due date, and online payment action when enabled.
- Void workflow with reason; issued invoices are not silently deleted.

### Payments

- Independent payment ledger records linked to one invoice in V1.
- Manual payments with amount, date, method, optional note, and reference.
- Methods: cash, check, ACH, credit card, Venmo, PayPal, and other; listing a method does not imply provider integration.
- Deposits and any number of partial payments.
- Posted-payment total and invoice balance updated atomically.
- Partial and Paid states derived from ledger balance.
- Additive full or partial reversal records; posted payments are not edited or deleted in place.
- Receipts and payment activity after transaction commit.
- Online invoice payments through a provider-controlled Stripe Connect flow after the manual workflow is stable.

### Overdue Management and Communications

- Overdue derived when a non-void invoice has a positive balance after its business-local due date.
- Overdue display on dashboard, invoice list/detail, and client detail.
- Manual Send Reminder action in V1.
- Transactional emails for estimates, invoices, reminders, receipts, acceptance/decline, and payments.
- Secure document links; PDF attachments may supplement but not replace the link.
- Delivery-status tracking and operational visibility into failures.
- Internal notifications for estimate accepted/declined, payment received, and invoice overdue.

### Dashboard, Search, Reporting, and Export

- Dashboard cards for paid this month, outstanding invoices, overdue invoices, and open estimates.
- Needs Attention, Recent Activity, and quick actions.
- Search for client/contact fields, companies, email, phone, estimate numbers, and invoice numbers.
- Status filters for contacts, estimates, and invoices.
- Minimal revenue, accounts-receivable, and estimate reporting.
- Tenant-safe CSV exports for clients, invoices, and payments.
- Export values must reconcile with application totals.

### Settings and Account Operations

- Business identity, contact information, address, logo, and website.
- Estimate/invoice defaults, terms, notes, tax, currency, prefixes, and next numbers.
- Payment connection and accepted-method settings.
- User name, email, password, subscription, and security settings.
- Data export and account-closure procedure.

### Plans and Billing

- Configurable Plan, Subscription, entitlement, and optional usage-counter foundation.
- A genuinely useful Free tier: one business/user, limited active clients, estimates, invoices, manual payments, catalog, PDFs, email, dashboard, and application branding.
- Starter: materially higher limits plus online payments, branding, deposits/partial payments, reminders, reporting, and exports.
- Premium should launch only when it has meaningful differentiation; do not create artificial features to justify it.
- Server-side entitlement enforcement; templates may explain limits but never be the only enforcement.
- Stripe Billing for SaaS subscriptions and Stripe Connect for invoice payments, with separate models, provider identifiers, webhooks, and reconciliation.

**Implementation status (2026-08-12):** The application-layer Phase 6 scope is complete.
Free/Starter rules remain configurable; no final paid price was guessed. Stripe Billing
and Connect require environment-specific products, price IDs, credentials, webhook
destinations, and staging/live activation before customer use.

## Locked Financial Rules

- One default business currency; each estimate, invoice, and payment snapshots its currency.
- No V1 foreign-exchange conversion.
- Decimal arithmetic only; never use floating point for financial or quantity calculations.
- Line subtotal = quantity x unit rate.
- One document-level percentage or fixed discount.
- Discount allocated proportionally across lines.
- Tax calculated after discount and only on taxable amounts.
- Business supplies tax rates; the product does not determine tax law.
- Intermediate calculations retain sufficient precision; final totals use a centralized currency quantization policy.
- Issued subtotal, discount, tax, total, and rendering data are historical snapshots.
- Balance = invoice total - posted payments + posted reversals.
- Provider minor-unit conversion occurs through one tested adapter.

Changes to these rules require an entry in [DECISIONS.md](DECISIONS.md) and regression updates in [TEST_PLAN.md](TEST_PLAN.md).

## V1 Quality and Operational Scope

V1 includes tenant-isolation tests, concurrency tests for numbering/conversion/payment posting, idempotent webhook behavior, professional and accessible customer documents, responsive primary screens, error/empty states, migration rehearsal, backup restoration, monitoring, reconciliation, secure configuration, log redaction, support procedures, terms/privacy pages, and production-like end-to-end smoke testing.

## Explicitly Outside Initial V1

- General ledger, chart of accounts, expenses, bank feeds/reconciliation, payroll, tax filing, and automatic tax-law determination.
- Inventory, warehouse management, point of sale, purchase orders, and vendor management.
- Recurring invoices and automatic reminder schedules.
- Full client portal accounts.
- Multiple active businesses, multiple users, and role management.
- Multiple contacts/emails/phones per customer.
- Flutter applications for iOS and Android.
- Project management and manual task systems.
- Public API access, advanced automation/integrations, generic custom fields, and complex reporting.
- Enterprise-grade audit logging.

## Planned Post-V1 Extensions

1. Automatic reminder schedules.
2. Recurring invoices with duplicate-prevention and scheduling controls.
3. Additional users, roles, and active businesses.
4. Stable versioned API for first-party/external clients.
5. Flutter iOS and Android clients using the authoritative Django backend API.
6. Advanced reporting, integrations, customization, and automation based on validated demand.

## V1 Acceptance Boundary

V1 is complete only when all core features work together in a production-like environment, financial and tenant-safety suites pass, backups restore successfully, and this workflow is proven without customer or line-item re-entry:

> Lead -> Estimate -> Acceptance -> Invoice -> Deposit -> Partial payment -> Final payment -> Paid
