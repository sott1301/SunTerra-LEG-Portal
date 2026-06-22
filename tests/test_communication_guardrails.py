from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def verified_participant_token(client: TestClient, email: str) -> str:
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": email, "display_name": "Communication Guardrails"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    return accepted["access_token"]


def submit_regular_address_mutation(
    client: TestClient,
    participant_token: str,
):
    return client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "new_address": {
                "street": "Hauptstrasse 7",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    )


def test_invitation_creation_queues_participant_invitation_email_event() -> None:
    client = TestClient(app)
    recipient_email = "communication-invitation@example.test"

    invitation_response = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "email": recipient_email,
            "display_name": "Communication Invitation",
        },
    )
    events_response = client.get(
        f"/api/admin/communication-events?recipient_email={recipient_email}",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert invitation_response.status_code == 201
    assert events_response.status_code == 200
    events = events_response.json()
    assert len(events) == 1
    event = events[0]
    assert event["id"]
    assert event["created_at"]
    assert event == {
        "id": event["id"],
        "channel": "email",
        "event_type": "participant_invitation",
        "recipient_email": recipient_email,
        "status": "queued",
        "created_at": event["created_at"],
    }


def test_accepting_and_verifying_invitation_queues_email_verification_event() -> None:
    client = TestClient(app)
    recipient_email = "communication-verification@example.test"
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "email": recipient_email,
            "display_name": "Communication Verification",
        },
    ).json()

    acceptance_response = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    )
    verification_response = client.post(
        f"/api/auth/email-verifications/{invitation['token']}/verify",
    )
    events_response = client.get(
        f"/api/admin/communication-events?recipient_email={recipient_email}",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert acceptance_response.status_code == 200
    assert verification_response.status_code == 200
    assert events_response.status_code == 200
    assert [event["event_type"] for event in events_response.json()] == [
        "participant_invitation",
        "email_verification",
    ]


def test_regular_mutation_deadline_calculation_does_not_queue_deadline_reminder() -> None:
    client = TestClient(app)
    recipient_email = "communication-deadline@example.test"
    participant_token = verified_participant_token(client, recipient_email)

    mutation_response = submit_regular_address_mutation(client, participant_token)
    events_response = client.get(
        (
            "/api/admin/communication-events"
            f"?recipient_email={recipient_email}&event_type=deadline_reminder"
        ),
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert mutation_response.status_code == 201
    assert mutation_response.json()["participant_deadline"] == "2026-06-30"
    assert events_response.status_code == 200
    assert events_response.json() == []


def test_mutation_review_status_change_does_not_queue_status_update_email() -> None:
    client = TestClient(app)
    recipient_email = "communication-status@example.test"
    participant_token = verified_participant_token(client, recipient_email)
    mutation = submit_regular_address_mutation(client, participant_token).json()

    review_response = client.post(
        f"/api/admin/mutation-requests/{mutation['id']}/review-decision",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"decision": "approved"},
    )
    events_response = client.get(
        (
            "/api/admin/communication-events"
            f"?recipient_email={recipient_email}&event_type=mutation_status_update"
        ),
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert review_response.status_code == 200
    assert review_response.json()["status"] == "approved"
    assert events_response.status_code == 200
    assert events_response.json() == []
