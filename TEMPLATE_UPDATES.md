# Django starter template updates

## Customer-centric admin

- Admin home now starts with a prominent customer search.
- Account metrics show total, active, inactive, and staff users.
- `User` is the primary support/customer record.
- Customer profile details are editable inline from the user page.
- The user page automatically discovers reverse relations from project models that point to `settings.AUTH_USER_MODEL` and links to the related admin records.
- Raw profile administration remains available as an advanced screen.
- Admin CSS is isolated under `static/admin/customer_admin.css`.

## Custom user model fixes

- Kept the existing email-first `AbstractBaseUser` design.
- Added explicit admin creation/change forms so Django's stock auth forms do not assume a `username` field.
- Hardened `create_superuser` validation.
- Added `use_in_migrations = True` to the custom manager.
- Added a `display_name` property and customer-friendly string representation.
- Added an account-owner profile for broadly reusable non-auth metadata. Phase 0 later renamed it `AccountProfile` before the first migration to distinguish it from CRM contacts and tenant businesses.
- Added tests covering `AUTH_USER_MODEL`, email login model behavior, password hashing, superuser flags, profile relationship, and the customer-search admin landing page.
- Added `users/README.md` with the required relationship pattern: use `settings.AUTH_USER_MODEL` in model fields and `get_user_model()` at runtime. Avoid `user.user` chains.

## Starter hygiene

- Added `.gitignore` and `.env.example`.
- Removed macOS metadata, logs, and committed bytecode from the distributed copy.
- Fixed Docker `collectstatic` so a clean image build does not depend on runtime secrets being available during the image build.

## Before using this as a new project

Run the normal first-project database setup after dependencies and environment variables are configured:

```bash
python manage.py makemigrations users
python manage.py migrate
python manage.py createsuperuser
pytest
```

The source template supplied for this update did not contain a `users/migrations/` package. Phase 0 subsequently finalized UUID identifiers and generated the first migration from the completed User/AccountProfile model state.

## Universal foundation upgrades (v2)

- Updated Django from 6.0.3 to 6.0.8. The August 4, 2026 patch includes security fixes, including a high-severity issue; starter templates should begin on the latest supported patch release.

Phase 0 superseded this short-lived baseline with Django 5.2.16 LTS. The project prioritizes the LTS security-support window through April 2028 while retaining Python 3.13 support.

These additions are deliberately cross-project rather than SaaS/app-specific.

- Added environment-driven `APP_NAME`, `SITE_URL`, `SUPPORT_EMAIL`, `LANGUAGE_CODE`, and `TIME_ZONE` so shared templates do not need product-specific edits.
- Reworked `base.html` with dynamic language, reusable SEO/robots/social/icon/head/body blocks, Bootstrap layout partials, and accessible Django messages.
- Added reusable navigation/footer/message partials.
- Added generic 400/403/404/500 templates.
- Added `TimeStampedModel` as an **optional abstract base class** for the common `created_at`/`updated_at` pattern. It is not forced on project models.
- Added `/health/` readiness endpoint that checks the primary database for deployment monitoring.
- Added request/correlation IDs (`X-Request-ID`) to make production logs and support reports easier to trace.
- Added generic upload-memory limits that can be overridden by environment variables. These are application-level guards; production web/proxy body-size limits should still be configured.
- Added email timeout and `SERVER_EMAIL` settings.
- Added safer production parsing for `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
- Added `SECURE_CONTENT_TYPE_NOSNIFF`, referrer policy, SameSite defaults, and optional trusted reverse-proxy HTTPS handling.
- Made the production media storage backend environment-configurable. Local filesystem remains the zero-dependency default; production projects on ephemeral disks should install/configure a persistent cloud storage backend.
- Added Ruff pre-commit hooks because `pre-commit` was already included as a dependency but had no configuration.
- Added core tests for health checking and request IDs.

### Intentionally not included globally

Subscriptions/billing, organizations/tenancy, projects/tasks, APIs/DRF, Celery/background queues, WebSockets, soft deletion, UUID primary keys, audit-history packages, cloud-storage packages, and frontend frameworks remain optional. They are common in *some* apps but would make the base template opinionated or add unused infrastructure to many projects.
