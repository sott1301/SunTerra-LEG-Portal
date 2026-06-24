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


def poison_legacy_snapshot(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            insert into portal_state_snapshots (id, payload_json)
            values ('default', '{not valid json')
            on conflict(id) do update set payload_json = excluded.payload_json
            """,
        )


def onboard_verified_participant(client: TestClient, *, email: str) -> dict[str, str]:
    onboarding_response = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={"email": email, "display_name": "Async Package Member"},
    )
    assert onboarding_response.status_code == 201
    onboarding = onboarding_response.json()
    verification_response = client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    assert verification_response.status_code == 200
    setup_response = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Async Package Member",
            "password": "SunTerra123!",
        },
    )
    assert setup_response.status_code == 200

    return {"Authorization": f"Bearer {setup_response.json()['access_token']}"}


def create_approved_address_mutation(
    client: TestClient,
    *,
    participant_headers: dict[str, str],
    quarter: str,
    submitted_on: str,
) -> dict:
    submitted_response = client.post(
        "/api/participants/me/mutation-requests",
        headers=participant_headers,
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": quarter,
            "submitted_on": submitted_on,
            "new_address": {
                "street": "Async DB Weg 46",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    )
    assert submitted_response.status_code == 201
    submitted = submitted_response.json()
    review_response = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers=LEG_HEADERS,
        json={"decision": "approved"},
    )
    assert review_response.status_code == 200

    return submitted


def test_mutation_package_artifacts_use_async_database_when_legacy_snapshot_is_unreadable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "mutation-packages-async.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    participant_headers = onboard_verified_participant(
        first_client,
        email="async-package-artifacts@example.test",
    )
    submitted = create_approved_address_mutation(
        first_client,
        participant_headers=participant_headers,
        quarter="2036-Q2",
        submitted_on="2036-03-31",
    )
    package_response = first_client.post(
        "/api/admin/mutation-packages",
        headers=LEG_HEADERS,
        json={"quarter": "2036-Q2"},
    )
    assert package_response.status_code == 201
    package = package_response.json()

    poison_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    partner_list_response = second_client.get(
        "/api/partner/mutation-packages",
        headers=PARTNER_HEADERS,
    )
    partner_detail_response = second_client.get(
        f"/api/partner/mutation-packages/{package['package_id']}",
        headers=PARTNER_HEADERS,
    )
    admin_metadata_response = second_client.get(
        f"/api/admin/mutation-packages/{package['package_id']}",
        headers=LEG_HEADERS,
    )
    json_response = second_client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/json",
        headers=LEG_HEADERS,
    )
    csv_response = second_client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/csv",
        headers=LEG_HEADERS,
    )
    pdf_response = second_client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/pdf",
        headers=LEG_HEADERS,
    )

    assert partner_list_response.status_code == 200
    assert [
        summary
        for summary in partner_list_response.json()
        if summary["package_id"] == package["package_id"]
    ] == [
        {
            "package_id": package["package_id"],
            "leg_id": "basadingen",
            "quarter": "2036-Q2",
            "effective_date": "2036-07-01",
            "generated_at": package["generated_at"],
            "record_count": 1,
            "current_status": "created",
            "status_updated_at": package["generated_at"],
        },
    ]
    assert partner_detail_response.status_code == 200
    assert partner_detail_response.json()["records"][0]["mutation_request_id"] == submitted["id"]
    assert admin_metadata_response.status_code == 200
    assert admin_metadata_response.json()["current_status"] == "created"
    assert json_response.status_code == 200
    assert json_response.json()["hash"] == package["hash"]
    assert csv_response.status_code == 200
    assert submitted["id"] in csv_response.text
    assert "Async DB Weg 46" in csv_response.text
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF")


def test_partner_status_tasks_and_member_register_use_async_database_when_legacy_snapshot_is_unreadable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "mutation-package-status-async.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    participant_headers = onboard_verified_participant(
        first_client,
        email="async-package-status@example.test",
    )
    create_approved_address_mutation(
        first_client,
        participant_headers=participant_headers,
        quarter="2036-Q3",
        submitted_on="2036-06-30",
    )
    package_response = first_client.post(
        "/api/admin/mutation-packages",
        headers=LEG_HEADERS,
        json={"quarter": "2036-Q3"},
    )
    assert package_response.status_code == 201
    package = package_response.json()
    participant_id = package["records"][0]["participant_id"]

    poison_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app)

    status_response = second_client.post(
        f"/api/partner/mutation-packages/{package['package_id']}/status",
        headers=PARTNER_HEADERS,
        json={"status": "question", "reference": "EW-ASYNC-46"},
    )
    tasks_response = second_client.get("/api/partner/tasks", headers=PARTNER_HEADERS)
    register_response = second_client.get(
        "/api/partner/member-register",
        headers=PARTNER_HEADERS,
    )
    admin_metadata_response = second_client.get(
        f"/api/admin/mutation-packages/{package['package_id']}",
        headers=LEG_HEADERS,
    )

    assert status_response.status_code == 200
    status_payload = status_response.json()
    status_event = status_payload["status_history"][-1]
    assert status_payload["current_status"] == "question"
    assert status_event == {
        "status": "question",
        "actor_role": "partner_admin",
        "created_at": status_event["created_at"],
        "reference": "EW-ASYNC-46",
        "reason": None,
    }
    assert tasks_response.status_code == 200
    assert [
        task
        for task in tasks_response.json()
        if task["package_id"] == package["package_id"]
    ] == [
        {
            "task_id": f"{package['package_id']}:question",
            "package_id": package["package_id"],
            "leg_id": "basadingen",
            "quarter": "2036-Q3",
            "effective_date": "2036-10-01",
            "status": "question",
            "reference": "EW-ASYNC-46",
            "reason": None,
            "created_at": status_event["created_at"],
            "record_count": 1,
        },
    ]
    assert register_response.status_code == 200
    assert [
        member
        for member in register_response.json()["members"]
        if member["participant_id"] == participant_id
    ] == [
        {
            "participant_id": participant_id,
            "display_name": "Async Package Member",
            "membership_status": "active",
            "reporting_address": {
                "street": "Async DB Weg 46",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
            "latest_package_status": {
                "package_id": package["package_id"],
                "quarter": "2036-Q3",
                "effective_date": "2036-10-01",
                "status": "question",
            },
        },
    ]
    assert admin_metadata_response.status_code == 200
    assert admin_metadata_response.json()["current_status"] == "question"


def test_admin_generates_mutation_package_from_async_database_when_legacy_snapshot_is_unreadable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "mutation-package-generation-async.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    participant_headers = onboard_verified_participant(
        first_client,
        email="async-package-generation@example.test",
    )
    submitted = create_approved_address_mutation(
        first_client,
        participant_headers=participant_headers,
        quarter="2037-Q1",
        submitted_on="2036-12-31",
    )

    poison_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app, raise_server_exceptions=False)

    package_response = second_client.post(
        "/api/admin/mutation-packages",
        headers=LEG_HEADERS,
        json={"quarter": "2037-Q1"},
    )
    assert package_response.status_code == 201
    package = package_response.json()
    json_response = second_client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/json",
        headers=LEG_HEADERS,
    )

    assert package["quarter"] == "2037-Q1"
    assert package["records"][0]["mutation_request_id"] == submitted["id"]
    assert package["records"][0]["new_address"]["street"] == "Async DB Weg 46"
    assert json_response.status_code == 200
    assert json_response.json()["hash"] == package["hash"]


def test_admin_package_generation_does_not_duplicate_mutation_requests_in_async_database(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "mutation-package-duplicate-guard-async.db"
    migration_url = f"sqlite:///{database_path.as_posix()}"
    runtime_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    migrate_database(migration_url)
    monkeypatch.delenv("SUNTERRA_DATABASE_URL", raising=False)
    monkeypatch.setenv("SUNTERRA_ASYNC_DATABASE_URL", runtime_url)
    clear_runtime_state()

    first_client = TestClient(app)
    participant_headers = onboard_verified_participant(
        first_client,
        email="async-package-duplicate@example.test",
    )
    submitted = create_approved_address_mutation(
        first_client,
        participant_headers=participant_headers,
        quarter="2037-Q2",
        submitted_on="2037-03-31",
    )

    poison_legacy_snapshot(database_path)
    clear_runtime_state()
    second_client = TestClient(app, raise_server_exceptions=False)

    first_package_response = second_client.post(
        "/api/admin/mutation-packages",
        headers=LEG_HEADERS,
        json={"quarter": "2037-Q2"},
    )
    second_package_response = second_client.post(
        "/api/admin/mutation-packages",
        headers=LEG_HEADERS,
        json={"quarter": "2037-Q2"},
    )
    partner_list_response = second_client.get(
        "/api/partner/mutation-packages",
        headers=PARTNER_HEADERS,
    )

    assert first_package_response.status_code == 201
    first_package = first_package_response.json()
    assert second_package_response.status_code == 400
    assert second_package_response.json() == {
        "detail": "No approved un-packaged mutation requests for quarter",
    }
    assert partner_list_response.status_code == 200
    assert [
        summary
        for summary in partner_list_response.json()
        if summary["quarter"] == "2037-Q2"
    ] == [
        {
            "package_id": first_package["package_id"],
            "leg_id": "basadingen",
            "quarter": "2037-Q2",
            "effective_date": "2037-07-01",
            "generated_at": first_package["generated_at"],
            "record_count": 1,
            "current_status": "created",
            "status_updated_at": first_package["generated_at"],
        },
    ]
    detail_response = second_client.get(
        f"/api/partner/mutation-packages/{first_package['package_id']}",
        headers=PARTNER_HEADERS,
    )
    assert detail_response.status_code == 200
    assert [
        record["mutation_request_id"]
        for record in detail_response.json()["records"]
    ] == [submitted["id"]]
