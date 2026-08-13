# Launch Checklist

Last reviewed: 2026-08-12

This checklist is a release gate, not evidence that production is ready. Every required
item needs an owner, date, environment, and durable evidence link before real customer
data or money is accepted.

## Current Blockers

- Hosting, managed PostgreSQL, Redis, worker/scheduler, private object storage,
  transactional email, monitoring, and backup providers are not selected.
- Final product/legal identity, domain, support channel, Terms, Privacy Notice, retention
  schedule, subprocessors, and incident contacts are not approved.
- Stripe is intentionally sandbox-only. Final pricing, Price IDs, webhook registration,
  Connect platform settings, liability choices, and live credentials are not approved.
- No production-like browser, accessibility, responsive, email/PDF, backup/restore, or
  Stripe end-to-end evidence has been recorded.

## Repository Gate

Run against the exact release artifact:

```powershell
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
pytest
python manage.py check --deploy --settings=config.settings.prod
python manage.py launch_gate --json --fail-on-warning --require-stripe
python manage.py outbox_health_check
python manage.py provider_health_check --json
python manage.py reconciliation_check
python manage.py stripe_billing_reconciliation_check --json --provider
python manage.py stripe_reconciliation_check --json --provider
```

CI must also scan pinned Python dependencies and the built image for known
vulnerabilities. Any exception needs a written risk owner and expiry date.

## Infrastructure and Configuration

- [ ] Immutable image is identified by commit and digest.
- [ ] Production settings use a unique secret, HTTPS domain, strict hosts/origins, secure
  proxy configuration, Redis cache, non-console email, and private persistent storage.
- [ ] Web and supervised worker/scheduler use the same artifact and environment version.
- [ ] The worker frequently runs outbox and both webhook inbox processors.
- [ ] Scheduled health/reconciliation commands alert on nonzero exit.
- [ ] Central logs preserve request IDs and redact public tokens, passwords, Stripe keys,
  signing secrets, and signature headers.
- [ ] Error monitoring, uptime, latency, database, worker, email, storage, outbox, webhook,
  and reconciliation alerts reach a tested on-call channel.
- [ ] Environment secrets are stored in the host secret manager, never in Git, images,
  logs, tickets, chat, screenshots, or database dumps.

## Stripe Sandbox Before Live Mode

- [ ] Use only `sk_test_`, `pk_test_`, sandbox Price IDs, and sandbox endpoint secrets.
- [ ] Set `STRIPE_LIVE_MODE=false`.
- [ ] Configure separate platform and connected-account event destinations.
- [ ] Test new/updated/canceled subscriptions and past-due entitlement fallback.
- [ ] Complete Express onboarding for at least two fictional businesses.
- [ ] Test successful, failed, expired, duplicated, delayed, and wrong-account events.
- [ ] Prove an open Checkout blocks manual posting and that expiry restores it.
- [ ] Prove one successful charge creates exactly one online ledger entry and receipt.
- [ ] Run both reconciliation commands with `--provider` and retain clean output.

Live-mode activation is a separate change. Never replace test keys in a local `.env` with
live keys. Add live secrets only to the selected production host, set
`STRIPE_LIVE_MODE=true`, use live Price IDs/endpoints, and execute a controlled low-value
production validation with documented refund/support handling.

## Data Protection and Recovery

- [ ] Approved data inventory, lawful-purpose statement, Privacy Notice, retention
  schedule, deletion/closure process, subprocessor list, and customer request workflow.
- [ ] Automated encrypted database backups and object-storage versioning/retention.
- [ ] Alerts for backup failure/staleness.
- [ ] Restore rehearsal follows [BACKUP_RESTORE_RUNBOOK.md](BACKUP_RESTORE_RUNBOOK.md) and
  meets approved RPO/RTO.
- [ ] Representative documents and payment evidence survive restore.
- [ ] Restored sensitive data is access-controlled and removed after the exercise.

## Customer Experience and Operations

- [ ] Keyboard, screen-reader, focus, contrast, zoom, and reduced-motion review.
- [ ] Responsive review at common phone, tablet, laptop, and large-screen sizes.
- [ ] Customer estimate/invoice/payment links, error states, PDFs, and email clients pass
  professional review using fictional data.
- [ ] Terms, Privacy, Support, account export, and closure flows are approved and reachable.
- [ ] Support ownership, severity matrix, communication templates, incident process, and
  provider escalation paths are rehearsed.
- [ ] Production-like lead-to-paid and subscription end-to-end smoke tests pass.

## Release and Rollback

- [ ] Representative migration rehearsal records duration and locks.
- [ ] Current backup and restore evidence are within policy.
- [ ] Rollout order covers release migration, web, worker, and scheduled jobs.
- [ ] Backward compatibility and application rollback/forward-fix path are documented.
- [ ] Named operator observes health, logs, queues, webhooks, and reconciliation throughout
  the release window.
- [ ] Release result and follow-ups are recorded in CHANGELOG and the incident tracker.

