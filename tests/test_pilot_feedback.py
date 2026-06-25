from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app
from tests.test_public_self_service_onboarding import start_self_service_onboarding


def verified_participant_headers(client: TestClient) -> dict[str, str]:
    onboarding = start_self_service_onboarding(
        client,
        "pilot.feedback@example.test",
    )
    client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    setup = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={
            "display_name": "Pilot Feedback",
            "password": "SunTerra123!",
        },
    )
    return {"Authorization": f"Bearer {setup.json()['access_token']}"}


def test_pilot_user_can_submit_feedback_and_leg_admin_can_review_it() -> None:
    client = TestClient(app)
    participant_headers = verified_participant_headers(client)

    submitted = client.post(
        "/api/pilot-feedback",
        headers=participant_headers,
        json={
            "category": "process",
            "message": "Der Paketbereit-Check ist im Pilot gut nachvollziehbar.",
            "context": "mutation-package",
        },
    )
    listed = client.get(
        "/api/admin/pilot-feedback",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert submitted.status_code == 201
    payload = submitted.json()
    assert payload.pop("id")
    assert payload.pop("created_at")
    assert payload == {
        "category": "process",
        "message": "Der Paketbereit-Check ist im Pilot gut nachvollziehbar.",
        "context": "mutation-package",
        "user_id": payload["user_id"],
        "user_email": "pilot.feedback@example.test",
        "user_role": "participant",
        "status": "submitted",
        "rollout_relevance": None,
        "admin_note": None,
        "reviewed_at": None,
        "reviewed_by": None,
    }
    assert listed.status_code == 200
    assert listed.json() == [submitted.json()]


def test_leg_admin_can_mark_pilot_feedback_resolution_and_rollout_relevance() -> None:
    client = TestClient(app)
    participant_headers = verified_participant_headers(client)
    submitted = client.post(
        "/api/pilot-feedback",
        headers=participant_headers,
        json={
            "category": "rollout_gate",
            "message": "Vor dem public rollout muss das Paketprotokoll klarer sein.",
            "context": "go-no-go",
        },
    )

    reviewed = client.patch(
        f"/api/admin/pilot-feedback/{submitted.json()['id']}",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "status": "resolved",
            "rollout_relevance": "blocks_public_rollout",
            "admin_note": "In Checkliste aufgenommen und vor Rollout zu klaeren.",
        },
    )
    listed = client.get(
        "/api/admin/pilot-feedback",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert reviewed.status_code == 200
    assert reviewed.json() | {"id": submitted.json()["id"]} == {
        "id": submitted.json()["id"],
        "category": "rollout_gate",
        "message": "Vor dem public rollout muss das Paketprotokoll klarer sein.",
        "context": "go-no-go",
        "user_id": reviewed.json()["user_id"],
        "user_email": "pilot.feedback@example.test",
        "user_role": "participant",
        "status": "resolved",
        "rollout_relevance": "blocks_public_rollout",
        "admin_note": "In Checkliste aufgenommen und vor Rollout zu klaeren.",
        "reviewed_at": reviewed.json()["reviewed_at"],
        "reviewed_by": "dev-leg-admin",
        "created_at": reviewed.json()["created_at"],
    }
    assert listed.status_code == 200
    assert listed.json() == [reviewed.json()]
