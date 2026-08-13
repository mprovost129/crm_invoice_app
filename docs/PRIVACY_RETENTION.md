# Privacy and Retention Decision Register

Last reviewed: 2026-08-12

This is an engineering decision register, not a Privacy Notice or legal advice. Product
pages and automated deletion must not be launched until qualified review approves the
items below for the actual company, jurisdictions, subprocessors, and business practices.

## Data Inventory

The application currently stores account identity/authentication data; business profile
and settings; CRM contact/address/notes; estimate/invoice/payment evidence; activity,
notification, email-delivery and outbox metadata; digest-only public-link tokens;
subscription and connected-account identifiers/status; and verified Stripe webhook event
payloads. It does not intentionally store full card numbers, CVCs, bank credentials, or
plaintext public-link tokens.

## Decisions Required Before Real Customer Data

- Legal entity/controller/contact and jurisdictions served.
- Purposes and lawful bases for account, CRM, communication, financial, fraud/security,
  support, analytics, and provider data.
- Approved subprocessors and cross-border transfer terms.
- Retention periods for prospects, customers, issued documents, financial evidence,
  activities, emails, public links, webhook payloads, logs, backups, support cases, and
  closed accounts.
- Customer/user access, correction, export, objection/restriction, and deletion procedures,
  including identity verification and financial/legal retention exceptions.
- Cookie/session disclosure and whether non-essential analytics will exist.
- Incident/breach notification decision process and contacts.

## Engineering Constraints

- Hard deletion remains prohibited for issued documents and immutable financial/provider
  evidence unless an approved retention policy explicitly authorizes it.
- Account closure must first address active subscriptions, connected payments, outstanding
  invoices, export, legal holds, and retained financial evidence.
- Public links are revocable and expiring; logs must redact their raw tokens.
- Backups need bounded retention and a documented way to age deleted data out safely.
- Provider payload retention should be minimized after determining the fields required for
  idempotency, support, reconciliation, and legal evidence.
- New data fields/providers require an inventory and notice/retention review.

