from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def test_leg_admin_can_invite_participant_for_basadingen() -> None:
    response = TestClient(app).post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "anna.mueller@example.test", "display_name": "Anna Mueller"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload.pop("token")
    assert payload == {
        "email": "anna.mueller@example.test",
        "display_name": "Anna Mueller",
        "leg_id": "basadingen",
        "status": "pending_email_verification",
    }


def test_participant_cannot_invite_participant() -> None:
    response = TestClient(app).post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:participant"},
        json={"email": "blocked@example.test", "display_name": "Blocked Person"},
    )

    assert response.status_code == 403


def test_invited_participant_can_accept_invitation() -> None:
    client = TestClient(app)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "ben.keller@example.test", "display_name": "Ben Keller"},
    ).json()

    response = client.post(f"/api/auth/invitations/{invitation['token']}/accept")

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"].startswith("dev:participant:")
    assert payload["token_type"] == "bearer"
    assert payload["participant_id"]
    assert payload["email_verification_required"] is True


def test_invited_participant_can_verify_email_after_accepting() -> None:
    client = TestClient(app)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "carla.graf@example.test", "display_name": "Carla Graf"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()

    response = client.post(
        f"/api/auth/email-verifications/{invitation['token']}/verify",
    )

    assert response.status_code == 200
    assert response.json() == {
        "participant_id": accepted["participant_id"],
        "email_verified": True,
    }


def test_accepted_unverified_participant_cannot_open_own_membership_workspace() -> None:
    client = TestClient(app)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "clara.steiner@example.test", "display_name": "Clara Steiner"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()

    response = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {accepted['access_token']}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Email verification required"}


def test_verified_invited_participant_can_use_issued_access_token_for_me() -> None:
    client = TestClient(app)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "dario.huber@example.test", "display_name": "Dario Huber"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {accepted['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": accepted["participant_id"],
        "email": "dario.huber@example.test",
        "display_name": "Dario Huber",
        "role": "participant",
    }


def test_verified_participant_can_open_own_membership_workspace() -> None:
    client = TestClient(app)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "eva.baumann@example.test", "display_name": "Eva Baumann"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    response = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {accepted['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "participant_id": accepted["participant_id"],
        "display_name": "Eva Baumann",
        "email": "eva.baumann@example.test",
        "leg_id": "basadingen",
        "leg_name": "SunTerra LEG Basadingen",
        "membership_status": "active",
        "billing_notice": "Abrechnung und Inkasso bleiben bei Gemeinde/EW.",
    }


def test_non_participant_cannot_open_participant_membership_workspace() -> None:
    response = TestClient(app).get(
        "/api/participants/me/membership",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert response.status_code == 403


def test_participant_cannot_read_another_participants_membership() -> None:
    client = TestClient(app)
    first_invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "fiona.meier@example.test", "display_name": "Fiona Meier"},
    ).json()
    first_accepted = client.post(
        f"/api/auth/invitations/{first_invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{first_invitation['token']}/verify")
    second_invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "gian.wyss@example.test", "display_name": "Gian Wyss"},
    ).json()
    second_accepted = client.post(
        f"/api/auth/invitations/{second_invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{second_invitation['token']}/verify")

    response = client.get(
        f"/api/participants/{second_accepted['participant_id']}/membership",
        headers={"Authorization": f"Bearer {first_accepted['access_token']}"},
    )

    assert response.status_code == 403
