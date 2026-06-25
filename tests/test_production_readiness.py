import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
READINESS_SCRIPT = PROJECT_ROOT / "scripts" / "production_readiness.py"
MERMAID_MAP = PROJECT_ROOT / "docs" / "portal-mermaid-map.md"
READINESS_DOCS = PROJECT_ROOT / "docs" / "ops" / "production-readiness.md"
CONTEXT_DOC = PROJECT_ROOT / "CONTEXT.md"
ADR_DIR = PROJECT_ROOT / "docs" / "adr"
PORTAL_PRD = PROJECT_ROOT / "docs" / "prds" / "sunterra-leg-member-mutation-portal-prd.md"
PORTAL_PLAN = PROJECT_ROOT / "docs" / "plans" / "sunterra-leg-member-mutation-portal.md"
README = PROJECT_ROOT / "README.md"


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
    env["SUNTERRA_SMTP_HOST"] = "smtp.example.test"
    env["SUNTERRA_SMTP_PORT"] = "587"
    env["SUNTERRA_SMTP_FROM_EMAIL"] = "noreply@portal.example.test"
    env["SUNTERRA_PUBLIC_BASE_URL"] = "https://portal.example.test"
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
    assert "portal_state_snapshots" in tables
    assert "portal_participants" in tables
    assert "portal_network_topology_entries" in tables
    assert "portal_participant_invitations" in tables
    assert "portal_identity_verifications" in tables
    assert "portal_document_versions" in tables
    assert "portal_consent_evidence" in tables
    assert "portal_mutation_requests" in tables
    assert "portal_participant_audit_events" in tables
    assert "portal_mutation_packages" in tables
    assert "portal_mutation_package_metadata" in tables
    assert "portal_packaged_mutation_requests" in tables
    assert "portal_file_evidence" in tables
    assert "portal_user_accounts" in tables
    assert "portal_password_reset_tokens" in tables
    assert "portal_communication_events" in tables


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
    assert "SUNTERRA_SMTP_HOST" in result.stderr
    assert "SUNTERRA_SMTP_PORT" in result.stderr
    assert "SUNTERRA_SMTP_FROM_EMAIL" in result.stderr
    assert "SUNTERRA_PUBLIC_BASE_URL" in result.stderr


def test_production_rejects_development_bearer_tokens(tmp_path: Path) -> None:
    database_path = tmp_path / "production-auth.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    migrate_result = run_readiness("migrate-fresh", "--database-url", database_url)
    assert migrate_result.returncode == 0, migrate_result.stderr
    env = production_env_with_required_config(tmp_path)
    env["SUNTERRA_DATABASE_URL"] = database_url
    code = (
        "import json\n"
        "from fastapi.testclient import TestClient\n"
        "from sunterra_leg_portal.main import app\n"
        "with TestClient(app) as client:\n"
        "    response = client.get(\n"
        "        '/api/me',\n"
        "        headers={'Authorization': 'Bearer dev:platform_admin'},\n"
        "    )\n"
        "    print(json.dumps({'status_code': response.status_code, 'body': response.json()}))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "status_code": 401,
        "body": {
            "detail": "Development authentication is disabled in production",
        },
    }


def test_production_cors_uses_configured_allowed_origins(tmp_path: Path) -> None:
    code = (
        "import json\n"
        "from fastapi.testclient import TestClient\n"
        "from sunterra_leg_portal.main import app\n"
        "with TestClient(app) as client:\n"
        "    configured = client.options(\n"
        "        '/api/health',\n"
        "        headers={\n"
        "            'Origin': 'https://portal.example.test',\n"
        "            'Access-Control-Request-Method': 'GET',\n"
        "        },\n"
        "    )\n"
        "    local = client.options(\n"
        "        '/api/health',\n"
        "        headers={\n"
        "            'Origin': 'http://127.0.0.1:5173',\n"
        "            'Access-Control-Request-Method': 'GET',\n"
        "        },\n"
        "    )\n"
        "    print(json.dumps({\n"
        "        'configured_status': configured.status_code,\n"
        "        'configured_origin': configured.headers.get('access-control-allow-origin'),\n"
        "        'local_status': local.status_code,\n"
        "        'local_origin': local.headers.get('access-control-allow-origin'),\n"
        "    }))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=production_env_with_required_config(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "configured_status": 200,
        "configured_origin": "https://portal.example.test",
        "local_status": 400,
        "local_origin": None,
    }


