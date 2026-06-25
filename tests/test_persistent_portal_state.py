from base64 import b64encode
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from sunterra_leg_portal import auth
from sunterra_leg_portal import main as portal
from sunterra_leg_portal.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEG_HEADERS = {"Authorization": "Bearer dev:leg_admin"}
PARTNER_HEADERS = {"Authorization": "Bearer dev:partner_admin"}


def migrate_database(database_url: str) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def clear_runtime_state() -> None:
    for store in [
        portal.INVITATIONS,
        portal.COMMUNICATION_EVENTS,
        portal.USER_ACCOUNTS,
        portal.PASSWORD_RESET_TOKENS,
        portal.PARTICIPANTS,
        portal.NETWORK_TOPOLOGY_ENTRIES,
        portal.PILOT_FEEDBACK,
        portal.INTEREST_RECORDS,
        portal.PILOT_ALLOWLIST,
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


def poison_legacy_snapshot(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            insert into portal_state_snapshots (id, payload_json)
            values ('default', '{not valid json')
            on conflict(id) do update set payload_json = excluded.payload_json
            """,
        )


def approve_participant_eligibility(
    client: TestClient,
    participant_id: str,
) -> None:
    response = client.post(
        f"/api/admin/participants/{participant_id}/eligibility-review",
        headers=LEG_HEADERS,
        json={
            "decision": "approved",
            "reason": "Persistent-state test participant eligibility approved.",
        },
    )
    assert response.status_code == 200


def delete_document_versions(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("delete from portal_document_versions")


def delete_consent_evidence(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("delete from portal_consent_evidence")


def delete_mutation_requests_and_audit_events(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("delete from portal_participant_audit_events")
        connection.execute("delete from portal_mutation_requests")


def delete_file_evidence(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("delete from portal_file_evidence")


def test_self_service_onboarding_survives_new_session_without_legacy_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "onboarding-state.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("SUNTERRA_DATABASE_URL", database_url)
    migrate_database(database_url)
    clear_runtime_state()

    first_client = TestClient(app)
    recipient_email = "table-backed-onboarding@example.test"
    onboarding_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": recipient_email,
            "display_name": "Table Backed Participant",
        },
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    participant_headers = {
        "Authorization": f"Bearer {onboarding['access_token']}",
    }
    verification_response = first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    assert verification_response.status_code == 200
    setup_response = first_client.post(
        "/api/auth/participant-account-setup",
        headers=participant_headers,
        json={
            "display_name": "Table Backed Participant",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200
    approve_participant_eligibility(first_client, onboarding["participant_id"])
    participant_headers = {
        "Authorization": f"Bearer {setup_response.json()['access_token']}",
    }

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    me_response = second_client.get("/api/me", headers=participant_headers)
    membership_response = second_client.get(
        "/api/participants/me/membership",
        headers=participant_headers,
    )
    checkpoint_response = second_client.get(
        "/api/participants/me/identity-checkpoint?action=membership_activation",
        headers=participant_headers,
    )
    communication_response = second_client.get(
        f"/api/admin/communication-events?recipient_email={recipient_email}",
        headers=LEG_HEADERS,
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == recipient_email
    assert membership_response.status_code == 200
    assert membership_response.json()["membership_status"] == "active"
    assert membership_response.json()["display_name"] == "Table Backed Participant"
    assert checkpoint_response.status_code == 200
    assert checkpoint_response.json()["current_level"] == "account_setup"
    assert checkpoint_response.json()["satisfied"] is True
    assert communication_response.status_code == 200
    assert {
        event["event_type"]
        for event in communication_response.json()
    } == {"email_verification"}


def test_failed_smtp_event_uses_database_source_after_delivery_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "smtp-failed-event.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    recipient_email = "db-backed-smtp-failure@example.test"

    class FailingSmtp:
        def __init__(self, _host: str, _port: int, timeout: int):
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def send_message(self, _message):
            raise RuntimeError("smtp unavailable")

    monkeypatch.setenv("SUNTERRA_DATABASE_URL", database_url)
    monkeypatch.setenv("SUNTERRA_ENV", "production")
    monkeypatch.setenv("SUNTERRA_PUBLIC_ROLLOUT_APPROVED", "1")
    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "smtp-production-secret")
    monkeypatch.setenv("SUNTERRA_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SUNTERRA_SMTP_PORT", "587")
    monkeypatch.setenv("SUNTERRA_SMTP_FROM_EMAIL", "noreply@portal.example.test")
    monkeypatch.setenv("SUNTERRA_PUBLIC_BASE_URL", "https://portal.example.test")
    monkeypatch.setattr("smtplib.SMTP", FailingSmtp)
    migrate_database(database_url)
    clear_runtime_state()

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={"email": recipient_email, "display_name": "DB Failed SMTP"},
    )
    clear_runtime_state()
    monkeypatch.setenv("SUNTERRA_ENV", "development")
    events_response = client.get(
        f"/api/admin/communication-events?recipient_email={recipient_email}",
        headers=LEG_HEADERS,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Email delivery failed"}
    assert events_response.status_code == 200
    assert [event["status"] for event in events_response.json()] == ["failed"]


def test_participant_identity_checkpoint_uses_async_database_when_legacy_snapshot_is_unreadable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "identity-checkpoint-no-legacy-snapshot.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "async-runtime-checkpoint@example.test",
            "display_name": "Async Runtime Checkpoint",
        },
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup_response = first_client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Runtime Checkpoint",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200

    poison_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app, raise_server_exceptions=False)

    checkpoint_response = second_client.get(
        "/api/participants/me/identity-checkpoint?action=membership_activation",
        headers={"Authorization": f"Bearer {setup_response.json()['access_token']}"},
    )

    assert checkpoint_response.status_code == 200
    assert checkpoint_response.json() == {
        "action": "membership_activation",
        "required_level": "account_setup",
        "current_level": "account_setup",
        "satisfied": True,
    }


def test_document_version_survives_new_session_without_legacy_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "document-state.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("SUNTERRA_DATABASE_URL", database_url)
    migrate_database(database_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "table-backed-documents@example.test",
            "display_name": "Document Reader",
        },
    ).json()
    participant_headers = {
        "Authorization": f"Bearer {onboarding['access_token']}",
    }
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup = first_client.post(
        "/api/auth/participant-account-setup",
        headers=participant_headers,
        json={
            "display_name": "Document Reader",
            "password": "SunTerra123!",
        },
    ).json()
    participant_headers = {
        "Authorization": f"Bearer {setup['access_token']}",
    }
    published_response = first_client.post(
        "/api/admin/document-versions",
        headers=LEG_HEADERS,
        json={
            "document_key": "portal_terms_table_backed",
            "title": "Portal Nutzungsbedingungen",
            "version": "2034-01-01",
            "content": "Persistierte Dokumentversion.",
            "context": "participant_onboarding",
        },
    )
    assert published_response.status_code == 201
    published = published_response.json()

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    current_response = second_client.get(
        "/api/documents/current?document_key=portal_terms_table_backed",
        headers=participant_headers,
    )

    assert current_response.status_code == 200
    assert current_response.json() == {
        "id": published["id"],
        "document_key": "portal_terms_table_backed",
        "title": "Portal Nutzungsbedingungen",
        "version": "2034-01-01",
        "content": "Persistierte Dokumentversion.",
        "document_hash": published["document_hash"],
        "context": "participant_onboarding",
        "published_at": published["published_at"],
    }


def test_consent_evidence_survives_new_session_without_legacy_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "consent-state.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("SUNTERRA_DATABASE_URL", database_url)
    migrate_database(database_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "table-backed-consent@example.test",
            "display_name": "Consent Reader",
        },
    ).json()
    participant_headers = {
        "Authorization": f"Bearer {onboarding['access_token']}",
    }
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup = first_client.post(
        "/api/auth/participant-account-setup",
        headers=participant_headers,
        json={
            "display_name": "Consent Reader",
            "password": "SunTerra123!",
        },
    ).json()
    participant_headers = {
        "Authorization": f"Bearer {setup['access_token']}",
    }
    document = first_client.post(
        "/api/admin/document-versions",
        headers=LEG_HEADERS,
        json={
            "document_key": "portal_terms_consent_table_backed",
            "title": "Portal Nutzungsbedingungen",
            "version": "2034-02-01",
            "content": "Persistierte Zustimmung.",
            "context": "participant_onboarding",
        },
    ).json()
    consent_response = first_client.post(
        "/api/participants/me/consent-evidence",
        headers=participant_headers,
        json={
            "document_version_id": document["id"],
            "context": "participant_onboarding",
            "accepted": True,
        },
    )
    assert consent_response.status_code == 201
    consent = consent_response.json()

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    history_response = second_client.get(
        "/api/participants/me/consent-evidence",
        headers=participant_headers,
    )

    assert history_response.status_code == 200
    assert history_response.json() == [consent]


def test_mutation_request_review_survives_new_session_without_legacy_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "mutation-state.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("SUNTERRA_DATABASE_URL", database_url)
    migrate_database(database_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "table-backed-mutation@example.test",
            "display_name": "Mutation Submitter",
        },
    ).json()
    participant_headers = {
        "Authorization": f"Bearer {onboarding['access_token']}",
    }
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup = first_client.post(
        "/api/auth/participant-account-setup",
        headers=participant_headers,
        json={
            "display_name": "Mutation Submitter",
            "password": "SunTerra123!",
        },
    ).json()
    participant_headers = {
        "Authorization": f"Bearer {setup['access_token']}",
    }
    approve_participant_eligibility(first_client, onboarding["participant_id"])
    submitted_response = first_client.post(
        "/api/participants/me/mutation-requests",
        headers=participant_headers,
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": "2034-Q2",
            "submitted_on": "2034-03-31",
            "new_address": {
                "street": "Tabellenweg 28",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    )
    assert submitted_response.status_code == 201
    submitted = submitted_response.json()
    review_response = first_client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers=LEG_HEADERS,
        json={"decision": "approved"},
    )
    assert review_response.status_code == 200
    reviewed = review_response.json()

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    participant_requests_response = second_client.get(
        "/api/participants/me/mutation-requests",
        headers=participant_headers,
    )
    admin_requests_response = second_client.get(
        "/api/admin/mutation-requests?status=approved",
        headers=LEG_HEADERS,
    )

    assert participant_requests_response.status_code == 200
    assert participant_requests_response.json() == [
        {
            key: value
            for key, value in reviewed.items()
            if key != "participant"
        },
    ]
    assert admin_requests_response.status_code == 200
    assert [
        request
        for request in admin_requests_response.json()
        if request["id"] == submitted["id"]
    ] == [reviewed]


def test_file_evidence_survives_new_session_without_legacy_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "file-evidence-state.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("SUNTERRA_DATABASE_URL", database_url)
    migrate_database(database_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "table-backed-evidence@example.test",
            "display_name": "Evidence Owner",
        },
    ).json()
    participant_headers = {
        "Authorization": f"Bearer {onboarding['access_token']}",
    }
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup = first_client.post(
        "/api/auth/participant-account-setup",
        headers=participant_headers,
        json={
            "display_name": "Evidence Owner",
            "password": "SunTerra123!",
        },
    ).json()
    participant_headers = {
        "Authorization": f"Bearer {setup['access_token']}",
    }
    approve_participant_eligibility(first_client, onboarding["participant_id"])
    submitted = first_client.post(
        "/api/participants/me/mutation-requests",
        headers=participant_headers,
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": "2034-Q3",
            "submitted_on": "2034-06-30",
            "new_address": {
                "street": "Belegweg 4",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    ).json()
    evidence_content = b"Persistierte Mutation Evidence"
    attached_response = first_client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/file-evidence",
        headers=LEG_HEADERS,
        json={
            "document_type": "mutation_review_supporting_document",
            "purpose": "mutation_review",
            "version": "2034-06-30",
            "filename": "address-proof.txt",
            "content_type": "text/plain",
            "content_base64": b64encode(evidence_content).decode("ascii"),
        },
    )
    assert attached_response.status_code == 201
    attached = attached_response.json()

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    metadata_response = second_client.get(
        f"/api/mutation-requests/{submitted['id']}/file-evidence/{attached['id']}",
        headers=LEG_HEADERS,
    )
    content_response = second_client.get(
        f"/api/mutation-requests/{submitted['id']}/file-evidence/{attached['id']}/content",
        headers=participant_headers,
    )

    assert metadata_response.status_code == 200
    assert metadata_response.json() == attached
    assert content_response.status_code == 200
    assert content_response.json() == {
        **attached,
        "content_base64": b64encode(evidence_content).decode("ascii"),
    }


def test_portal_state_survives_new_client_session(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "portal-state.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("SUNTERRA_DATABASE_URL", database_url)
    migrate_database(database_url)
    clear_runtime_state()

    first_client = TestClient(app)
    invitation = first_client.post(
        "/api/admin/participant-invitations",
        headers=LEG_HEADERS,
        json={
            "email": "persistent-participant@example.test",
            "display_name": "Persistent Participant",
        },
    ).json()
    accepted = first_client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    first_client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")
    participant_headers = {
        "Authorization": f"Bearer {accepted['access_token']}",
    }
    setup = first_client.post(
        "/api/auth/participant-account-setup",
        headers=participant_headers,
        json={
            "display_name": "Persistent Participant",
            "password": "SunTerra123!",
        },
    ).json()
    participant_headers = {
        "Authorization": f"Bearer {setup['access_token']}",
    }
    submitted = first_client.post(
        "/api/participants/me/mutation-requests",
        headers=participant_headers,
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": "2033-Q1",
            "submitted_on": "2032-12-31",
            "new_address": {
                "street": "Persistenzweg 1",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    ).json()
    first_client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/package-readiness",
        headers=LEG_HEADERS,
        json={"ready": True, "reason": "Paketbereit-Check bestanden."},
    )
    package = first_client.post(
        "/api/admin/mutation-packages",
        headers=LEG_HEADERS,
        json={"quarter": "2033-Q1"},
    ).json()
    first_client.post(
        f"/api/partner/mutation-packages/{package['package_id']}/status",
        headers=PARTNER_HEADERS,
        json={"status": "question", "reference": "EW-RF-PERSIST"},
    )

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    me_response = second_client.get("/api/me", headers=participant_headers)
    membership_response = second_client.get(
        "/api/participants/me/membership",
        headers=participant_headers,
    )
    tasks_response = second_client.get("/api/partner/tasks", headers=PARTNER_HEADERS)
    package_response = second_client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/json",
        headers=LEG_HEADERS,
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "persistent-participant@example.test"
    assert membership_response.status_code == 200
    assert membership_response.json()["display_name"] == "Persistent Participant"
    assert tasks_response.status_code == 200
    assert [
        task
        for task in tasks_response.json()
        if task["package_id"] == package["package_id"]
    ][0]["reference"] == "EW-RF-PERSIST"
    assert package_response.status_code == 200
    assert package_response.json()["hash"] == package["hash"]


def test_self_service_login_uses_async_runtime_database_after_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-auth.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.setenv("SUNTERRA_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "async-runtime-login@example.test",
            "display_name": "Async Runtime Login",
        },
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup_response = first_client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Runtime Account",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    login_response = second_client.post(
        "/api/auth/login",
        json={
            "email": "async-runtime-login@example.test",
            "password": "SunTerra123!",
        },
    )
    assert login_response.status_code == 200
    login = login_response.json()
    assert login["user"]["display_name"] == "Async Runtime Account"
    assert login["user"]["role"] == "participant"

    me_response = second_client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json() == login["user"]


def test_invitation_account_setup_uses_async_runtime_database_after_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-invitation.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    invitation_response = first_client.post(
        "/api/admin/participant-invitations",
        headers=LEG_HEADERS,
        json={
            "email": "async-runtime-invited@example.test",
            "display_name": "Async Runtime Invited",
        },
    )
    assert invitation_response.status_code == 201
    invitation = invitation_response.json()
    accepted_response = first_client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    )
    assert accepted_response.status_code == 200
    verified_response = first_client.post(
        f"/api/auth/email-verifications/{invitation['token']}/verify",
    )
    assert verified_response.status_code == 200

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    setup_response = second_client.post(
        "/api/auth/participant-account-setup",
        headers={
            "Authorization": f"Bearer {accepted_response.json()['access_token']}",
        },
        json={
            "display_name": "Async Runtime Invited Account",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    third_client = TestClient(app)

    login_response = third_client.post(
        "/api/auth/login",
        json={
            "email": "async-runtime-invited@example.test",
            "password": "SunTerra123!",
        },
    )
    assert login_response.status_code == 200
    login = login_response.json()
    assert login["user"]["display_name"] == "Async Runtime Invited Account"
    assert login["user"]["role"] == "participant"

    me_response = third_client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json() == login["user"]


def test_network_topology_precheck_uses_async_runtime_database_after_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-network-topology.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    imported_response = first_client.post(
        "/api/admin/network-topology-entries",
        headers=LEG_HEADERS,
        json={
            "source_name": "Async Runtime Topologie 2035",
            "entries": [
                {
                    "metering_point_id": "CH-ASYNC-8254-0001",
                    "street": "Persistenzweg 12",
                    "postal_code": "8254",
                    "city": "Basadingen",
                },
            ],
        },
    )
    assert imported_response.status_code == 201

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    onboarding_response = second_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "async-runtime-topology@example.test",
            "display_name": "Async Runtime Topology",
            "metering_point_id": "CH-ASYNC-8254-0001",
            "street": "Persistenzweg 12",
            "postal_code": "8254",
            "city": "Basadingen",
        },
    )
    onboarding = onboarding_response.json()
    second_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup_response = second_client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Runtime Topology",
            "password": "SunTerra123!",
        },
    )
    participant_headers = {
        "Authorization": f"Bearer {setup_response.json()['access_token']}",
    }
    membership_response = second_client.get(
        "/api/participants/me/membership",
        headers=participant_headers,
    )

    assert onboarding_response.status_code == 201
    assert setup_response.status_code == 200
    assert membership_response.status_code == 200
    assert membership_response.json()["membership_status"] == "active"
    assert membership_response.json()["eligibility_status"] == "approved"
    assert (
        membership_response.json()["eligibility_review_reason"]
        == "Netzwerktopologie vorgeprueft: Async Runtime Topologie 2035"
    )


def test_password_reset_token_uses_async_runtime_database_after_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-password-reset.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "async-runtime-reset@example.test",
            "display_name": "Async Runtime Reset",
        },
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup_response = first_client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Runtime Reset",
            "password": "OldReset123!",
        },
    )
    assert setup_response.status_code == 200

    reset_request_response = first_client.post(
        "/api/auth/password-reset/request",
        json={"email": "async-runtime-reset@example.test"},
    )
    assert reset_request_response.status_code == 202
    assert len(portal.PASSWORD_RESET_TOKENS) == 1
    reset_token = next(iter(portal.PASSWORD_RESET_TOKENS))

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    confirm_response = second_client.post(
        "/api/auth/password-reset/confirm",
        json={"token": reset_token, "password": "NewReset123!"},
    )
    old_login_response = second_client.post(
        "/api/auth/login",
        json={
            "email": "async-runtime-reset@example.test",
            "password": "OldReset123!",
        },
    )
    new_login_response = second_client.post(
        "/api/auth/login",
        json={
            "email": "async-runtime-reset@example.test",
            "password": "NewReset123!",
        },
    )
    reused_response = second_client.post(
        "/api/auth/password-reset/confirm",
        json={"token": reset_token, "password": "AnotherReset123!"},
    )

    assert confirm_response.status_code == 200
    assert confirm_response.json() == {"status": "password_reset_completed"}
    assert old_login_response.status_code == 401
    assert new_login_response.status_code == 200
    assert reused_response.status_code == 400


def test_pilot_feedback_uses_async_runtime_database_after_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-pilot-feedback.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "async-runtime-feedback@example.test",
            "display_name": "Async Runtime Feedback",
        },
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup_response = first_client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Runtime Feedback",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200
    feedback_response = first_client.post(
        "/api/pilot-feedback",
        headers={"Authorization": f"Bearer {setup_response.json()['access_token']}"},
        json={
            "category": "rollout_gate",
            "message": "Pilotfeedback bleibt nach Neustart sichtbar.",
            "context": "public-rollout-go-no-go",
        },
    )
    assert feedback_response.status_code == 201
    feedback = feedback_response.json()

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    listed_response = second_client.get(
        "/api/admin/pilot-feedback",
        headers=LEG_HEADERS,
    )

    assert listed_response.status_code == 200
    assert listed_response.json() == [feedback]

    reviewed_response = second_client.patch(
        f"/api/admin/pilot-feedback/{feedback['id']}",
        headers=LEG_HEADERS,
        json={
            "status": "resolved",
            "rollout_relevance": "blocks_public_rollout",
            "admin_note": "Vor Public-Rollout im Go/No-Go geprueft.",
        },
    )
    assert reviewed_response.status_code == 200
    reviewed_feedback = reviewed_response.json()
    assert reviewed_feedback["status"] == "resolved"
    assert reviewed_feedback["rollout_relevance"] == "blocks_public_rollout"
    assert reviewed_feedback["admin_note"] == "Vor Public-Rollout im Go/No-Go geprueft."
    assert reviewed_feedback["reviewed_by"] == "dev-leg-admin"

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    third_client = TestClient(app)
    relisted_response = third_client.get(
        "/api/admin/pilot-feedback",
        headers=LEG_HEADERS,
    )

    assert relisted_response.status_code == 200
    assert relisted_response.json() == [reviewed_feedback]


def test_pilot_interest_and_allowlist_use_async_runtime_database_after_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-pilot-access.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    monkeypatch.setenv("SUNTERRA_REGISTRATION_MODE", "pilot")
    clear_runtime_state()

    first_client = TestClient(app)
    email = "async-runtime-pilot-access@example.test"
    interest_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={"email": email, "display_name": "Async Pilot Access"},
    )
    listed_interest = first_client.get(
        "/api/admin/interest-records",
        headers=LEG_HEADERS,
    )
    allowlisted_response = first_client.post(
        "/api/admin/pilot-allowlist",
        headers=LEG_HEADERS,
        json={"email": email},
    )

    assert interest_response.status_code == 202
    interest_record = interest_response.json()
    assert listed_interest.status_code == 200
    assert listed_interest.json() == [interest_record]
    assert allowlisted_response.status_code == 201
    assert allowlisted_response.json()["email"] == email

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)
    relisted_interest = second_client.get(
        "/api/admin/interest-records",
        headers=LEG_HEADERS,
    )
    onboarding_response = second_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={"email": email, "display_name": "Async Pilot Access"},
    )

    assert relisted_interest.status_code == 200
    assert relisted_interest.json() == [interest_record]
    assert onboarding_response.status_code == 201
    assert onboarding_response.json()["participant_status"] == "pending_email_verification"


def test_admin_participant_directory_uses_async_runtime_database_after_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-participant-directory.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    invitation_response = first_client.post(
        "/api/admin/participant-invitations",
        headers=LEG_HEADERS,
        json={
            "email": "async-runtime-directory@example.test",
            "display_name": "Async Runtime Directory",
        },
    )
    assert invitation_response.status_code == 201
    invitation = invitation_response.json()
    accepted_response = first_client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    )
    assert accepted_response.status_code == 200
    accepted = accepted_response.json()
    verified_response = first_client.post(
        f"/api/auth/email-verifications/{invitation['token']}/verify",
    )
    assert verified_response.status_code == 200

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    directory_response = second_client.get(
        "/api/admin/participants",
        headers=LEG_HEADERS,
    )

    assert directory_response.status_code == 200
    participants_by_id = {
        participant["participant_id"]: participant
        for participant in directory_response.json()["participants"]
    }
    assert participants_by_id[accepted["participant_id"]] == {
        "participant_id": accepted["participant_id"],
        "display_name": "Async Runtime Directory",
        "email": "async-runtime-directory@example.test",
        "leg_id": "basadingen",
        "membership_status": "active",
    }


def test_admin_invitation_list_uses_async_runtime_database_after_status_updates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-invitation-list.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    invitation_response = first_client.post(
        "/api/admin/participant-invitations",
        headers=LEG_HEADERS,
        json={
            "email": "async-runtime-invitation-list@example.test",
            "display_name": "Async Runtime Invitation List",
        },
    )
    assert invitation_response.status_code == 201
    invitation = invitation_response.json()
    accepted_response = first_client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    )
    assert accepted_response.status_code == 200
    verified_response = first_client.post(
        f"/api/auth/email-verifications/{invitation['token']}/verify",
    )
    assert verified_response.status_code == 200

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    list_response = second_client.get(
        "/api/admin/participant-invitations",
        headers=LEG_HEADERS,
    )

    assert list_response.status_code == 200
    invitations_by_token = {
        listed_invitation["token"]: listed_invitation
        for listed_invitation in list_response.json()
    }
    assert invitations_by_token[invitation["token"]] == {
        "token": invitation["token"],
        "email": "async-runtime-invitation-list@example.test",
        "display_name": "Async Runtime Invitation List",
        "leg_id": "basadingen",
        "status": "active",
    }


def test_participant_contact_channels_use_async_runtime_database_after_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-contact-channels.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    invitation_response = first_client.post(
        "/api/admin/participant-invitations",
        headers=LEG_HEADERS,
        json={
            "email": "async-runtime-contact@example.test",
            "display_name": "Async Runtime Contact",
        },
    )
    assert invitation_response.status_code == 201
    invitation = invitation_response.json()
    accepted_response = first_client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    )
    assert accepted_response.status_code == 200
    participant_headers = {
        "Authorization": f"Bearer {accepted_response.json()['access_token']}",
    }
    verified_response = first_client.post(
        f"/api/auth/email-verifications/{invitation['token']}/verify",
    )
    assert verified_response.status_code == 200
    update_response = first_client.patch(
        "/api/participants/me/contact-channels",
        headers=participant_headers,
        json={
            "phone_number": "+41 52 555 33 44",
            "preferred_contact_channel": "phone",
        },
    )
    assert update_response.status_code == 200

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    contact_response = second_client.get(
        "/api/participants/me/contact-channels",
        headers=participant_headers,
    )

    assert contact_response.status_code == 200
    contact_channels = contact_response.json()
    assert contact_channels["email"] == "async-runtime-contact@example.test"
    assert contact_channels["phone_number"] == "+41 52 555 33 44"
    assert contact_channels["preferred_contact_channel"] == "phone"
    assert [event["action"] for event in contact_channels["audit_events"]] == [
        "participant.contact_channels_updated",
    ]


def test_document_versions_use_async_runtime_database_after_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-documents.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "async-runtime-document-reader@example.test",
            "display_name": "Async Runtime Document Reader",
        },
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup_response = first_client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Runtime Document Reader",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200
    participant_headers = {
        "Authorization": f"Bearer {setup_response.json()['access_token']}",
    }
    published_response = first_client.post(
        "/api/admin/document-versions",
        headers=LEG_HEADERS,
        json={
            "document_key": "portal_terms_async_runtime",
            "title": "Portal Nutzungsbedingungen",
            "version": "2035-01-01",
            "content": "Async persistierte Dokumentversion.",
            "context": "participant_onboarding",
        },
    )
    assert published_response.status_code == 201
    published = published_response.json()

    delete_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    platform_login_response = second_client.post(
        "/api/auth/login",
        json={"email": "platform-admin@example.test", "password": "SunTerra123!"},
    )
    assert platform_login_response.status_code == 200
    admin_read_response = second_client.get(
        "/api/admin/document-versions",
        headers={
            "Authorization": f"Bearer {platform_login_response.json()['access_token']}",
        },
    )
    current_response = second_client.get(
        "/api/documents/current?document_key=portal_terms_async_runtime",
        headers=participant_headers,
    )

    assert admin_read_response.status_code == 200
    assert published in admin_read_response.json()
    assert current_response.status_code == 200
    assert current_response.json() == {
        "id": published["id"],
        "document_key": "portal_terms_async_runtime",
        "title": "Portal Nutzungsbedingungen",
        "version": "2035-01-01",
        "content": "Async persistierte Dokumentversion.",
        "document_hash": published["document_hash"],
        "context": "participant_onboarding",
        "published_at": published["published_at"],
    }


def test_current_document_lookup_uses_async_runtime_table_over_stale_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-document-source.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "async-runtime-stale-document@example.test",
            "display_name": "Async Runtime Stale Document",
        },
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup_response = first_client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Runtime Stale Document",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200
    published_response = first_client.post(
        "/api/admin/document-versions",
        headers=LEG_HEADERS,
        json={
            "document_key": "portal_terms_stale_snapshot",
            "title": "Portal Nutzungsbedingungen",
            "version": "2035-02-01",
            "content": "Darf nicht aus dem Snapshot zurueckkommen.",
            "context": "participant_onboarding",
        },
    )
    assert published_response.status_code == 201
    participant_headers = {
        "Authorization": f"Bearer {setup_response.json()['access_token']}",
    }

    delete_document_versions(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    current_response = second_client.get(
        "/api/documents/current?document_key=portal_terms_stale_snapshot",
        headers=participant_headers,
    )

    assert current_response.status_code == 404


def test_participant_consent_history_uses_async_runtime_table_over_stale_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-consent-source.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "async-runtime-stale-consent@example.test",
            "display_name": "Async Runtime Stale Consent",
        },
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup_response = first_client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Runtime Stale Consent",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200
    participant_headers = {
        "Authorization": f"Bearer {setup_response.json()['access_token']}",
    }
    document = first_client.post(
        "/api/admin/document-versions",
        headers=LEG_HEADERS,
        json={
            "document_key": "portal_terms_stale_consent",
            "title": "Portal Nutzungsbedingungen",
            "version": "2035-03-01",
            "content": "Consent Evidence darf nicht aus dem Snapshot zurueckkommen.",
            "context": "participant_onboarding",
        },
    ).json()
    consent_response = first_client.post(
        "/api/participants/me/consent-evidence",
        headers=participant_headers,
        json={
            "document_version_id": document["id"],
            "context": "participant_onboarding",
            "accepted": True,
        },
    )
    assert consent_response.status_code == 201

    delete_consent_evidence(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    history_response = second_client.get(
        "/api/participants/me/consent-evidence",
        headers=participant_headers,
    )

    assert history_response.status_code == 200
    assert history_response.json() == []


def test_mutation_requests_use_async_runtime_table_over_stale_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-mutation-source.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "async-runtime-stale-mutation@example.test",
            "display_name": "Async Runtime Stale Mutation",
        },
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup_response = first_client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Runtime Stale Mutation",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200
    participant_headers = {
        "Authorization": f"Bearer {setup_response.json()['access_token']}",
    }
    approve_participant_eligibility(first_client, onboarding["participant_id"])
    submitted_response = first_client.post(
        "/api/participants/me/mutation-requests",
        headers=participant_headers,
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": "2035-Q4",
            "submitted_on": "2035-09-30",
            "new_address": {
                "street": "Snapshotweg 9",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    )
    assert submitted_response.status_code == 201
    submitted = submitted_response.json()
    review_response = first_client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers=LEG_HEADERS,
        json={"decision": "approved"},
    )
    assert review_response.status_code == 200

    delete_mutation_requests_and_audit_events(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    participant_requests_response = second_client.get(
        "/api/participants/me/mutation-requests",
        headers=participant_headers,
    )
    admin_requests_response = second_client.get(
        "/api/admin/mutation-requests?status=approved",
        headers=LEG_HEADERS,
    )
    rereview_response = second_client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers=LEG_HEADERS,
        json={"decision": "approved"},
    )

    assert participant_requests_response.status_code == 200
    assert participant_requests_response.json() == []
    assert admin_requests_response.status_code == 200
    assert [
        request
        for request in admin_requests_response.json()
        if request["id"] == submitted["id"]
    ] == []
    assert rereview_response.status_code == 404


def test_file_evidence_uses_async_runtime_table_over_stale_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "async-runtime-file-evidence-source.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    onboarding_response = first_client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "async-runtime-stale-file-evidence@example.test",
            "display_name": "Async Runtime Stale File Evidence",
        },
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    first_client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup_response = first_client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Runtime Stale File Evidence",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200
    participant_headers = {
        "Authorization": f"Bearer {setup_response.json()['access_token']}",
    }
    approve_participant_eligibility(first_client, onboarding["participant_id"])
    submitted = first_client.post(
        "/api/participants/me/mutation-requests",
        headers=participant_headers,
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": "2036-Q1",
            "submitted_on": "2035-12-31",
            "new_address": {
                "street": "Belegsnapshot 12",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    ).json()
    evidence_content = b"Stale snapshot evidence must not be served"
    attached_response = first_client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/file-evidence",
        headers=LEG_HEADERS,
        json={
            "document_type": "mutation_review_supporting_document",
            "purpose": "mutation_review",
            "version": "2035-12-31",
            "filename": "address-proof.txt",
            "content_type": "text/plain",
            "content_base64": b64encode(evidence_content).decode("ascii"),
        },
    )
    assert attached_response.status_code == 201
    attached = attached_response.json()

    delete_file_evidence(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    metadata_response = second_client.get(
        f"/api/mutation-requests/{submitted['id']}/file-evidence/{attached['id']}",
        headers=LEG_HEADERS,
    )
    content_response = second_client.get(
        f"/api/mutation-requests/{submitted['id']}/file-evidence/{attached['id']}/content",
        headers=participant_headers,
    )

    assert metadata_response.status_code == 404
    assert content_response.status_code == 404
