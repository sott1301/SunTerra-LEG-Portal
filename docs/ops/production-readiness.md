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

`SUNTERRA_DATABASE_URL` uses SQLAlchemy/SQLModel URL syntax. Local smoke checks
can use file-backed SQLite URLs such as `sqlite:///./tmp/readiness.db`; staging
or production-like checks can point at a Postgres-compatible URL such as
`postgresql+psycopg://user:password@host:5432/database` when the runtime includes
the matching database driver.

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

The smoke verifies that the schema contains Alembic's version table, the legacy
snapshot compatibility table, and the DB runtime persistence tables for users,
participants, documents, consent evidence, mutation requests, mutation packages,
file evidence, and communication events. Productive API requests use the direct
runtime tables; the snapshot table is retained only as an explicit compatibility
artifact.

## Legacy snapshot compatibility

Legacy snapshot compatibility is not part of the productive request path. The
full portal-state reload/save middleware is bypassed for `/api/*` routes, and
direct table-backed handlers persist Auth, Public, Participant, Admin, and
Partner workflows to the DB runtime persistence tables. A legacy snapshot path
can be enabled only for non-production compatibility or fallback work by setting
`SUNTERRA_ENABLE_LEGACY_PORTAL_STATE=1`.

## Scaling and Concurrency Gates

Run the scaling smoke against a migrated disposable database:

```powershell
.\.venv\Scripts\python scripts\production_readiness.py scaling-gates --database-url sqlite:///./tmp/scaling-gates.db --registered-users 1000 --active-users 100
```

The default gate covers 1000 registered users and 100 active users. It performs
representative concurrent writes for registration/account setup, consent,
mutation submission, and package generation, then verifies that package
generation serializes duplicate packaging attempts through the DB constraints.
The gate also asserts that no legacy snapshot rows are written.

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
