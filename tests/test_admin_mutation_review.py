from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def verified_participant_token(
    client: TestClient,
    email: str,
    display_name: str = "Address Mutation Tester",
) -> str:
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": email, "display_name": display_name},
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


def test_leg_admin_can_view_pending_submitted_regular_address_mutations_for_their_leg() -> None:
    client = TestClient(app)
    participant_email = "admin-inbox-regular-address@example.test"
    participant_token = verified_participant_token(
        client,
        participant_email,
        display_name="Anna Admin Inbox",
    )
    submitted = submit_regular_address_mutation(client, participant_token).json()

    response = client.get(
        "/api/admin/mutation-requests?status=submitted",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert response.status_code == 200
    records = response.json()
    record = next(item for item in records if item["id"] == submitted["id"])
    assert record == {
        **submitted,
        "participant": {
            "participant_id": participant_token.removeprefix("dev:participant:"),
            "display_name": "Anna Admin Inbox",
            "email": participant_email,
        },
        "audit_events": [],
        "reviewed_at": None,
        "review_reason": None,
    }


def test_leg_admin_can_approve_submitted_mutation_request() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "admin-approve-regular-address@example.test",
    )
    submitted = submit_regular_address_mutation(client, participant_token).json()

    response = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"decision": "approved"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == submitted["id"]
    assert payload["status"] == "approved"
    assert payload["reviewed_at"]
    assert payload["review_reason"] is None


def test_approved_decision_is_visible_in_participant_and_admin_histories() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "admin-approve-history@example.test",
    )
    submitted = submit_regular_address_mutation(client, participant_token).json()
    client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"decision": "approved"},
    )

    participant_response = client.get(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
    )
    admin_response = client.get(
        "/api/admin/mutation-requests?status=approved",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert participant_response.status_code == 200
    participant_record = participant_response.json()[0]
    assert "participant" not in participant_record
    assert participant_record["id"] == submitted["id"]
    assert participant_record["status"] == "approved"
    assert participant_record["reviewed_at"]
    assert participant_record["review_reason"] is None
    participant_audit_event = participant_record["audit_events"][0]
    assert participant_audit_event["id"]
    assert participant_audit_event["created_at"]
    assert participant_audit_event == {
        "id": participant_audit_event["id"],
        "action": "mutation_request.approved",
        "actor_role": "leg_admin",
        "created_at": participant_audit_event["created_at"],
        "from_status": "submitted",
        "to_status": "approved",
        "reason": None,
    }

    assert admin_response.status_code == 200
    admin_record = next(
        item for item in admin_response.json() if item["id"] == submitted["id"]
    )
    assert admin_record["participant"]["participant_id"] == participant_token.removeprefix(
        "dev:participant:",
    )
    assert admin_record["audit_events"] == [participant_audit_event]


def test_leg_admin_can_reject_submitted_mutation_request_with_reason() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "admin-reject-regular-address@example.test",
    )
    submitted = submit_regular_address_mutation(client, participant_token).json()

    response = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "decision": "rejected",
            "reason": "Adresse stimmt nicht mit dem Netzanschluss ueberein.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == submitted["id"]
    assert payload["status"] == "rejected"
    assert payload["review_reason"] == (
        "Adresse stimmt nicht mit dem Netzanschluss ueberein."
    )
    audit_event = payload["audit_events"][0]
    assert audit_event["action"] == "mutation_request.rejected"
    assert audit_event["actor_role"] == "leg_admin"
    assert audit_event["from_status"] == "submitted"
    assert audit_event["to_status"] == "rejected"
    assert audit_event["reason"] == "Adresse stimmt nicht mit dem Netzanschluss ueberein."


def test_rejecting_without_reason_is_rejected() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "admin-reject-without-reason@example.test",
    )
    submitted = submit_regular_address_mutation(client, participant_token).json()

    response = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"decision": "rejected"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Rejecting a mutation request requires a reason",
    }
    admin_response = client.get(
        "/api/admin/mutation-requests?status=submitted",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )
    record = next(item for item in admin_response.json() if item["id"] == submitted["id"])
    assert record["status"] == "submitted"
    assert record["reviewed_at"] is None
    assert record["audit_events"] == []


def test_non_leg_admins_cannot_review_mutation_requests() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "admin-review-unauthorized@example.test",
    )
    submitted = submit_regular_address_mutation(client, participant_token).json()

    for token in [
        participant_token,
        "dev:partner_admin",
        "dev:platform_admin",
    ]:
        response = client.post(
            f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
            headers={"Authorization": f"Bearer {token}"},
            json={"decision": "approved"},
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "Role is not allowed"}

    admin_response = client.get(
        "/api/admin/mutation-requests?status=submitted",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )
    record = next(item for item in admin_response.json() if item["id"] == submitted["id"])
    assert record["status"] == "submitted"
    assert record["audit_events"] == []


def test_reviewed_mutation_request_cannot_be_reviewed_again() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "admin-review-once@example.test",
    )
    submitted = submit_regular_address_mutation(client, participant_token).json()
    first_response = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"decision": "approved"},
    )

    second_response = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "decision": "rejected",
            "reason": "Nachtraegliche Korrektur ist nicht erlaubt.",
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 400
    assert second_response.json() == {
        "detail": "Mutation request has already been reviewed",
    }
    admin_response = client.get(
        "/api/admin/mutation-requests?status=approved",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )
    record = next(item for item in admin_response.json() if item["id"] == submitted["id"])
    assert record["status"] == "approved"
    assert record["review_reason"] is None
    assert len(record["audit_events"]) == 1
