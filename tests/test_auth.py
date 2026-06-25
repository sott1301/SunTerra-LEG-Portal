from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def test_authenticated_participant_can_retrieve_own_identity_and_role() -> None:
    response = TestClient(app).get(
        "/api/me",
        headers={"Authorization": "Bearer dev:participant"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "dev-participant",
        "email": "participant@example.test",
        "display_name": "Teilnehmer Demo",
        "role": "participant",
        "mfa_satisfied": False,
    }


def test_me_requires_authentication() -> None:
    response = TestClient(app).get("/api/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_participant_cannot_open_admin_participant_workspace() -> None:
    response = TestClient(app).get(
        "/api/admin/participants",
        headers={"Authorization": "Bearer dev:participant"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Role is not allowed"}


def test_leg_admin_can_open_admin_participant_workspace() -> None:
    response = TestClient(app).get(
        "/api/admin/participants",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert response.status_code == 200
    assert response.json() == {"participants": []}
