from base64 import b64encode
import pytest
from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


LEG_HEADERS = {"Authorization": "Bearer dev:leg_admin"}
PARTNER_HEADERS = {"Authorization": "Bearer dev:partner_admin"}


def assert_keys_absent(value, forbidden_keys: set[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            assert key not in forbidden_keys
            assert_keys_absent(nested, forbidden_keys)
    elif isinstance(value, list):
        for item in value:
            assert_keys_absent(item, forbidden_keys)


def verified_participant_token(client: TestClient, email: str) -> str:
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers=LEG_HEADERS,
        json={"email": email, "display_name": "Partner Workflow Tester"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    return accepted["access_token"]


def create_approved_package(
    client: TestClient,
    *,
    email: str,
    quarter: str,
    submitted_on: str,
) -> dict:
    participant_token = verified_participant_token(client, email)
    submitted = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": quarter,
            "submitted_on": submitted_on,
            "new_address": {
                "street": "Partnerweg 13",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    ).json()
    approved = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers=LEG_HEADERS,
        json={"decision": "approved"},
    )
    package_response = client.post(
        "/api/admin/mutation-packages",
        headers=LEG_HEADERS,
        json={"quarter": quarter},
    )

    assert approved.status_code == 200
    assert package_response.status_code == 201

    return package_response.json()


def test_partner_admin_can_list_redacted_mutation_package_summary() -> None:
    client = TestClient(app)
    package = create_approved_package(
        client,
        email="partner-package-list@example.test",
        quarter="2029-Q2",
        submitted_on="2029-03-31",
    )

    response = client.get("/api/partner/mutation-packages", headers=PARTNER_HEADERS)

    assert response.status_code == 200
    summaries = [
        summary
        for summary in response.json()
        if summary["package_id"] == package["package_id"]
    ]
    assert summaries == [
        {
            "package_id": package["package_id"],
            "leg_id": "basadingen",
            "quarter": "2029-Q2",
            "effective_date": "2029-07-01",
            "generated_at": package["generated_at"],
            "record_count": 1,
            "current_status": "created",
            "status_updated_at": package["generated_at"],
        },
    ]
    assert "hash" not in summaries[0]
    assert "records" not in summaries[0]
    assert "status_history" not in summaries[0]


def test_partner_status_update_is_leg_visible_without_changing_json_artifact() -> None:
    client = TestClient(app)
    package = create_approved_package(
        client,
        email="partner-package-received@example.test",
        quarter="2029-Q3",
        submitted_on="2029-06-30",
    )
    artifact_before = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/json",
        headers=LEG_HEADERS,
    ).json()

    response = client.post(
        f"/api/partner/mutation-packages/{package['package_id']}/status",
        headers=PARTNER_HEADERS,
        json={"status": "received"},
    )

    assert response.status_code == 200
    partner_payload = response.json()
    assert partner_payload["current_status"] == "received"
    assert partner_payload["status_history"][0] == {
        "status": "created",
        "actor_role": "leg_admin",
        "created_at": package["generated_at"],
        "reference": None,
        "reason": None,
    }
    partner_status = partner_payload["status_history"][1]
    assert partner_status == {
        "status": "received",
        "actor_role": "partner_admin",
        "created_at": partner_status["created_at"],
        "reference": None,
        "reason": None,
    }
    assert "actor_id" not in partner_status

    admin_response = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}",
        headers=LEG_HEADERS,
    )
    artifact_after = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/json",
        headers=LEG_HEADERS,
    ).json()

    assert admin_response.status_code == 200
    admin_payload = admin_response.json()
    assert admin_payload["current_status"] == "received"
    assert admin_payload["status_history"][1] == {
        "status": "received",
        "actor_id": "dev-partner-admin",
        "actor_role": "partner_admin",
        "created_at": partner_status["created_at"],
        "reference": None,
        "reason": None,
    }
    assert artifact_after == artifact_before


@pytest.mark.parametrize(
    ("status_payload", "expected_status"),
    [
        ({"status": "received"}, {"status": "received"}),
        ({"status": "in_review"}, {"status": "in_review"}),
        ({"status": "processed"}, {"status": "processed"}),
        (
            {"status": "question", "reference": "EW-RF-2042"},
            {"status": "question", "reference": "EW-RF-2042"},
        ),
        (
            {
                "status": "technically_not_possible",
                "reason": "Zaehlerpunkt fehlt im EW-System",
            },
            {
                "status": "technically_not_possible",
                "reason": "Zaehlerpunkt fehlt im EW-System",
            },
        ),
    ],
)
def test_partner_admin_can_set_supported_statuses(
    status_payload: dict,
    expected_status: dict,
) -> None:
    client = TestClient(app)
    package = create_approved_package(
        client,
        email=f"partner-package-{status_payload['status']}@example.test",
        quarter="2029-Q4",
        submitted_on="2029-09-30",
    )

    response = client.post(
        f"/api/partner/mutation-packages/{package['package_id']}/status",
        headers=PARTNER_HEADERS,
        json=status_payload,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_status"] == expected_status["status"]
    status_event = payload["status_history"][-1]
    assert status_event == {
        "status": expected_status["status"],
        "actor_role": "partner_admin",
        "created_at": status_event["created_at"],
        "reference": expected_status.get("reference"),
        "reason": expected_status.get("reason"),
    }


@pytest.mark.parametrize("status", ["question", "technically_not_possible"])
def test_follow_up_statuses_require_reference_or_reason(status: str) -> None:
    client = TestClient(app)
    package = create_approved_package(
        client,
        email=f"partner-package-{status}-missing-context@example.test",
        quarter="2030-Q1",
        submitted_on="2029-12-31",
    )

    response = client.post(
        f"/api/partner/mutation-packages/{package['package_id']}/status",
        headers=PARTNER_HEADERS,
        json={"status": status, "reference": "  ", "reason": ""},
    )
    metadata_response = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}",
        headers=LEG_HEADERS,
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Status question or technically_not_possible requires a reference or reason",
    }
    assert metadata_response.status_code == 200
    assert metadata_response.json()["current_status"] == "created"
    assert len(metadata_response.json()["status_history"]) == 1


