# Data Model

Last reviewed: 2026-08-12

## Status Legend

- **Implemented:** model exists in repository code.
- **Planned:** approved V1 model, not yet implemented.
- **Post-V1:** extension point intentionally not exposed in V1.

The repository includes migrations through Phase 3 for `users`, `workspaces`, `core`,
`crm`, `catalog`, `activity`, `estimates`, and `communications` with Django 5.2.16 against
PostgreSQL 16.

## Current Implemented Models

### `users.User` - Implemented

Email-first authentication identity based on `AbstractBaseUser` and `PermissionsMixin`.

Important fields: UUID primary key, case-insensitively unique normalized email,
first/last name, email-verification timestamp, active/staff flags, joined date, last
login, password, groups, and permissions. `email` is the login identifier.

This is a human login identity. Business data must not be attached directly to it.

### `users.AccountProfile` - Implemented

UUID one-to-one supplementary profile for an authenticated user, containing company name, phone, internal notes, and timestamps.

This model is deliberately limited to login-owner/support metadata. It is not the planned CRM `Contact`, workspace `Business`, or customer/client record.

### `core.TimeStampedModel` and `BusinessOwnedModel` - Implemented abstract models

`TimeStampedModel` provides indexed `created_at` and `updated_at` timestamps.
`BusinessOwnedModel` adds a UUID primary key and required protected Business foreign key
for future tenant-owned domain rows.

## Target Relationship Map

```text
User 1 ----< Membership >---- 1 Workspace ----< Business
                                  |
                                  +---- 1 Subscription

Business 1 ---- 1 BusinessSettings
Business 1 ----< DocumentSequence
Business 1 ----< Contact
Business 1 ----< ProductService
Business 1 ----< Estimate ----< EstimateLineItem
                         |
                         +---- 0..1 EstimateAcceptance
                         +---- 0..1 Invoice (conversion source)
Business 1 ----< Invoice ----< InvoiceLineItem
                        |
                        +----< Payment ----< PaymentReversal

Estimate/Invoice ----< PublicDocumentLink
Estimate/Invoice ----< DocumentSnapshot ---- 0..1 FileAsset (PDF)
Estimate/Invoice/Payment ----< EmailDelivery
Business ----< ActivityEvent
Workspace/User ----< Notification
Business ---- 0..1 ConnectedAccount
Provider ----< WebhookEvent
Domain transaction ----< OutboxEvent
```

## Identity and Tenancy

### `Workspace` - Implemented

The SaaS account, subscription, and entitlement boundary. It has a globally unique slug and lifecycle status. One workspace has one active owner membership and one active business in V1; the schema may support more later.

### `Membership` - Implemented

Joins User and Workspace, with a unique pair plus role and status. Only the owner role is exposed in V1. Future admin/member roles must remain inaccessible until their permissions are implemented and tested.

### `Business` - Implemented

The strict isolation boundary for contacts, catalog, documents, payments, files, and activity. It stores operating identity, contact/address data, currency, timezone, logo reference, active state, and archive lifecycle.

Every business-owned entity below carries a direct business foreign key even when that relationship could be inferred through its parent.

### `BusinessSettings` - Implemented

One-to-one with Business. Stores validated estimate/invoice prefixes and defaults for
terms, expiration, tax, and notes. Number allocation itself belongs in
`DocumentSequence`; branding assets remain planned.

## CRM and Catalog

### `Contact` - Implemented

One record represents either a lead or client using a status field. Stores one V1 contact name, company, email, phone, address, notes, creator, conversion timestamp, and archive lifecycle.

Relationships: belongs to Business; referenced with deletion protection by estimates and invoices; related client history is read from estimates, invoices, payments, and activities. Financially referenced contacts are archived rather than deleted.

The implemented lifecycle constraint keeps Lead, Client, and Archived timestamps/state
consistent. Promotion updates the same UUID record, and archive/restore remembers whether
the contact was a lead or client. `ContactNote` stores protected, tenant-owned authored
notes without exposing edit/delete workflows.

### `ProductService` - Implemented

Reusable catalog record belonging to Business. Stores name, description, product/service type, unit, rate, taxability, active state, and archive lifecycle.

Document lines may retain a nullable protected source reference, but always copy the item values into snapshot fields.

The implemented catalog validates non-negative default rates, standard/custom units, and
active/archive consistency. Estimate lines may retain its protected source while copying
all customer-visible values.

## Shared Financial Infrastructure

### `DocumentSequence` - Implemented

One row per `(business, document_type)` with prefix, next positive value, and padding width. Allocation locks the row and creates the target document in one transaction. Database uniqueness separately protects visible document numbers within a business.

## Estimates

### `Estimate` - Implemented

Belongs to Business and protected Contact. Stores sequence/visible number, workflow status, currency, issue/expiration dates, discount and deposit configuration, persisted subtotal/discount/tax/total, notes/terms, acceptance requirement, transition timestamps, and creator.

Workflow values: Draft, Sent, Viewed, Accepted, Declined, Converted. Expired is derived for sent/viewed estimates whose expiration date has passed in the business timezone.

