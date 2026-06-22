from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def verified_participant_token(client: TestClient, email: str) -> str:
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": email, "display_name": "Contact Channel Tester"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    return accepted["access_token"]


def test_verified_participant_updates_contact_channels_without_mutation_request() -> None:
    client = TestClient(app)
    participant_email = "contact-channel-update@example.test"
    participant_token = verified_participant_token(client, participant_email)

    response = client.patch(
        "/api/participants/me/contact-channels",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "phone_number": "+41 52 555 01 23",
            "preferred_contact_channel": "phone",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["participant_id"] == participant_token.removeprefix(
        "dev:participant:",
    )
    assert payload["email"] == participant_email
    assert payload["phone_number"] == "+41 52 555 01 23"
    assert payload["preferred_contact_channel"] == "phone"
    assert len(payload["audit_events"]) == 1
    audit_event = payload["audit_events"][0]
    assert audit_event["id"]
    assert audit_event["created_at"]
    assert audit_event == {
        "id": audit_event["id"],
        "action": "participant.contact_channels_updated",
        "actor_role": "participant",
        "created_at": audit_event["created_at"],
        "from_status": None,
        "to_status": None,
        "reason": None,
    }

    mutation_response = client.get(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
    )

    assert mutation_response.status_code == 200
    assert mutation_response.json() == []


def test_meldepflichtige_fields_are_rejected_from_direct_contact_channel_update() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "contact-channel-address-rejected@example.test",
    )

    response = client.patch(
        "/api/participants/me/contact-channels",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "phone_number": "+41 52 555 01 24",
            "preferred_contact_channel": "phone",
            "address": {
                "street": "Hauptstrasse 7",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    )

    assert response.status_code == 422

    mutation_response = client.get(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
    )
    assert mutation_response.status_code == 200
    assert mutation_response.json() == []

    accepted_response = client.patch(
        "/api/participants/me/contact-channels",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "phone_number": "+41 52 555 01 25",
            "preferred_contact_channel": "phone",
        },
    )

    assert accepted_response.status_code == 200
    assert len(accepted_response.json()["audit_events"]) == 1
