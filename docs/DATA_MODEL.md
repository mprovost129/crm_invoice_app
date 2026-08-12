# Data Model

Last reviewed: 2026-08-12

## Status Legend

- **Implemented:** model exists in repository code.
- **Planned:** approved V1 model, not yet implemented.
- **Post-V1:** extension point intentionally not exposed in V1.

The repository includes migrations through Phase 5 for `users`, `workspaces`, `core`,
`crm`, `catalog`, `activity`, `estimates`, `invoices`, `payments`, and `communications`
with Django 5.2.16 against PostgreSQL 16.

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
Estimate/Invoice ---- 1 DocumentSnapshot
Estimate/Invoice/Payment ----< FileAsset (PDF/receipt)
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

### `Invoice` - Implemented

Belongs to Business and protected Contact; optionally has a unique one-to-one source Estimate. Stores visible number, workflow state, currency/dates, contact and billing snapshots, line/tax/discount totals, cached amount paid/balance, deposit requirement, notes/terms, delivery/view/void timestamps, reason, and creator.

Editable workflow values are Draft, Sent, Viewed, and Void. Partial, Paid, and Overdue are derived from ledger totals, balance, due date, and business-local date.

Key constraints: `(business, number)` unique; source Estimate one-to-one; due date valid;
money non-negative and internally balanced; issue and void state/timestamps consistent.
Payment and void service rules add row locking and ledger-aware validation.

### `InvoiceLineItem` - Implemented

Invoice-specific historical line snapshot with the same financial shape as an estimate line. It never shares persistence with `EstimateLineItem` and does not change when a source catalog/estimate line changes.

### `Payment` - Implemented

Authoritative immutable posted ledger entry belonging directly to Business and one
protected Invoice. Stores manual/online source, positive amount, currency, paid date,
method/reference/note, optional provider identifier and actor, posting timestamp, and
immutable invoice-total/balance-after snapshots. Reversed status is derived from additive
reversal totals.

Posted payments are immutable. Currency must equal invoice currency; provider payment identifiers are unique when present; child and invoice businesses must match.

### `PaymentReversal` - Implemented

Additive immutable correction record belonging to Business and one protected Payment.
Stores positive amount, required reason, timestamp, and actor. The reversal service locks
the payment and invoice and prevents aggregate reversals exceeding the posted amount.

Payment rows plus reversals are the source of truth. Invoice paid/balance caches exist for read performance and must reconcile to the ledger.

## Communications and Audit

### `PublicDocumentLink` - Implemented for estimates and invoices

Purpose-scoped, revocable access to exactly one Estimate or Invoice. Stores only a unique
token digest plus purpose, expiration/revocation, and access data. Estimate view/respond
and invoice view links are separate; raw tokens are never persisted.

### `FileAsset` - Implemented for document PDFs and payment receipts

Tenant-owned metadata for exactly one Estimate, Invoice, or Payment asset: kind, storage
key, content type, byte size, checksum, and optional matching document snapshot. Invoice
PDFs are cached by immutable snapshot plus current payment-state render key.

### `DocumentSnapshot` - Implemented for estimates and invoices

Immutable versioned rendering payload for one issued estimate or invoice, optionally linked to a generated PDF asset. Legitimate revisions create new versions; historical documents are not silently regenerated from current defaults.

### `EmailDelivery` - Implemented for estimates, invoices, reminders, and receipts

Tracks exactly one estimate/invoice/payment target, delivery kind, recipient, subject,
queued/sent/failed state, timestamps, and sanitized failure information.

### `ActivityEvent` - Implemented foundation

Append-only business history supports explicit Contact, ProductService, Estimate,
Invoice, or Payment targets, optional actor, constrained event type, summary, minimal
metadata, and occurrence timestamp.

### `Notification` - Implemented

Tenant-owned owner notification with a workspace-member recipient, constrained kind,
title/body, internal target path, read timestamp, and business-scoped dedupe key. Current
kinds cover estimate acceptance/decline, recorded payment, overdue invoice, and delivery
failure. Event services create immediate notifications; an idempotent command synchronizes
date-derived overdue notifications.

## Commercial and Integration Models

### `Plan` and `Subscription` - Planned

Plan is configurable data for code, name, active state, prices, currency, limits, and features. Subscription is one-to-one with Workspace and records plan, status, interval, provider identifiers, period end, and cancellation intent.

### `UsageCounter` - Planned, optional

Use only when an authoritative V1 query is too expensive for enforcement. Counters require reconciliation.

### `ConnectedAccount` - Planned

One-to-one payment-provider connection for Business with unique provider account ID, onboarding state, capability flags, and last synchronization time.

### `WebhookEvent` - Planned

Durable provider inbox with unique `(provider, provider_event_id)`, type, mode, payload, signature verification, processing status, attempts, error, and timestamps.

### `OutboxEvent` - Implemented

Durable after-commit work record with event type, required Business, unique dedupe key,
validated payload, availability/processing timestamps, attempts, status, and last error.
It currently drives estimate/invoice/reminder/receipt email delivery and command-based
retry.

## Cross-Model Invariants

- Every business-owned child matches its parent's Business.
- Estimate and Invoice are separate models with separate line models.
- One Estimate converts to at most one Invoice.
- Issued document snapshots and posted ledger entries are immutable.
- Visible document numbers are unique per Business, not globally.
- All document/payment currencies agree; no V1 currency conversion.
- Exactly one type-aligned target is set on public links, snapshots, files, deliveries,
  and activity events.
- Provider event/payment/account identifiers are unique in their correct scope.
- Financial parents are protected from deletion; corrections use archive, void, or reversal semantics.

See [ARCHITECTURE.md](ARCHITECTURE.md) for transaction/service conventions and [TEST_PLAN.md](TEST_PLAN.md) for invariant coverage.
