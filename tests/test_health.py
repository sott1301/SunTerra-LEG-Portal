from pathlib import Path
import sqlite3

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def migrate_database(database_url: str) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def test_health_endpoint_describes_running_portal() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "sunterra-leg-portal",
        "version": "0.1.0",
    }


def test_readiness_endpoint_proves_async_runtime_database_query_after_migration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "runtime-readiness.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("SUNTERRA_DATABASE_URL", database_url)
    migrate_database(database_url)

    response = TestClient(app).get("/api/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "sunterra-leg-portal",
        "version": "0.1.0",
        "database": {
            "status": "ok",
            "query_result": 1,
        },
    }


def test_health_endpoint_does_not_load_legacy_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "health-no-legacy-snapshot.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("SUNTERRA_DATABASE_URL", database_url)
    migrate_database(database_url)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            insert into portal_state_snapshots (id, payload_json)
            values ('default', '{not valid json')
            """,
        )

    response = TestClient(app, raise_server_exceptions=False).get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unmatched_api_route_does_not_load_legacy_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "unknown-api-no-legacy-snapshot.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("SUNTERRA_DATABASE_URL", database_url)
    migrate_database(database_url)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            insert into portal_state_snapshots (id, payload_json)
            values ('default', '{not valid json')
            """,
        )

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/not-a-real-route",
    )

    assert response.status_code == 404
