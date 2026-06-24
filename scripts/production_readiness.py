from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from alembic import command
from alembic.config import Config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sunterra_leg_portal.config import (  # noqa: E402
    ProductionConfigurationError,
    assert_production_configured,
)


def redacted_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return "sqlite:///<redacted>"
    scheme, separator, _rest = database_url.partition("://")
    if separator:
        return f"{scheme}://<redacted>"
    return "<redacted>"


def alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def run_migrations(database_url: str) -> dict[str, Any]:
    previous_database_url = os.environ.get("SUNTERRA_DATABASE_URL")
    os.environ["SUNTERRA_DATABASE_URL"] = database_url
    try:
        command.upgrade(alembic_config(database_url), "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("SUNTERRA_DATABASE_URL", None)
        else:
            os.environ["SUNTERRA_DATABASE_URL"] = previous_database_url

    return {
        "check": "migrate-fresh",
        "status": "ok",
        "database_url": redacted_database_url(database_url),
    }


class ReadinessError(RuntimeError):
    pass


def sqlite_database_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ReadinessError(
            "backup-restore currently supports sqlite test databases only",
        )

    path_text = database_url.removeprefix(prefix)
    if not path_text or path_text == ":memory:":
        raise ReadinessError("backup-restore requires a file-backed sqlite database")

    return Path(path_text)


def reject_existing_file(path: Path) -> None:
    if path.exists():
        raise ReadinessError(f"Refusing to overwrite existing file: {path}")


def run_backup_restore(
    database_url: str,
    backup_path: Path,
    restore_path: Path,
) -> dict[str, Any]:
    source_path = sqlite_database_path(database_url)
    reject_existing_file(backup_path)
    reject_existing_file(restore_path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    restore_path.parent.mkdir(parents=True, exist_ok=True)

    marker = uuid4().hex

    with sqlite3.connect(source_path) as source_connection:
        source_connection.execute(
            "create table if not exists production_readiness_smoke "
            "(marker text primary key)",
        )
        source_connection.execute(
            "insert into production_readiness_smoke (marker) values (?)",
            (marker,),
        )
        source_connection.commit()

        with sqlite3.connect(backup_path) as backup_connection:
            source_connection.backup(backup_connection)

    with sqlite3.connect(backup_path) as backup_connection:
        with sqlite3.connect(restore_path) as restore_connection:
            backup_connection.backup(restore_connection)

    with sqlite3.connect(restore_path) as restored_connection:
        restored_rows = restored_connection.execute(
            "select count(*) from production_readiness_smoke where marker = ?",
            (marker,),
        ).fetchone()[0]

    if restored_rows != 1:
        raise ReadinessError("Restored database did not contain the smoke marker")

    return {
        "check": "backup-restore",
        "status": "ok",
        "database_url": redacted_database_url(database_url),
        "marker": marker,
        "restored_rows": restored_rows,
    }


def run_config_check() -> dict[str, Any]:
    assert_production_configured()
    return {
        "check": "check-production-config",
        "status": "ok",
        "environment": os.environ.get("SUNTERRA_ENV", "development"),
    }


def sqlite_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=30)
    connection.execute("pragma busy_timeout = 30000")
    return connection


def run_scaling_gates(
    database_url: str,
    *,
    registered_users: int,
    active_users: int,
) -> dict[str, Any]:
    if registered_users < 1:
        raise ReadinessError("registered-users must be at least 1")
    if active_users < 1 or active_users > registered_users:
        raise ReadinessError("active-users must be between 1 and registered-users")

    run_migrations(database_url)
    database_path = sqlite_database_path(database_url)

    with sqlite_connection(database_path) as connection:
        connection.execute(
            """
            insert into portal_document_versions (
                id, document_key, title, version, document_hash, context,
                published_at, content
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "scaling-consent-doc",
                "portal_terms_scaling_gate",
                "Scaling Gate Terms",
                "2040-01",
                "scaling-gate-document-hash",
                "participant_onboarding",
                "2040-01-01T00:00:00+00:00",
                "Scaling gate consent terms.",
            ),
        )
        for index in range(registered_users):
            participant_id = f"scale-participant-{index:04d}"
            email = f"scale-participant-{index:04d}@example.test"
            display_name = f"Scale Participant {index:04d}"
            connection.execute(
                """
                insert into portal_participants (
                    id, email, display_name, leg_id, email_verified,
                    phone_number, preferred_contact_channel
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    participant_id,
                    email,
                    display_name,
                    "basadingen",
                    1,
                    None,
                    "email",
                ),
            )
            connection.execute(
                """
                insert into portal_user_accounts (
                    id, email, display_name, role, active, organization,
                    password_hash, password_salt
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    participant_id,
                    email,
                    display_name,
                    "participant",
                    1,
                    None,
                    "initial-password-hash",
                    "initial-password-salt",
                ),
            )
            connection.execute(
                """
                insert into portal_identity_verifications (
                    participant_id, email, display_name, leg_id, source,
                    required_level, current_level, satisfied, verified_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    participant_id,
                    email,
                    display_name,
                    "basadingen",
                    "scaling_gate",
                    "account_setup",
                    "email_verified",
                    0,
                    "2040-01-01T00:00:00+00:00",
                ),
            )

    active_indexes = list(range(active_users))

    def write_account_setup(index: int) -> None:
        participant_id = f"scale-participant-{index:04d}"
        display_name = f"Active Scale Participant {index:04d}"
        with sqlite_connection(database_path) as connection:
            connection.execute(
                "update portal_participants set display_name = ? where id = ?",
                (display_name, participant_id),
            )
            connection.execute(
                """
                update portal_user_accounts
                set display_name = ?, password_hash = ?, password_salt = ?
                where id = ?
                """,
                (
                    display_name,
                    f"setup-password-hash-{index:04d}",
                    f"setup-password-salt-{index:04d}",
                    participant_id,
                ),
            )
            connection.execute(
                """
                update portal_identity_verifications
                set current_level = ?, satisfied = ?
                where participant_id = ?
                """,
                ("account_setup", 1, participant_id),
            )

    def write_consent(index: int) -> None:
        participant_id = f"scale-participant-{index:04d}"
        with sqlite_connection(database_path) as connection:
            connection.execute(
                """
                insert into portal_consent_evidence (
                    participant_id, document_version_id, accepted_at,
                    document_key, version, document_hash, context
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    participant_id,
                    "scaling-consent-doc",
                    f"2040-01-01T00:00:{index:02d}+00:00",
                    "portal_terms_scaling_gate",
                    "2040-01",
                    "scaling-gate-document-hash",
                    "participant_onboarding",
                ),
            )

    def write_mutation(index: int) -> None:
        participant_id = f"scale-participant-{index:04d}"
        mutation_id = f"scale-mutation-{index:04d}"
        payload = {
            "id": mutation_id,
            "participant_id": participant_id,
            "leg_id": "basadingen",
            "mutation_type": "address",
            "mode": "regular",
            "status": "approved",
            "submitted_at": f"2040-01-01T00:01:{index:02d}+00:00",
            "requested_quarter": "2040-Q1",
            "quarter": "2040-Q1",
            "submitted_on": "2040-01-01",
            "effective_date": "2040-04-01",
            "reviewed_at": f"2040-01-01T00:02:{index:02d}+00:00",
            "reviewed_by": "scaling-gate",
            "new_address": {
                "street": f"Scale Street {index}",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        }
        with sqlite_connection(database_path) as connection:
            connection.execute(
                """
                insert into portal_mutation_requests (
                    id, participant_id, leg_id, status, submitted_at, payload_json
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (
                    mutation_id,
                    participant_id,
                    "basadingen",
                    "approved",
                    payload["submitted_at"],
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                ),
            )

    with ThreadPoolExecutor(max_workers=min(16, active_users)) as executor:
        list(executor.map(write_account_setup, active_indexes))
        list(executor.map(write_consent, active_indexes))
        list(executor.map(write_mutation, active_indexes))

    mutation_ids = [f"scale-mutation-{index:04d}" for index in active_indexes]

    def try_generate_package(package_id: str) -> bool:
        package_payload = {
            "package_id": package_id,
            "leg_id": "basadingen",
            "quarter": "2040-Q1",
            "effective_date": "2040-04-01",
            "generated_at": "2040-01-01T00:03:00+00:00",
            "records": mutation_ids,
        }
        metadata_payload = {
            "package_id": package_id,
            "current_status": "created",
            "status_history": [
                {
                    "status": "created",
                    "actor_role": "leg_admin",
                    "created_at": "2040-01-01T00:03:00+00:00",
                    "reference": None,
                    "reason": None,
                },
            ],
        }
        try:
            with sqlite_connection(database_path) as connection:
                connection.execute(
                    """
                    insert into portal_mutation_packages (
                        package_id, leg_id, quarter, generated_at, payload_json
                    ) values (?, ?, ?, ?, ?)
                    """,
                    (
                        package_id,
                        "basadingen",
                        "2040-Q1",
                        "2040-01-01T00:03:00+00:00",
                        json.dumps(
                            package_payload,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    ),
                )
                connection.execute(
                    """
                    insert into portal_mutation_package_metadata (
                        package_id, current_status, payload_json
                    ) values (?, ?, ?)
                    """,
                    (
                        package_id,
                        "created",
                        json.dumps(
                            metadata_payload,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    ),
                )
                for mutation_id in mutation_ids:
                    connection.execute(
                        """
                        insert into portal_packaged_mutation_requests (
                            mutation_request_id, package_id
                        ) values (?, ?)
                        """,
                        (mutation_id, package_id),
                    )
            return True
        except sqlite3.IntegrityError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        package_results = list(
            executor.map(
                try_generate_package,
                ["scale-package-primary", "scale-package-racing"],
            ),
        )

    if package_results.count(True) != 1:
        raise ReadinessError("package-generation gate did not serialize duplicates")

    with sqlite_connection(database_path) as connection:
        legacy_snapshot_rows = connection.execute(
            "select count(*) from portal_state_snapshots",
        ).fetchone()[0]
        packaged_mutation_requests = connection.execute(
            "select count(*) from portal_packaged_mutation_requests",
        ).fetchone()[0]

    if legacy_snapshot_rows != 0:
        raise ReadinessError("scaling gates wrote legacy portal state snapshots")
    if packaged_mutation_requests != active_users:
        raise ReadinessError("package-generation gate packaged the wrong row count")

    return {
        "active_users": active_users,
        "check": "scaling-gates",
        "concurrency_gates": [
            "registration-account-setup",
            "consent",
            "mutation-submission",
            "package-generation",
        ],
        "database_url": redacted_database_url(database_url),
        "legacy_snapshot_rows": legacy_snapshot_rows,
        "packaged_mutation_requests": packaged_mutation_requests,
        "registered_users": registered_users,
        "status": "ok",
    }


def write_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run production-readiness smoke checks for the SunTerra LEG Portal.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate_fresh = subparsers.add_parser(
        "migrate-fresh",
        help="Migrate an empty database to the current schema.",
    )
    migrate_fresh.add_argument("--database-url", required=True)

    backup_restore = subparsers.add_parser(
        "backup-restore",
        help="Back up and restore a test database, then verify persisted smoke data.",
    )
    backup_restore.add_argument("--database-url", required=True)
    backup_restore.add_argument("--backup-path", required=True, type=Path)
    backup_restore.add_argument("--restore-path", required=True, type=Path)

    subparsers.add_parser(
        "check-production-config",
        help="Validate required production configuration without printing secrets.",
    )

    scaling_gates = subparsers.add_parser(
        "scaling-gates",
        help="Run DB scaling and concurrent-write gates for registered users.",
    )
    scaling_gates.add_argument("--database-url", required=True)
    scaling_gates.add_argument("--registered-users", type=int, default=1000)
    scaling_gates.add_argument("--active-users", type=int, default=100)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "migrate-fresh":
            write_json(run_migrations(args.database_url))
            return 0

        if args.command == "backup-restore":
            write_json(
                run_backup_restore(
                    args.database_url,
                    args.backup_path,
                    args.restore_path,
                ),
            )
            return 0

        if args.command == "check-production-config":
            write_json(run_config_check())
            return 0

        if args.command == "scaling-gates":
            write_json(
                run_scaling_gates(
                    args.database_url,
                    registered_users=args.registered_users,
                    active_users=args.active_users,
                ),
            )
            return 0
    except (ReadinessError, ProductionConfigurationError) as error:
        print(str(error), file=sys.stderr)
        return 2

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
