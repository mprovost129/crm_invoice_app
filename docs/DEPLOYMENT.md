# Deployment

Last reviewed: 2026-08-12

## Current Deployment State

The repository provides a portable Docker/Gunicorn foundation, a committed GitHub Actions
quality gate, configurable email/storage adapters, and a durable estimate-email outbox.
It does not identify an active hosting platform or production environment and has no
deployment automation, independently deployed worker/scheduler, cloud object-storage
package, monitoring provider, backup automation, or documented production deployment.

Treat the procedures below as the required operating model, not evidence that those controls already exist.

## Environments

### Local Development

Current Compose services:

- `web`: Django development server on port 8000 with source mounted and `config.settings.dev`.
- `db`: PostgreSQL 16 with a named `postgres_data` volume and host port 5432.
- `redis`: Redis 7 on host port 6379.

Local configuration comes from `.env`, based on `.env.example`. Never commit `.env`.

### Test / CI

The committed GitHub Actions workflow provides:

- Isolated PostgreSQL database.
- Production-like Python/Django dependency set.
- Ruff/format checks, migration drift/application, PostgreSQL pytest suite, and Django production deploy checks.
- No real customer information or production provider credentials.
- Deterministic fictional fixtures.

Dependency/image vulnerability scanning remains a required follow-up for the deployment pipeline.

### Staging

Required before launch:

- Production-like app, worker, PostgreSQL, Redis, object storage, email, and monitoring.
- Isolated test-mode Stripe Billing and Connect accounts/credentials.
- Independent database/storage/secrets from production.
- Safe test domain and non-production email delivery controls.
- Migration rehearsal and end-to-end smoke environment.

### Production

Required services at the relevant product phase:

- Containerized Django/Gunicorn web service.
- Managed PostgreSQL with automated backups and point-in-time recovery if available.
- Redis or comparable broker/cache.
- Separate background worker process when outbox/email/PDF/webhook work is introduced.
- Private persistent object storage for logos, PDFs, and exports.
- Transactional email provider.
- Stripe Billing and Stripe Connect when commercial integrations launch.
- Centralized structured logs, error monitoring, metrics, uptime checks, and alerting.

Web and workers should scale independently and use the same application image/config version.

## Current Runtime Artifacts

- `Dockerfile`: multi-stage Python 3.13 slim build, pinned wheel installation, non-root runtime user, build-time `collectstatic`, container health check, and two Gunicorn workers bound to port 8000.
- `Procfile`: Gunicorn `web` process and `release` migration command.
- `config.settings.prod`: secure HTTPS/cookies/HSTS, WhiteNoise static files, Redis cache, persistent database connections, strict hosts/origins, and optional trusted reverse-proxy header.
- `config.wsgi` and `config.asgi`: default to production settings.

## Configuration and Secrets

Required application/database settings:

- `SECRET_KEY`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `DB_HOST`, `DB_PORT`
- `APP_NAME`, `SITE_URL`, `SUPPORT_EMAIL`
- `LANGUAGE_CODE`, `TIME_ZONE`, `MEDIA_URL`

Production/security settings:

- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `REDIS_URL`
- `DJANGO_LOG_LEVEL`
- `TRUST_X_FORWARDED_PROTO` only behind a correctly configured trusted proxy
- `MEDIA_STORAGE_BACKEND` plus provider-specific credentials/configuration
- `PUBLIC_DOCUMENT_LINK_TTL_DAYS`, `PUBLIC_DOCUMENT_VIEW_LIMIT`
- Upload memory limits when defaults are unsuitable

Email settings:

- `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL`, `EMAIL_TIMEOUT`, `PASSWORD_RESET_TIMEOUT`

Future provider credentials, webhook secrets, signing keys, storage credentials, and monitoring DSNs must be platform-managed secrets with environment isolation and rotation procedures. Do not log or expose plaintext secrets.

## Deployment Preconditions

Before any production release:

1. CI passes formatting/linting, migration drift, tests, and security checks.
2. Deployment artifact is immutable and identified by version/commit/digest.
3. Release notes list schema/config/provider changes and operator actions.
4. Database backup is current and restore capability is within its tested window.
5. Migration is rehearsed against representative production-like data.
6. Migration lock/duration and backward compatibility are understood.
7. New required configuration exists in the target environment.
8. Web/worker/provider compatibility and rollout order are documented.
9. A rollback or forward-fix plan is named for application and data changes.

## Standard Deployment Procedure

1. Build the container once from the reviewed dependency lock.
2. Run static checks, full relevant tests, migration drift check, and image/security scan.
3. Deploy the exact artifact to staging.
4. Apply migrations in staging and run the production-like smoke suite.
5. Confirm health, logs, metrics, worker/outbox, storage, email, and enabled provider test paths.
6. Create/verify the production pre-deploy backup.
7. Apply production migrations using one controlled release job.
8. Roll out web processes; roll out workers in the compatibility order documented for the change.
9. Confirm `/health/`, application authentication, tenant context, critical reads/writes, static/media access, and enabled integrations.
10. Watch error rate, latency, database locks/connections, outbox/webhook/email failures, and reconciliation signals during the release window.
11. Record the result and any follow-up in [CHANGELOG.md](CHANGELOG.md).

Do not run migrations independently from every web replica. The current Procfile `release` command is suitable only if the hosting platform guarantees a single controlled release process.

