from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def verified_participant_token(client: TestClient, email: str) -> str:
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": email, "display_name": "Address Mutation Tester"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    return accepted["access_token"]


def submit_regular_address_mutation(
    client: TestClient,
    participant_token: str,
    *,
    requested_quarter: str,
    submitted_on: str,
):
    return client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": requested_quarter,
            "submitted_on": submitted_on,
            "new_address": {
                "street": "Hauptstrasse 7",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    )


def test_verified_participant_can_submit_regular_address_mutation() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-address-submit@example.test",
    )

    response = submit_regular_address_mutation(
        client,
        participant_token,
        requested_quarter="2026-Q3",
        submitted_on="2026-06-15",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload.pop("id")
    assert payload.pop("submitted_at")
    assert payload == {
        "participant_id": participant_token.removeprefix("dev:participant:"),
        "leg_id": "basadingen",
        "mutation_type": "address",
        "mode": "regular",
        "status": "submitted",
        "quarter": "2026-Q3",
        "quarter_end": "2026-09-30",
        "participant_deadline": "2026-06-30",
        "effective_date": "2026-10-01",
        "new_address": {
            "street": "Hauptstrasse 7",
            "postal_code": "8254",
            "city": "Basadingen",
            "country": "CH",
        },
    }


def test_participant_can_view_own_mutation_status_and_effective_date() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-address-history@example.test",
    )
    submitted = submit_regular_address_mutation(
        client,
        participant_token,
        requested_quarter="2026-Q3",
        submitted_on="2026-06-15",
    ).json()

    response = client.get(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            **submitted,
            "status": "submitted",
            "effective_date": "2026-10-01",
        },
    ]


def test_regular_address_mutation_uses_q1_deadline_calculation() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-address-q1@example.test",
    )

    response = submit_regular_address_mutation(
        client,
        participant_token,
        requested_quarter="2026-Q1",
        submitted_on="2025-12-31",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["quarter"] == "2026-Q1"
    assert payload["participant_deadline"] == "2025-12-31"
    assert payload["quarter_end"] == "2026-03-31"
    assert payload["effective_date"] == "2026-04-01"


def test_regular_address_mutation_uses_q2_deadline_calculation() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-address-q2@example.test",
    )

    response = submit_regular_address_mutation(
        client,
        participant_token,
        requested_quarter="2026-Q2",
        submitted_on="2026-03-31",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["quarter"] == "2026-Q2"
    assert payload["participant_deadline"] == "2026-03-31"
    assert payload["quarter_end"] == "2026-06-30"
    assert payload["effective_date"] == "2026-07-01"


def test_regular_address_mutation_uses_q4_deadline_calculation() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-address-q4@example.test",
    )

    response = submit_regular_address_mutation(
        client,
        participant_token,
        requested_quarter="2026-Q4",
        submitted_on="2026-09-30",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["quarter"] == "2026-Q4"
    assert payload["participant_deadline"] == "2026-09-30"
    assert payload["quarter_end"] == "2026-12-31"
    assert payload["effective_date"] == "2027-01-01"


def test_regular_address_mutation_calculates_deadlines_for_later_years() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-address-future-year@example.test",
    )

    response = submit_regular_address_mutation(
        client,
        participant_token,
        requested_quarter="2027-Q2",
        submitted_on="2027-03-31",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["quarter"] == "2027-Q2"
    assert payload["participant_deadline"] == "2027-03-31"
    assert payload["quarter_end"] == "2027-06-30"
    assert payload["effective_date"] == "2027-07-01"


def test_late_regular_address_mutation_is_rejected() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-address-late@example.test",
    )

    response = submit_regular_address_mutation(
        client,
        participant_token,
        requested_quarter="2026-Q3",
        submitted_on="2026-07-01",
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "Regular address mutation for 2026-Q3 must be submitted by "
            "participant deadline 2026-06-30"
        ),
    }


def test_only_regular_address_mutations_are_accepted_in_first_mutation_slice() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-address-type-guard@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "role",
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

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Only regular address mutations are supported",
    }


def test_invalid_requested_quarter_is_rejected() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-address-invalid-quarter@example.test",
    )

    response = submit_regular_address_mutation(
        client,
        participant_token,
        requested_quarter="2026-Q5",
        submitted_on="2026-06-15",
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Requested quarter must use YYYY-Q1 through YYYY-Q4",
    }
