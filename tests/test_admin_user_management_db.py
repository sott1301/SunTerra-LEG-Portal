import base64
from datetime import UTC, datetime
import hmac
from hashlib import sha1
import sqlite3
from pathlib import Path
import struct
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from sunterra_leg_portal import auth
from sunterra_leg_portal import main as portal
from sunterra_leg_portal.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def totp_code(secret: str, timestamp: datetime | None = None) -> str:
    now = timestamp or datetime.now(UTC)
    counter = int(now.timestamp()) // 30
    key = base64.b32decode(secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def migrate_database(database_url: str) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def clear_runtime_state() -> None:
    for store in [
        portal.INVITATIONS,
        portal.COMMUNICATION_EVENTS,
        portal.USER_ACCOUNTS,
        portal.PARTICIPANTS,
        portal.IDENTITY_VERIFICATIONS,
        portal.DOCUMENT_VERSIONS,
        portal.CONSENT_EVIDENCE,
        portal.MUTATION_REQUESTS,
        portal.PARTICIPANT_AUDIT_EVENTS,
        portal.FILE_EVIDENCE,
        portal.MUTATION_PACKAGES,
        portal.MUTATION_PACKAGE_METADATA,
        portal.PACKAGED_MUTATION_REQUEST_IDS,
        auth.DEV_PARTICIPANT_USERS,
    ]:
        store.clear()


def delete_legacy_snapshot(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("delete from portal_state_snapshots")


def legacy_snapshot_count(database_path: Path) -> int:
    with sqlite3.connect(database_path) as connection:
        return int(
            connection.execute("select count(*) from portal_state_snapshots").fetchone()[0],
        )


def platform_admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": "platform-admin@example.test", "password": "SunTerra123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def leg_admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": "leg-admin@example.test", "password": "SunTerra123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_platform_admin_user_management_survives_async_db_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "admin-users.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    platform = platform_admin_token(first_client)
    email = f"persistent-admin-{uuid4().hex}@example.test"
    created_response = first_client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": email,
            "display_name": "Persistent LEG Admin",
            "role": "leg_admin",
            "password": "Start123!",
        },
    )
    assert created_response.status_code == 201
    account = created_response.json()

    updated_response = first_client.patch(
        f"/api/admin/users/{account['id']}",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "display_name": "Persistent Platform Admin",
            "role": "platform_admin",
            "active": False,
        },
    )
    assert updated_response.status_code == 200

    reactivated_response = first_client.patch(
        f"/api/admin/users/{account['id']}",
        headers={"Authorization": f"Bearer {platform}"},
        json={"active": True},
    )
    assert reactivated_response.status_code == 200

    reset_response = first_client.post(
        f"/api/admin/users/{account['id']}/reset-password",
        headers={"Authorization": f"Bearer {platform}"},
        json={"password": "ChangedStart123!"},
    )
    assert reset_response.status_code == 200

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    old_password_response = second_client.post(
        "/api/auth/login",
        json={"email": email, "password": "Start123!"},
    )
    login_response = second_client.post(
        "/api/auth/login",
        json={"email": email, "password": "ChangedStart123!"},
    )

    assert old_password_response.status_code == 401
    assert login_response.status_code == 200
    login = login_response.json()
    assert login["user"]["display_name"] == "Persistent Platform Admin"
    assert login["user"]["role"] == "platform_admin"
    assert login["user"]["mfa_satisfied"] is False

    listed_response = second_client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert listed_response.status_code == 403

    enrollment_response = second_client.post(
        "/api/auth/mfa/totp/enroll",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert enrollment_response.status_code == 201
    mfa_login_response = second_client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "ChangedStart123!",
            "totp_code": totp_code(enrollment_response.json()["secret"]),
        },
    )
    assert mfa_login_response.status_code == 200
    listed_response = second_client.get(
        "/api/admin/users",
        headers={
            "Authorization": f"Bearer {mfa_login_response.json()['access_token']}",
        },
    )
    assert listed_response.status_code == 200
    assert [
        user
        for user in listed_response.json()
        if user["id"] == account["id"]
    ] == [
        {
            "id": account["id"],
            "email": email,
            "display_name": "Persistent Platform Admin",
            "role": "platform_admin",
            "active": True,
            "organization": None,
        },
    ]


