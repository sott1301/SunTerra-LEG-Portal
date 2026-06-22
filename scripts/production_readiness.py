from __future__ import annotations

import argparse
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
    except (ReadinessError, ProductionConfigurationError) as error:
        print(str(error), file=sys.stderr)
        return 2

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
