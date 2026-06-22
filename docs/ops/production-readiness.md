# Production Readiness Checks

Issue #17 adds the first smoke checks that a developer or deployment agent can
run before managed operation. The checks are intentionally service-light: local
tests use SQLite, while deployment pipelines can pass a production-equivalent
database URL when the required driver and service are available.

## Required Production Configuration

The application starts normally in local development. When `SUNTERRA_ENV` is set
to `production`, startup fails unless these variables are present:

- `SUNTERRA_SECRET_KEY`
- `SUNTERRA_DATABASE_URL`
- `SUNTERRA_ALLOWED_ORIGINS`

Run the explicit config check:

```powershell
.\.venv\Scripts\python scripts\production_readiness.py check-production-config
```

The command returns JSON on success and does not print secret values.

## Fresh Migration Smoke

Run Alembic against an empty test database:

```powershell
.\.venv\Scripts\python scripts\production_readiness.py migrate-fresh --database-url sqlite:///./tmp/readiness.db
```

For a deployment pipeline, pass the managed test or staging database URL instead
of the SQLite URL. Do not run this against a production database that already
contains live data.

## Backup/Restore Smoke

The backup/restore smoke is a file-backed SQLite test. It writes a smoke marker,
backs up the database, restores it into a new file, and verifies that the marker
is present in the restored database.

```powershell
.\.venv\Scripts\python scripts\production_readiness.py backup-restore --database-url sqlite:///./tmp/readiness.db --backup-path ./tmp/readiness-backup.db --restore-path ./tmp/readiness-restored.db
```

This check demonstrates the restore path without depending on production
services. A managed PostgreSQL deployment should use provider-native backup
tooling or `pg_dump`/`pg_restore` in addition to this local smoke.

## Verification Flow

The production-readiness tests are part of the normal Python test suite:

```powershell
.\.venv\Scripts\python -m pytest
```

To run only these checks:

```powershell
.\.venv\Scripts\python -m pytest tests/test_production_readiness.py
```
