import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
READINESS_SCRIPT = PROJECT_ROOT / "scripts" / "production_readiness.py"


def run_readiness(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(READINESS_SCRIPT), *args]
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def production_env_without_required_config() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SUNTERRA_")
    }
    env["SUNTERRA_ENV"] = "production"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return env


def production_env_with_required_config(tmp_path: Path) -> dict[str, str]:
    env = production_env_without_required_config()
    env["SUNTERRA_SECRET_KEY"] = "test-secret-for-production-readiness"
    env["SUNTERRA_DATABASE_URL"] = f"sqlite:///{(tmp_path / 'configured.db').as_posix()}"
    env["SUNTERRA_ALLOWED_ORIGINS"] = "https://portal.example.test"
    return env


def test_fresh_database_can_be_migrated(tmp_path: Path) -> None:
    database_path = tmp_path / "fresh-readiness.db"

    result = run_readiness(
        "migrate-fresh",
        "--database-url",
        f"sqlite:///{database_path.as_posix()}",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "check": "migrate-fresh",
        "status": "ok",
        "database_url": "sqlite:///<redacted>",
    }
    assert database_path.exists()

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table'",
            )
        }

    assert "alembic_version" in tables


def test_production_startup_fails_when_required_config_is_missing() -> None:
    code = (
        "from fastapi.testclient import TestClient\n"
        "from sunterra_leg_portal.main import app\n"
        "with TestClient(app) as client:\n"
        "    client.get('/api/health')\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=production_env_without_required_config(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Missing required production configuration" in result.stderr
    assert "SUNTERRA_SECRET_KEY" in result.stderr
    assert "SUNTERRA_DATABASE_URL" in result.stderr
    assert "SUNTERRA_ALLOWED_ORIGINS" in result.stderr


def test_backup_restore_smoke_restores_persisted_test_data(tmp_path: Path) -> None:
    database_path = tmp_path / "source.db"
    backup_path = tmp_path / "backup.db"
    restored_path = tmp_path / "restored.db"
    database_url = f"sqlite:///{database_path.as_posix()}"

    migrate_result = run_readiness("migrate-fresh", "--database-url", database_url)
    assert migrate_result.returncode == 0, migrate_result.stderr

    result = run_readiness(
        "backup-restore",
        "--database-url",
        database_url,
        "--backup-path",
        str(backup_path),
        "--restore-path",
        str(restored_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["check"] == "backup-restore"
    assert payload["status"] == "ok"
    assert payload["database_url"] == "sqlite:///<redacted>"
    assert payload["restored_rows"] == 1

    with sqlite3.connect(restored_path) as connection:
        restored_marker = connection.execute(
            "select marker from production_readiness_smoke where marker = ?",
            (payload["marker"],),
        ).fetchone()

    assert restored_marker == (payload["marker"],)


def test_production_config_check_reports_ready_without_leaking_secret(tmp_path: Path) -> None:
    result = run_readiness(
        "check-production-config",
        env=production_env_with_required_config(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "check": "check-production-config",
        "status": "ok",
        "environment": "production",
    }
    assert "test-secret-for-production-readiness" not in result.stdout
    assert "test-secret-for-production-readiness" not in result.stderr
