# CRM and Invoicing SaaS

A Django/PostgreSQL application for the service-business workflow from lead through
estimate, acceptance, invoice, and payment. The repository is currently completing its
foundation phase; see [Project Overview](docs/PROJECT_OVERVIEW.md),
[Roadmap](docs/ROADMAP.md), and [Features](docs/FEATURES.md).

## Prerequisites

- Docker Desktop with Docker Compose v2.
- Git for normal source-control workflows.

Python 3.13 can also be used directly, but Docker Compose is the canonical setup because
development and tests must use PostgreSQL rather than SQLite.

## First-Time Setup

1. Copy `.env.example` to `.env`.
2. Replace `SECRET_KEY` and `DB_PASSWORD` with local-only values.
3. Start the database and cache:

   ```powershell
   docker compose up -d db redis
   ```

4. Build the application and apply migrations:

   ```powershell
   docker compose build web
   docker compose run --rm web python manage.py migrate
   ```

5. Start the application:

   ```powershell
   docker compose up -d web
   ```

6. Open `http://localhost:8000/`. Readiness is available at
   `http://localhost:8000/health/ready/`.

Create a local staff account when needed:

```powershell
docker compose exec web python manage.py createsuperuser
```

## Quality Gate

Run the same checks used by continuous integration:

```powershell
docker compose run --rm web ruff check .
docker compose run --rm web ruff format --check .
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web pytest
```

To validate the production settings locally, provide non-placeholder production values:

```powershell
docker compose run --rm `
  -e DJANGO_SETTINGS_MODULE=config.settings.prod `
  -e SECRET_KEY=local-deploy-check-only-secret-key-with-at-least-fifty-characters `
  -e ALLOWED_HOSTS=example.com `
  -e CSRF_TRUSTED_ORIGINS=https://example.com `
  web python manage.py check --deploy
```

## Common Commands

```powershell
# View service state and logs
docker compose ps
docker compose logs -f web

# Apply committed migrations
docker compose run --rm web python manage.py migrate

# Confirm database/application readiness
Invoke-RestMethod http://localhost:8000/health/ready/

# Stop services without deleting the database volume
docker compose down
```

Do not remove the `postgres_data` volume unless you deliberately intend to delete the
local database.

## Configuration

`.env.example` documents the supported environment variables. Development loads `.env`;
production secrets must come from the hosting platform or secret manager. Never commit
`.env`, provider credentials, private keys, customer exports, or database dumps.

The application fails fast when `SECRET_KEY`, `DB_NAME`, `DB_USER`, or `DB_PASSWORD` is
missing. Production additionally requires non-empty `ALLOWED_HOSTS` and a unique
non-placeholder `SECRET_KEY` of at least 50 characters.

## Architecture and Delivery

- [Architecture](docs/ARCHITECTURE.md)
- [Data Model](docs/DATA_MODEL.md)
- [Product Scope](docs/PRODUCT_SCOPE.md)
- [Test Plan](docs/TEST_PLAN.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Decisions](docs/DECISIONS.md)
- [Changelog](docs/CHANGELOG.md)
