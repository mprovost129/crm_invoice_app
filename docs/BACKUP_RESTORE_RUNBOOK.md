# Backup and Restore Runbook

Last reviewed: 2026-08-12

Provider-specific commands cannot be finalized until hosting and storage are selected.
This runbook defines the required evidence and safe sequence; it must be supplemented with
reviewed provider-native commands before launch.

## Required Backup Set

- Managed PostgreSQL automated encrypted backups with approved retention and point-in-time
  recovery where available.
- Private object-storage versioning/retention for PDFs, receipts, and future uploads.
- An inventory of environment-variable names, host configuration, image digest, domains,
  scheduled jobs, webhook destinations, and external provider account identifiers. Secret
  values remain in the provider secret manager and are never copied into a database dump.

## Restore Exercise

1. Create a new isolated restoration environment with no customer email delivery, no live
   Stripe credentials, no live webhooks, and access limited to named operators.
2. Record source backup timestamp, requested recovery point, operator, target image/version,
   start time, and expected RPO/RTO.
3. Restore the database through the managed provider. Restore/version-select private media
   through the storage provider without making the bucket public.
4. Configure fictional/test-only email and Stripe sandbox settings. Keep
   `STRIPE_LIVE_MODE=false`.
5. Apply required forward migrations exactly once with the target artifact.
6. Run:

   ```powershell
   python manage.py check --deploy --settings=config.settings.prod
   python manage.py launch_gate --json
   python manage.py reconciliation_check
   python manage.py outbox_health_check
   python manage.py provider_health_check --json
   python manage.py stripe_billing_reconciliation_check --json
   python manage.py stripe_reconciliation_check --json
   ```

7. Verify representative tenants, contacts, immutable estimate/invoice snapshots, payments,
   reversals, PDFs/receipts, subscriptions, connected-account references, and inbox/outbox
   evidence. Do not process restored outbound work against real recipients/providers.
8. Record finish time, achieved recovery point/time, row/document spot checks, command
   output, gaps, and remediation owners.
9. Securely destroy or retain the restored environment according to the approved privacy
   policy and record completion.

## Failed Restore

Do not label backup protection complete. Preserve provider/job errors without credentials,
escalate as at least SEV-2, determine whether later/earlier restore points are viable, and
repeat after remediation. Backup job success without a demonstrated restore does not pass
the launch gate.