def test_auth_login_uses_async_user_account_table_when_legacy_snapshot_is_unreadable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "auth-without-legacy-snapshot.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    platform = platform_admin_token(first_client)
    email = f"legacy-free-login-{uuid4().hex}@example.test"
    created_response = first_client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": email,
            "display_name": "Legacy Free Login",
            "role": "leg_admin",
            "password": "Start123!",
        },
    )
    assert created_response.status_code == 201

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            insert into portal_state_snapshots (id, payload_json)
            values ('default', '{not valid json')
            on conflict(id) do update set payload_json = excluded.payload_json
            """,
        )
    clear_runtime_state()
    second_client = TestClient(app, raise_server_exceptions=False)

    login_response = second_client.post(
        "/api/auth/login",
        json={"email": email, "password": "Start123!"},
    )

    assert login_response.status_code == 200
    assert login_response.json()["user"] == {
        "id": created_response.json()["id"],
        "email": email,
        "display_name": "Legacy Free Login",
        "role": "leg_admin",
        "mfa_satisfied": False,
    }


def test_admin_user_management_writes_async_database_without_legacy_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "admin-users-no-legacy-snapshot.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    platform = platform_admin_token(first_client)
    email = f"no-legacy-admin-{uuid4().hex}@example.test"
    created_response = first_client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": email,
            "display_name": "No Legacy Snapshot Admin",
            "role": "leg_admin",
            "password": "Start123!",
        },
    )

    assert created_response.status_code == 201
    assert legacy_snapshot_count(database_path) == 0

    clear_runtime_state()
    second_client = TestClient(app)
    login_response = second_client.post(
        "/api/auth/login",
        json={"email": email, "password": "Start123!"},
    )

    assert login_response.status_code == 200
    assert login_response.json()["user"]["display_name"] == "No Legacy Snapshot Admin"


def test_platform_admin_cannot_promote_user_to_partner_admin_in_async_db(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "admin-role-boundary.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    platform = platform_admin_token(first_client)
    email = f"not-partner-admin-{uuid4().hex}@example.test"
    created_response = first_client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": email,
            "display_name": "Not Partner Admin",
            "role": "leg_admin",
            "password": "Start123!",
        },
    )
    assert created_response.status_code == 201
    account = created_response.json()

    forbidden_response = first_client.patch(
        f"/api/admin/users/{account['id']}",
        headers={"Authorization": f"Bearer {platform}"},
        json={"role": "partner_admin"},
    )
    assert forbidden_response.status_code == 400

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)
    login_response = second_client.post(
        "/api/auth/login",
        json={"email": email, "password": "Start123!"},
    )

    assert login_response.status_code == 200
    assert login_response.json()["user"]["role"] == "leg_admin"


def test_leg_admin_partner_admin_creation_survives_async_db_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "partner-admin-users.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    leg_admin = leg_admin_token(first_client)
    email = f"persistent-partner-admin-{uuid4().hex}@example.test"
    created_response = first_client.post(
        "/api/admin/partner-admin-users",
        headers={"Authorization": f"Bearer {leg_admin}"},
        json={
            "email": email,
            "display_name": "Persistent Partner Admin",
            "organization": "Gemeinde/EW Basadingen",
            "password": "Start123!",
        },
    )

    assert created_response.status_code == 201
    assert created_response.json()["role"] == "partner_admin"
    assert created_response.json()["organization"] == "Gemeinde/EW Basadingen"

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    partner_login_response = second_client.post(
        "/api/auth/login",
        json={"email": email, "password": "Start123!"},
    )
    assert partner_login_response.status_code == 200
    assert partner_login_response.json()["user"]["role"] == "partner_admin"

    platform = platform_admin_token(second_client)
    publish_response = second_client.post(
        "/api/admin/document-versions",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "document_key": "platform_role_boundary",
            "title": "Platform Boundary",
            "version": "2042-01",
            "content": "Platform admins do not publish documents.",
            "context": "participant_onboarding",
        },
    )
    assert publish_response.status_code == 403


def test_duplicate_email_and_invalid_admin_role_stay_rejected_on_async_db_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "admin-rejections.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    platform = platform_admin_token(first_client)
    email = f"duplicate-admin-{uuid4().hex}@example.test"
    created_response = first_client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": email,
            "display_name": "Duplicate Source",
            "role": "leg_admin",
            "password": "Start123!",
        },
    )
    assert created_response.status_code == 201

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)
    platform = platform_admin_token(second_client)
    leg_admin = leg_admin_token(second_client)

    duplicate_internal_response = second_client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": email,
            "display_name": "Duplicate Internal",
            "role": "platform_admin",
            "password": "Start123!",
        },
    )
    duplicate_partner_response = second_client.post(
        "/api/admin/partner-admin-users",
        headers={"Authorization": f"Bearer {leg_admin}"},
        json={
            "email": email,
            "display_name": "Duplicate Partner",
            "organization": "Gemeinde/EW Basadingen",
            "password": "Start123!",
        },
    )
    invalid_role_response = second_client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": f"invalid-role-{uuid4().hex}@example.test",
            "display_name": "Invalid Role",
            "role": "partner_admin",
            "password": "Start123!",
        },
    )

    assert duplicate_internal_response.status_code == 409
    assert duplicate_partner_response.status_code == 409
    assert invalid_role_response.status_code == 400