Key constraints: `(business, number)` unique; non-negative monetary values; bounded percentages; valid timestamp/state combinations; only one conversion.

### `EstimateLineItem` - Implemented

Belongs to Estimate and directly to Business. Stores position, optional source catalog item, copied name/description/unit/rate/tax fields, quantity, and calculated line totals.

Key constraints: unique position per estimate, positive quantity, non-negative values, and child business equal to parent business.

### `EstimateAcceptance` - Implemented

Immutable, one-to-one proof of acceptance. Stores method, optional accepting identity, timestamp, optional IP/user agent under a retention policy, recording user, terms/total snapshots, and constrained metadata.

Online and manually recorded acceptance use the same business outcome without misrepresenting the evidence source.

## Invoices and Payments

### `Invoice` - Planned

Belongs to Business and protected Contact; optionally has a unique one-to-one source Estimate. Stores visible number, workflow state, currency/dates, contact and billing snapshots, line/tax/discount totals, cached amount paid/balance, deposit requirement, notes/terms, delivery/view/void timestamps, reason, and creator.

Editable workflow values are Draft, Sent, Viewed, and Void. Partial, Paid, and Overdue are derived from ledger totals, balance, due date, and business-local date.

Key constraints: `(business, number)` unique; non-null source estimate unique; due date valid; money non-negative; void invoices cannot receive payments.

### `InvoiceLineItem` - Planned

Invoice-specific historical line snapshot with the same financial shape as an estimate line. It never shares persistence with `EstimateLineItem` and does not change when a source catalog/estimate line changes.

### `Payment` - Planned

Authoritative ledger entry belonging directly to Business and one protected Invoice. Stores manual/online source, pending/posted/failed/reversed status, positive amount, currency, paid date, method/reference/note, provider identifiers, optional actor, and posting/reversal timestamps.

Posted payments are immutable. Currency must equal invoice currency; provider payment identifiers are unique when present; child and invoice businesses must match.

### `PaymentReversal` - Planned

Additive correction record belonging to Business and one protected Payment. Stores positive amount, reason, optional unique provider identifier, timestamp, and actor. Aggregate reversals cannot exceed the unreversed posted amount.

Payment rows plus reversals are the source of truth. Invoice paid/balance caches exist for read performance and must reconcile to the ledger.

## Communications and Audit

### `PublicDocumentLink` - Implemented for estimates

Purpose-scoped, revocable access to exactly one Estimate or Invoice. Stores a unique token digest, purpose, optional expiration/revocation, and access data. Viewing, accepting, and paying are separate purposes.

### `FileAsset` - Implemented for estimate PDFs

Metadata for private object storage: optional Business, asset kind, storage key, content type, size, checksum, creator, and timestamp. Used for logos, PDFs, and exports.

### `DocumentSnapshot` - Implemented for estimates

Immutable versioned rendering payload for one issued estimate or invoice, optionally linked to a generated PDF asset. Legitimate revisions create new versions; historical documents are not silently regenerated from current defaults.

### `EmailDelivery` - Implemented for estimates

Tracks recipient, template, optional estimate/invoice/payment, queued/sent/delivered/failed state, provider message ID, timestamps, and failure code.

### `ActivityEvent` - Implemented foundation

Append-only business history supports explicit Contact, ProductService, and Estimate
targets, optional actor, constrained event type, summary, minimal metadata, and occurrence
timestamp. Invoice and Payment targets will be added with their domains.

### `Notification` - Planned

Workspace/user notification optionally scoped to Business, with event type, title/body, internal target path, read timestamp, and creation date.

## Commercial and Integration Models

### `Plan` and `Subscription` - Planned

Plan is configurable data for code, name, active state, prices, currency, limits, and features. Subscription is one-to-one with Workspace and records plan, status, interval, provider identifiers, period end, and cancellation intent.

### `UsageCounter` - Planned, optional

Use only when an authoritative V1 query is too expensive for enforcement. Counters require reconciliation.

### `ConnectedAccount` - Planned

One-to-one payment-provider connection for Business with unique provider account ID, onboarding state, capability flags, and last synchronization time.

### `WebhookEvent` - Planned

Durable provider inbox with unique `(provider, provider_event_id)`, type, mode, payload, signature verification, processing status, attempts, error, and timestamps.

### `OutboxEvent` - Planned

Durable after-commit work record with topic, aggregate identity, optional Business, validated payload, availability/processing timestamps, attempts, and last error.

## Cross-Model Invariants

- Every business-owned child matches its parent's Business.
- Estimate and Invoice are separate models with separate line models.
- One Estimate converts to at most one Invoice.
- Issued document snapshots and posted ledger entries are immutable.
- Visible document numbers are unique per Business, not globally.
- All document/payment currencies agree; no V1 currency conversion.
- Exactly one target is set on a public document link or document snapshot.
- Provider event/payment/account identifiers are unique in their correct scope.
- Financial parents are protected from deletion; corrections use archive, void, or reversal semantics.

See [ARCHITECTURE.md](ARCHITECTURE.md) for transaction/service conventions and [TEST_PLAN.md](TEST_PLAN.md) for invariant coverage.
