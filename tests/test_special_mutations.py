from fastapi.testclient import TestClient
import pytest

from sunterra_leg_portal.main import app


SPECIAL_MUTATION_TYPES = [
    "move_out",
    "death",
    "owner_tenant_change",
    "meter_point_error",
    "municipality_utility_correction",
]


def verified_participant_token(client: TestClient, email: str) -> str:
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": email, "display_name": "Special Mutation Tester"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    return accepted["access_token"]


def submit_special_mutation(
    client: TestClient,
    participant_token: str,
    *,
    mutation_type: str = "move_out",
    event_date: str = "2026-07-12",
    reason: str = "Auszug wegen Wohnungswechsel.",
):
    return client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": mutation_type,
            "mode": "special",
            "event_date": event_date,
            "reason": reason,
        },
    )


def test_verified_participant_can_submit_special_move_out_mutation() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "special-move-out@example.test",
    )

    response = submit_special_mutation(client, participant_token)

    assert response.status_code == 201
    payload = response.json()
    assert payload.pop("id")
    assert payload.pop("submitted_at")
    assert payload == {
        "participant_id": participant_token.removeprefix("dev:participant:"),
        "leg_id": "basadingen",
        "mutation_type": "move_out",
        "mode": "special",
        "status": "submitted",
        "quarter": None,
        "quarter_end": None,
        "participant_deadline": None,
        "effective_date": "2026-07-12",
        "new_address": None,
        "mutation_details": {
            "reason": "Auszug wegen Wohnungswechsel.",
            "event_date": "2026-07-12",
        },
    }

    history_response = client.get(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
    )

    assert history_response.status_code == 200
    assert history_response.json() == [
        {
            **payload,
            "id": response.json()["id"],
            "submitted_at": response.json()["submitted_at"],
            "reviewed_at": None,
            "review_reason": None,
            "audit_events": [],
        },
    ]


def test_leg_admin_can_review_special_mutation_with_reason_context() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "special-admin-review@example.test",
    )
    submitted = submit_special_mutation(
        client,
        participant_token,
        mutation_type="death",
        event_date="2026-08-03",
        reason="Todesfall durch Angehoerige gemeldet.",
    ).json()

    inbox_response = client.get(
        "/api/admin/mutation-requests?status=submitted",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert inbox_response.status_code == 200
    admin_record = next(
        item for item in inbox_response.json() if item["id"] == submitted["id"]
    )
    assert admin_record == {
        **submitted,
        "participant": {
            "participant_id": participant_token.removeprefix("dev:participant:"),
            "display_name": "Special Mutation Tester",
            "email": "special-admin-review@example.test",
        },
        "reviewed_at": None,
        "review_reason": None,
        "audit_events": [],
    }
    assert admin_record["mode"] == "special"
    assert admin_record["mutation_type"] == "death"
    assert admin_record["mutation_details"] == {
        "reason": "Todesfall durch Angehoerige gemeldet.",
        "event_date": "2026-08-03",
    }

    review_response = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"decision": "approved"},
    )

    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["id"] == submitted["id"]
    assert reviewed["status"] == "approved"
    assert reviewed["mode"] == "special"
    assert reviewed["mutation_details"] == {
        "reason": "Todesfall durch Angehoerige gemeldet.",
        "event_date": "2026-08-03",
    }
    assert reviewed["audit_events"][0]["action"] == "mutation_request.approved"

    participant_response = client.get(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
    )

    assert participant_response.status_code == 200
    participant_record = participant_response.json()[0]
    assert participant_record["id"] == submitted["id"]
    assert participant_record["status"] == "approved"
    assert participant_record["reviewed_at"]
    assert participant_record["mutation_details"] == {
        "reason": "Todesfall durch Angehoerige gemeldet.",
        "event_date": "2026-08-03",
    }


@pytest.mark.parametrize("mutation_type", SPECIAL_MUTATION_TYPES)
def test_each_supported_special_mutation_type_can_be_submitted(
    mutation_type: str,
) -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        f"special-{mutation_type}@example.test",
    )

    response = submit_special_mutation(
        client,
        participant_token,
        mutation_type=mutation_type,
        event_date="2026-09-14",
        reason=f"Begruendung fuer {mutation_type}.",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["mutation_type"] == mutation_type
    assert payload["mode"] == "special"
    assert payload["quarter"] is None
    assert payload["quarter_end"] is None
    assert payload["participant_deadline"] is None
    assert payload["effective_date"] == "2026-09-14"
    assert payload["mutation_details"] == {
        "reason": f"Begruendung fuer {mutation_type}.",
        "event_date": "2026-09-14",
    }


@pytest.mark.parametrize("mutation_type", SPECIAL_MUTATION_TYPES)
def test_special_mutation_requires_reason(mutation_type: str) -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        f"special-{mutation_type}-missing-reason@example.test",
    )

    response = submit_special_mutation(
        client,
        participant_token,
        mutation_type=mutation_type,
        event_date="2026-09-14",
        reason="   ",
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Special mutation requires reason"}


def test_special_mutation_requires_event_date() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "special-missing-event-date@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "meter_point_error",
            "mode": "special",
            "reason": "Messpunkt war im Register falsch zugeordnet.",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Special mutation requires event_date"}
