# Project Overview

Last reviewed: 2026-08-12

## Product

This project is a simple, invoice-centric CRM and invoicing SaaS for independent service providers, freelancers, contractors, and small service businesses. It is designed around one practical business lifecycle:

> Lead -> Estimate -> Acceptance -> Invoice -> Deposit or partial payment -> Final payment -> Paid

The product exists to let an owner enter customer information once and carry it through estimating, invoicing, payment collection, and follow-up without learning accounting software or repeatedly entering the same data.

It should be simpler than traditional accounting products and more operationally useful than a basic invoice generator. It is explicitly not a general-ledger, tax-filing, payroll, inventory, or ERP system.

## Problem Being Solved

Small service businesses commonly manage leads, estimates, invoices, and payments across disconnected tools. That creates duplicated entry, inconsistent customer records, stale totals, weak follow-up, and poor visibility into outstanding cash.

This product combines the minimum CRM and financial-document capabilities needed to:

- Maintain a single lead/client record.
- Reuse products and services while allowing custom work.
- Produce professional estimates and invoices.
- Preserve the history of issued documents.
- Support deposits, partial payments, final payments, and reversals.
- Derive accurate balances and overdue states.
- Surface work needing attention.
- Give owners portable exports of their core business data.

## Primary User

The V1 user is an independent service provider who operates one business, works alone or with a very small team, sells services rather than inventory, prepares estimates, collects deposits, performs work, invoices customers, and collects final payment.

Representative users include contractors, painters, landscapers, designers, photographers, consultants, developers, handymen, cleaners, tutors, and other home or professional service providers.

## V1 Product Promise

An owner should be able to register, configure one business, add a lead once, create and deliver an estimate, record acceptance, convert it to an invoice without re-entry, collect a deposit and partial payments, identify overdue balances, send a reminder or receipt, review the complete client history, and export core data.

The experience should be understandable without accounting knowledge. Features that do not improve or protect this workflow remain outside the initial release.

## Product Principles

- **Workflow first:** prioritize the complete lead-to-paid path over breadth.
- **One source of truth:** backend services own business and financial rules.
- **Historical accuracy:** issued documents retain snapshots and do not change with later edits to contacts, catalog items, or defaults.
- **Financial integrity:** payments are ledger records; posted records are reversed or voided rather than silently edited or deleted.
- **Tenant safety:** every business-owned record is scoped to a verified business context.
- **Practical flexibility:** online acceptance is optional, and owners may record acceptance or payment received through other channels.
- **Portability and trust:** exports, audit-conscious lifecycle rules, tested backups, and reconciliation are launch requirements.
- **Progressive complexity:** responsive web first; automation, broader APIs, multiple users/businesses, and mobile later.

## Commercial Direction

The approved scope proposes a useful Free tier and a Starter tier as the normal plan for an operating service business. The exact client limits, prices, annual discounts, Premium timing, and additional-business pricing are hypotheses, not hard-coded product rules. Plan definitions and entitlements must be configurable.

Online payment architecture has two independent commercial relationships:

1. SaaS subscription billing, where the application customer pays the platform.
2. Invoice payment processing, where that customer's client pays the customer's business.

These flows must not share financial records or business logic.

## Current Repository State

The repository has completed the identity, tenant, CRM, and catalog foundation, but is
not yet a working invoicing V1.

Implemented today:

- Django project configuration for development and production.
- PostgreSQL configuration and local Docker services for PostgreSQL and Redis.
- Email-first UUID custom user model and manager.
- UUID one-to-one account-owner profile, explicitly separate from CRM contacts/businesses.
- Committed initial user/account-profile migration.
- Django login, logout, and password-reset routes/templates.
- Public registration and email verification.
- Atomic owner Workspace/Membership creation during registration.
- Business onboarding, editable defaults, and document-sequence initialization.
- Active workspace/business request context and tenant-scoped query helpers.
- An authenticated tenant-safe empty dashboard.
- Tenant-safe Contact records with Lead, Client, and Archived lifecycle states.
- Contact search, filtering, profile, durable notes, and append-only activity history.
- Reusable products/services with units, rates, tax defaults, search, filters, and archive/restore behavior.
- Customer-centric staff admin.
- Shared timestamp base model.
- Separate liveness/readiness endpoints and request correlation IDs.
- Self-hosted, checksum-verified HTMX 2.0.10 foundation.
- Baseline production security, static-file, cache, logging, and email configuration.
- Non-root multi-stage production container and health-checked Compose services.
- GitHub Actions quality gate and reproducible Docker setup instructions.
- Fifty-two passing PostgreSQL-backed tests through Phase 2.

Not yet implemented:

- Estimates, invoices, calculations, document snapshots, and PDFs.
- Payments, reminders, notifications, exports, and reporting.
- Subscription billing, Stripe Connect, webhooks, background work, and reconciliation.
- The V1 end-to-end workflow.

See [FEATURES.md](FEATURES.md) and [ROADMAP.md](ROADMAP.md) for status and sequencing.

## Success Definition

V1 is commercially usable only when the decisive end-to-end workflow is fast, accurate, secure, understandable, tenant-isolated, retry-safe, and proven in a production-like environment. A collection of disconnected CRUD screens does not satisfy that definition.

## Source Documents

- [V1 Product Scope](<CRM + Invoicing SaaS — V1 Product Scope.docx>)
- [Django Data Model & Architecture](<CRM + Invoicing SaaS — Django Data Model & Architecture.docx>)
- [MVP Build Plan & Acceptance Criteria](<CRM + Invoicing SaaS — MVP Build Plan & Acceptance Criteria.docx>)