def test_bootstrap_cli_creates_first_production_platform_admin(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "bootstrap-admin.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    migrate_result = run_readiness("migrate-fresh", "--database-url", database_url)
    assert migrate_result.returncode == 0, migrate_result.stderr
    env = production_env_with_required_config(tmp_path)
    env["SUNTERRA_DATABASE_URL"] = database_url
    password = "Bootstrap123!"
    env["SUNTERRA_BOOTSTRAP_ADMIN_PASSWORD"] = password

    bootstrap_command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "bootstrap_admin.py"),
        "--email",
        "first-admin@example.test",
        "--display-name",
        "First Production Admin",
        "--role",
        "platform_admin",
    ]
    bootstrap = subprocess.run(
        bootstrap_command,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert password not in bootstrap_command
    assert bootstrap.returncode == 0, bootstrap.stderr
    bootstrap_payload = json.loads(bootstrap.stdout)
    assert bootstrap_payload["status"] == "created"
    assert bootstrap_payload["email"] == "first-admin@example.test"
    assert bootstrap_payload["role"] == "platform_admin"
    assert password not in bootstrap.stdout
    assert password not in bootstrap.stderr

    code = (
        "import json\n"
        "from datetime import UTC, datetime\n"
        "from fastapi.testclient import TestClient\n"
        "from sunterra_leg_portal.main import app, _totp_code\n"
        "with TestClient(app) as client:\n"
        "    response = client.post(\n"
        "        '/api/auth/login',\n"
        "        json={\n"
        "            'email': 'first-admin@example.test',\n"
        "            'password': 'Bootstrap123!',\n"
        "        },\n"
        "    )\n"
        "    body = response.json()\n"
        "    denied_events = client.get(\n"
        "        '/api/admin/communication-events?recipient_email=first-admin@example.test',\n"
        "        headers={'Authorization': f\"Bearer {body['access_token']}\"},\n"
        "    )\n"
        "    enrollment = client.post(\n"
        "        '/api/auth/mfa/totp/enroll',\n"
        "        headers={'Authorization': f\"Bearer {body['access_token']}\"},\n"
        "    )\n"
        "    mfa_login = client.post(\n"
        "        '/api/auth/login',\n"
        "        json={\n"
        "            'email': 'first-admin@example.test',\n"
        "            'password': 'Bootstrap123!',\n"
        "            'totp_code': _totp_code(enrollment.json()['secret'], datetime.now(UTC)),\n"
        "        },\n"
        "    )\n"
        "    mfa_body = mfa_login.json()\n"
        "    events = client.get(\n"
        "        '/api/admin/communication-events?recipient_email=first-admin@example.test',\n"
        "        headers={'Authorization': f\"Bearer {mfa_body['access_token']}\"},\n"
        "    )\n"
        "    print(json.dumps({\n"
        "        'status_code': response.status_code,\n"
        "        'body': body,\n"
        "        'denied_events_status_code': denied_events.status_code,\n"
        "        'enrollment_status_code': enrollment.status_code,\n"
        "        'mfa_login_status_code': mfa_login.status_code,\n"
        "        'mfa_body': mfa_body,\n"
        "        'events_status_code': events.status_code,\n"
        "        'events_body': events.json(),\n"
        "    }))\n"
    )
    login = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert login.returncode == 0, login.stderr
    login_payload = json.loads(login.stdout)
    assert login_payload["status_code"] == 200
    assert login_payload["body"]["user"] == {
        "id": bootstrap_payload["id"],
        "email": "first-admin@example.test",
        "display_name": "First Production Admin",
        "role": "platform_admin",
        "mfa_satisfied": False,
    }
    assert login_payload["denied_events_status_code"] == 403
    assert login_payload["enrollment_status_code"] == 201
    assert login_payload["mfa_login_status_code"] == 200
    assert login_payload["mfa_body"]["user"] == {
        "id": bootstrap_payload["id"],
        "email": "first-admin@example.test",
        "display_name": "First Production Admin",
        "role": "platform_admin",
        "mfa_satisfied": True,
    }
    assert login_payload["events_status_code"] == 200
    assert login_payload["events_body"] == [
        {
            "id": bootstrap_payload["audit_event_id"],
            "channel": "admin_bootstrap",
            "event_type": "bootstrap_admin_created",
            "recipient_email": "first-admin@example.test",
            "status": "created",
            "created_at": bootstrap_payload["created_at"],
        },
    ]


def test_production_does_not_seed_default_demo_admin_accounts(tmp_path: Path) -> None:
    database_path = tmp_path / "no-default-admins.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    migrate_result = run_readiness("migrate-fresh", "--database-url", database_url)
    assert migrate_result.returncode == 0, migrate_result.stderr
    env = production_env_with_required_config(tmp_path)
    env["SUNTERRA_DATABASE_URL"] = database_url
    code = (
        "import json\n"
        "from fastapi.testclient import TestClient\n"
        "from sunterra_leg_portal.main import app\n"
        "with TestClient(app) as client:\n"
        "    response = client.post(\n"
        "        '/api/auth/login',\n"
        "        json={\n"
        "            'email': 'platform-admin@example.test',\n"
        "            'password': 'SunTerra123!',\n"
        "        },\n"
        "    )\n"
        "    print(json.dumps({'status_code': response.status_code, 'body': response.json()}))\n"
    )

    login = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert login.returncode == 0, login.stderr
    assert json.loads(login.stdout) == {
        "status_code": 401,
        "body": {"detail": "Invalid login credentials"},
    }


def test_production_invitation_acceptance_returns_usable_jwt(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "production-invitation-token.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    migrate_result = run_readiness("migrate-fresh", "--database-url", database_url)
    assert migrate_result.returncode == 0, migrate_result.stderr
    env = production_env_with_required_config(tmp_path)
    env["SUNTERRA_DATABASE_URL"] = database_url
    env["SUNTERRA_BOOTSTRAP_ADMIN_PASSWORD"] = "Bootstrap123!"

    bootstrap = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "bootstrap_admin.py"),
            "--email",
            "first-admin@example.test",
            "--display-name",
            "First Production Admin",
            "--role",
            "platform_admin",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr

    code = (
        "import json\n"
        "from datetime import UTC, datetime\n"
        "from fastapi.testclient import TestClient\n"
        "from sunterra_leg_portal.main import app, _totp_code\n"
        "import smtplib\n"
        "class FakeSmtp:\n"
        "    def __init__(self, host, port, timeout):\n"
        "        self.host = host\n"
        "        self.port = port\n"
        "        self.timeout = timeout\n"
        "    def __enter__(self):\n"
        "        return self\n"
        "    def __exit__(self, exc_type, exc, traceback):\n"
        "        return False\n"
        "    def send_message(self, message):\n"
        "        return None\n"
        "smtplib.SMTP = FakeSmtp\n"
        "with TestClient(app) as client:\n"
        "    admin_login = client.post(\n"
        "        '/api/auth/login',\n"
        "        json={\n"
        "            'email': 'first-admin@example.test',\n"
        "            'password': 'Bootstrap123!',\n"
        "        },\n"
        "    )\n"
        "    enrollment = client.post(\n"
        "        '/api/auth/mfa/totp/enroll',\n"
        "        headers={'Authorization': f\"Bearer {admin_login.json()['access_token']}\"},\n"
        "    )\n"
        "    admin_mfa_login = client.post(\n"
        "        '/api/auth/login',\n"
        "        json={\n"
        "            'email': 'first-admin@example.test',\n"
        "            'password': 'Bootstrap123!',\n"
        "            'totp_code': _totp_code(enrollment.json()['secret'], datetime.now(UTC)),\n"
        "        },\n"
        "    )\n"
        "    admin_token = admin_mfa_login.json()['access_token']\n"
        "    invitation = client.post(\n"
        "        '/api/admin/participant-invitations',\n"
        "        headers={'Authorization': f'Bearer {admin_token}'},\n"
        "        json={\n"
        "            'email': 'production-invited@example.test',\n"
        "            'display_name': 'Production Invited',\n"
        "        },\n"
        "    )\n"
        "    accepted = client.post(\n"
        "        f\"/api/auth/invitations/{invitation.json()['token']}/accept\",\n"
        "    )\n"
        "    accepted_body = accepted.json()\n"
        "    me = client.get(\n"
        "        '/api/me',\n"
        "        headers={'Authorization': f\"Bearer {accepted_body['access_token']}\"},\n"
        "    )\n"
        "    print(json.dumps({\n"
        "        'admin_login_status_code': admin_login.status_code,\n"
        "        'enrollment_status_code': enrollment.status_code,\n"
        "        'admin_mfa_login_status_code': admin_mfa_login.status_code,\n"
        "        'invitation_status_code': invitation.status_code,\n"
        "        'accept_status_code': accepted.status_code,\n"
        "        'access_token': accepted_body['access_token'],\n"
        "        'participant_id': accepted_body['participant_id'],\n"
        "        'me_status_code': me.status_code,\n"
        "        'me_body': me.json(),\n"
        "    }))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["admin_login_status_code"] == 200
    assert payload["enrollment_status_code"] == 201
    assert payload["admin_mfa_login_status_code"] == 200
    assert payload["invitation_status_code"] == 201
    assert payload["accept_status_code"] == 200
    assert not payload["access_token"].startswith("dev:")
    assert payload["me_status_code"] == 200
    assert payload["me_body"] == {
        "id": payload["participant_id"],
        "email": "production-invited@example.test",
        "display_name": "Production Invited",
        "role": "participant",
        "mfa_satisfied": False,
    }


def test_bootstrap_cli_refuses_after_first_internal_admin_exists(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "bootstrap-once.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    migrate_result = run_readiness("migrate-fresh", "--database-url", database_url)
    assert migrate_result.returncode == 0, migrate_result.stderr
    env = production_env_with_required_config(tmp_path)
    env["SUNTERRA_DATABASE_URL"] = database_url
    env["SUNTERRA_BOOTSTRAP_ADMIN_PASSWORD"] = "Bootstrap123!"

    first = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "bootstrap_admin.py"),
            "--email",
            "first-admin@example.test",
            "--display-name",
            "First Production Admin",
            "--role",
            "platform_admin",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr

    env["SUNTERRA_BOOTSTRAP_ADMIN_PASSWORD"] = "Bootstrap456!"
    second = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "bootstrap_admin.py"),
            "--email",
            "second-admin@example.test",
            "--display-name",
            "Second Production Admin",
            "--role",
            "leg_admin",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert second.returncode == 1
    assert "Bootstrap admin already exists" in second.stderr
    assert "Bootstrap456!" not in second.stderr


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


def test_scaling_gates_cover_registered_and_active_user_write_paths(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "scaling-gates.db"
    database_url = f"sqlite:///{database_path.as_posix()}"

    result = run_readiness(
        "scaling-gates",
        "--database-url",
        database_url,
        "--registered-users",
        "1000",
        "--active-users",
        "100",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "active_users": 100,
        "check": "scaling-gates",
        "concurrency_gates": [
            "registration-account-setup",
            "consent",
            "mutation-submission",
            "package-generation",
        ],
        "database_url": "sqlite:///<redacted>",
        "legacy_snapshot_rows": 0,
        "packaged_mutation_requests": 100,
        "registered_users": 1000,
        "status": "ok",
    }

    with sqlite3.connect(database_path) as connection:
        counts = {
            "participants": connection.execute(
                "select count(*) from portal_participants",
            ).fetchone()[0],
            "users": connection.execute(
                "select count(*) from portal_user_accounts",
            ).fetchone()[0],
            "consents": connection.execute(
                "select count(*) from portal_consent_evidence",
            ).fetchone()[0],
            "mutations": connection.execute(
                "select count(*) from portal_mutation_requests",
            ).fetchone()[0],
            "packages": connection.execute(
                "select count(*) from portal_mutation_packages",
            ).fetchone()[0],
            "packaged": connection.execute(
                "select count(*) from portal_packaged_mutation_requests",
            ).fetchone()[0],
            "snapshots": connection.execute(
                "select count(*) from portal_state_snapshots",
            ).fetchone()[0],
        }

    assert counts == {
        "participants": 1000,
        "users": 1000,
        "consents": 100,
        "mutations": 100,
        "packages": 1,
        "packaged": 100,
        "snapshots": 0,
    }


def test_architecture_docs_show_db_runtime_persistence_and_scaling_gates() -> None:
    mermaid = MERMAID_MAP.read_text(encoding="utf-8")
    readiness = READINESS_DOCS.read_text(encoding="utf-8")

    for expected in [
        "DB Runtime Persistence",
        "Admin API",
        "Partner API",
        "Participant API",
        "Public/Auth API",
    ]:
        assert expected in mermaid

    assert "Legacy snapshot compatibility" in readiness
    assert "scaling-gates" in readiness
    assert "1000 registered users" in readiness
    assert "100 active users" in readiness
    for expected in [
        "registration/account setup",
        "consent",
        "mutation submission",
        "package generation",
    ]:
        assert expected in readiness


def test_go_live_domain_docs_publish_canonical_language_and_adrs() -> None:
    assert CONTEXT_DOC.exists()
    context = CONTEXT_DOC.read_text(encoding="utf-8")
    prd = PORTAL_PRD.read_text(encoding="utf-8")
    plan = PORTAL_PLAN.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    public_docs = "\n".join([context, prd, plan, readme])
    adr_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(ADR_DIR.glob("*.md"))
    )

    for expected in [
        "SunTerra LEG",
        "LEG-Vertrag",
        "Mutation",
        "Eintritt",
        "Paketbereit-Check",
        "Netzwerktopologie",
        "Interessensmeldung",
        "Partnerstatus",
    ]:
        assert expected in context

    assert "Basadingen-Schlattingen" in context
    assert "Gebiet" in context
    assert "Partnerkontext" in context
    assert "LEG-/Mutationshinweise" not in public_docs
    assert "Mutationshinweise" not in public_docs
    assert "freigegebene Mutationen" not in plan
    assert "Mutationsfreigabe" not in plan
    assert "LEG-Freigabe" not in plan
    assert "Basadingen zuerst" not in public_docs
    assert "LEG-Vertrag" in prd
    assert "Paketbereit-Check" in plan
    assert "Basadingen-Schlattingen" in readme

    assert "verbindlicher Pilot" in adr_text
    assert "privates Hosting" in adr_text
    assert "Public-Rollout-Gate" in adr_text
    assert "Mutationsbindung" in adr_text
    assert "`entry`" in adr_text
    assert "Paketbereit-Check" in adr_text


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


def test_private_pilot_hosting_checklist_covers_go_live_operational_gates(
    tmp_path: Path,
) -> None:
    result = run_readiness(
        "private-pilot-checklist",
        env=production_env_with_required_config(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "alerts": [
            "application-downtime",
            "database-unreachable",
            "mail-delivery-failures",
            "critical-readiness-failures",
        ],
        "check": "private-pilot-hosting",
        "pilot_access": "invitation-or-allowlist",
        "private_hosting": "allowed-for-pilot",
        "public_rollout_gate": [
            "hosting-decision-private-or-managed",
            "restore-test-passed",
            "active-alerts",
            "pilot-feedback-reviewed",
            "14-stable-days-after-real-package",
            "legal-data-protection-community-process-approval",
            "explicit-public-rollout-approval",
        ],
        "readiness_probes": [
            "application-health",
            "database-readiness",
            "auth-readiness",
            "smtp-readiness",
        ],
        "requirements": [
            "tls-domain",
            "postgres-runtime",
            "configured-cors-origins",
            "production-secret-key",
            "smtp-delivery",
            "bootstrap-admin",
            "admin-totp-mfa",
            "daily-encrypted-offsite-backups",
            "documented-restore-test",
            "health-readiness-checks",
            "alert-routing",
            "SUNTERRA_PUBLIC_ROLLOUT_APPROVED",
        ],
        "status": "ok",
    }
    assert "test-secret-for-production-readiness" not in result.stdout
    assert "test-secret-for-production-readiness" not in result.stderr

    readiness_docs = READINESS_DOCS.read_text(encoding="utf-8")
    for expected in [
        "private-pilot-checklist",
        "application-health",
        "database-readiness",
        "auth-readiness",
        "smtp-readiness",
        "application-downtime",
        "hosting-decision-private-or-managed",
        "SUNTERRA_PUBLIC_ROLLOUT_APPROVED",
        "explicit-public-rollout-approval",
    ]:
        assert expected in readiness_docs