## Migration Strategy

- Commit migrations with the model/service change; never generate production migrations at deploy time.
- Prefer small, independently reviewable migration groups in dependency order: users; tenancy; CRM/catalog; shared financial infrastructure; estimates; invoices/payments; communications; commercial integrations.
- Use expand-and-contract for zero/low-downtime changes:
  1. Add nullable/new structures and deploy compatible code.
  2. Backfill in bounded resumable batches outside long transactions.
  3. Switch reads/writes and verify.
  4. Add constraints or remove legacy structures in a later release.
- Avoid table rewrites, unbounded data migrations, external network calls, and long locks in schema migrations.
- Make data migrations deterministic, observable, and safe to retry.
- Measure migration duration/locking with representative data.
- Keep web and worker versions compatible during rolling deployment.

Migrations through Phase 3 are generated and apply cleanly in dependency order. Phase 3
adds Estimate/EstimateLineItem/EstimateAcceptance, estimate-targeted activity, and the
communications snapshot/link/file/delivery/outbox models. Activity and communications use
split migrations to avoid circular dependencies. Back up existing data before applying
migrations outside development.

## Static Files and Media

Static files are collected into the image and served through WhiteNoise compressed-manifest storage.

Local media uses filesystem storage. Production on ephemeral hosts must install/configure a persistent private storage backend before accepting uploads or generating customer documents. Use signed short-lived access, content type/size validation, checksums, retention rules, and lifecycle cleanup. Public object buckets are not acceptable for financial documents.

## Background Work and Webhooks

The estimate email path creates a durable outbox row in the domain transaction, invokes
processing after commit for immediate local behavior, and exposes
`python manage.py process_outbox --limit N` for pending/failed retries. Production must run
that command through a supervised worker/scheduler until a dedicated queue consumer is
introduced.

For background processing:

- Run workers as separate processes using the same release artifact.
- Create outbox rows in the domain transaction and process after commit.
- Use bounded retries, exponential backoff, idempotency keys, dead/stuck job visibility, and alerts.
- Verify webhook signatures against raw bodies and store unique provider events before asynchronous processing.
- Drain or safely stop workers during incompatible deployments.
- Do not deploy code that publishes a new job schema before available workers can consume it safely.

## Backups and Restore

### Required Backup Policy

- Automated encrypted PostgreSQL backups with documented retention.
- Point-in-time recovery where supported and justified.
- Backup monitoring that alerts on failure or staleness.
- Object-storage versioning/retention appropriate for issued documents and exports.
- Secrets/configuration inventory sufficient to rebuild the service, stored separately from the database backup.

### Restore Exercise

On a scheduled cadence and before launch:

1. Restore a selected backup into an isolated environment.
2. Record backup timestamp, restore duration, recovery point, and operator.
3. Apply any required forward migrations using the target application version.
4. Run database integrity, tenant-isolation spot checks, financial reconciliation, and application smoke tests.
5. Confirm representative private documents/assets can be retrieved.
6. Destroy or protect the restored copy according to privacy policy.
7. Record evidence and remediation; a configured backup without a proven restore is not launch-ready.

Recovery point and time objectives must be set before real customer data based on business impact, provider capabilities, and cost.

## Rollback and Recovery Guidance

### Application-Only Failure

If the schema and job formats remain backward compatible, route traffic back to the last known-good immutable image and restore the compatible worker version. Confirm health and critical workflows.

### Schema Change Failure

Prefer a forward fix. Reverse a migration only when its reverse operation is proven safe and no incompatible writes occurred. Never blindly roll back a destructive or lossy data migration.

For expand-and-contract releases, keep old columns/paths until the new version is verified; this makes application rollback possible without data loss.

### Corrupt or Incorrect Business Data

Stop the faulty writer, preserve evidence, identify affected tenant/records, and use an audited corrective migration/service or provider reconciliation. Do not silently edit/delete issued documents, payments, reversals, or provider events. Restore the entire database only when scoped correction is unsafe and the business accepts the recovery-point data loss.

### Provider/Worker Failure

Disable or isolate the affected integration, keep domain state/outbox/provider events durable, and replay idempotently after correction. Manual payment workflows must remain independent of online provider availability.

### Incident Record

Record timeline, scope, customer/financial impact, recovery actions, reconciliation evidence, and preventive follow-up. Rotate compromised credentials immediately and follow notification obligations defined by the privacy/incident policy.

## Post-Deploy Verification

At minimum verify:

- `/health/` succeeds and database readiness is real.
- Static assets load and private media access is authorized.
- Login/logout/reset and secure cookies/HTTPS behave correctly.
- Tenant context resolves and foreign-tenant access is denied.
- A safe representative create/read/update flow works for enabled domains.
- Worker processes consume outbox work without duplicates or backlog growth.
- Email and enabled provider webhooks/payment test paths behave correctly.
- Dashboard/export totals reconcile where applicable.
- Logs include request IDs without secrets or sensitive payloads.
- Error/latency/database/worker/provider dashboards remain within expected bounds.

## Operations Ownership Still Required

Before production, name the hosting provider, deployment owner, database/backup owner, security/incident owner, support escalation, monitoring/on-call path, email/storage/payment providers, RPO/RTO, maintenance window policy, and rollback authority. The software configuration alone does not supply these operational responsibilities.