def test_partner_admin_can_inspect_redacted_package_detail() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "partner-package-detail@example.test",
    )
    document = client.post(
        "/api/admin/document-versions",
        headers={"Authorization": "Bearer dev:platform_admin"},
        json={
            "document_key": "portal_terms",
            "title": "Portal Nutzungsbedingungen",
            "version": "2030-06-01",
            "content": "Interne Zustimmung darf nicht ins Partnerpaket.",
            "context": "participant_onboarding",
        },
    ).json()
    client.post(
        "/api/participants/me/consent-evidence",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "document_version_id": document["id"],
            "context": "participant_onboarding",
            "accepted": True,
        },
    )
    submitted = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": "2030-Q2",
            "submitted_on": "2030-03-31",
            "new_address": {
                "street": "Detailweg 8",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    ).json()
    client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/file-evidence",
        headers=LEG_HEADERS,
        json={
            "document_type": "mutation_review_supporting_document",
            "purpose": "mutation_review",
            "version": "2030-06-01",
            "filename": "internal-proof.txt",
            "content_type": "text/plain",
            "content_base64": b64encode(b"internal review proof").decode("ascii"),
        },
    )
    client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers=LEG_HEADERS,
        json={"decision": "approved"},
    )
    package = client.post(
        "/api/admin/mutation-packages",
        headers=LEG_HEADERS,
        json={"quarter": "2030-Q2"},
    ).json()
    status_response = client.post(
        f"/api/partner/mutation-packages/{package['package_id']}/status",
        headers=PARTNER_HEADERS,
        json={"status": "question", "reference": "EW-RF-3030"},
    ).json()

    response = client.get(
        f"/api/partner/mutation-packages/{package['package_id']}",
        headers=PARTNER_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "package_id": package["package_id"],
        "leg_id": "basadingen",
        "quarter": "2030-Q2",
        "effective_date": "2030-07-01",
        "generated_at": package["generated_at"],
        "record_count": 1,
        "current_status": "question",
        "status_updated_at": status_response["status_history"][-1]["created_at"],
        "records": [
            {
                "mutation_request_id": submitted["id"],
                "participant_id": participant_token.removeprefix("dev:participant:"),
                "mutation_type": "address",
                "mode": "regular",
                "effective_date": "2030-07-01",
                "new_address": {
                    "street": "Detailweg 8",
                    "postal_code": "8254",
                    "city": "Basadingen",
                    "country": "CH",
                },
            },
        ],
        "status_history": [
            {
                "status": "created",
                "actor_role": "leg_admin",
                "created_at": package["generated_at"],
                "reference": None,
                "reason": None,
            },
            {
                "status": "question",
                "actor_role": "partner_admin",
                "created_at": status_response["status_history"][-1]["created_at"],
                "reference": "EW-RF-3030",
                "reason": None,
            },
        ],
    }
    assert_keys_absent(
        payload,
        {
            "hash",
            "actor_id",
            "reviewed_at",
            "review_reason",
            "audit_events",
            "consent_evidence",
            "file_evidence",
            "content_base64",
        },
    )


def test_partner_status_update_is_metadata_only() -> None:
    client = TestClient(app)
    participant_email = "partner-package-metadata-only@example.test"
    package = create_approved_package(
        client,
        email=participant_email,
        quarter="2030-Q3",
        submitted_on="2030-06-30",
    )
    json_before = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/json",
        headers=LEG_HEADERS,
    ).content
    csv_before = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/csv",
        headers=LEG_HEADERS,
    ).content
    pdf_before = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/pdf",
        headers=LEG_HEADERS,
    ).content

    response = client.post(
        f"/api/partner/mutation-packages/{package['package_id']}/status",
        headers=PARTNER_HEADERS,
        json={"status": "processed"},
    )
    events_response = client.get(
        (
            "/api/admin/communication-events"
            f"?recipient_email={participant_email}&event_type=mutation_status_update"
        ),
        headers=LEG_HEADERS,
    )

    assert response.status_code == 200
    assert events_response.status_code == 200
    assert events_response.json() == []
    assert (
        client.get(
            f"/api/admin/mutation-packages/{package['package_id']}/json",
            headers=LEG_HEADERS,
        ).content
        == json_before
    )
    assert (
        client.get(
            f"/api/admin/mutation-packages/{package['package_id']}/csv",
            headers=LEG_HEADERS,
        ).content
        == csv_before
    )
    assert (
        client.get(
            f"/api/admin/mutation-packages/{package['package_id']}/pdf",
            headers=LEG_HEADERS,
        ).content
        == pdf_before
    )
