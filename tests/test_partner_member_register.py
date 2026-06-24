from base64 import b64encode
import json

import pytest
from fastapi.testclient import TestClient

from sunterra_leg_portal import auth
from sunterra_leg_portal import main as portal
from sunterra_leg_portal.main import app


LEG_HEADERS = {"Authorization": "Bearer dev:leg_admin"}
PARTNER_HEADERS = {"Authorization": "Bearer dev:partner_admin"}


@pytest.fixture(autouse=True)
def reset_portal_state() -> None:
    for store in [
        portal.INVITATIONS,
        portal.COMMUNICATION_EVENTS,
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


def assert_keys_absent(value, forbidden_keys: set[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            assert key not in forbidden_keys
            assert_keys_absent(nested, forbidden_keys)
    elif isinstance(value, list):
        for item in value:
            assert_keys_absent(item, forbidden_keys)


def verified_participant_token(
    client: TestClient,
    *,
    email: str,
    display_name: str = "Partner Register Tester",
) -> str:
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers=LEG_HEADERS,
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
    *,
    quarter: str,
    submitted_on: str,
    street: str = "Registerweg 4",
) -> dict:
    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": quarter,
            "submitted_on": submitted_on,
            "new_address": {
                "street": street,
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    )
    assert response.status_code == 201

    return response.json()


def approve_mutation(client: TestClient, mutation_request_id: str) -> None:
    response = client.post(
        f"/api/admin/mutation-requests/{mutation_request_id}/review-decision",
        headers=LEG_HEADERS,
        json={"decision": "approved"},
    )
    assert response.status_code == 200


def package_mutations(client: TestClient, *, quarter: str) -> dict:
    response = client.post(
        "/api/admin/mutation-packages",
        headers=LEG_HEADERS,
        json={"quarter": quarter},
    )
    assert response.status_code == 201

    return response.json()


def test_partner_admin_can_view_basadingen_member_register_with_reporting_address_and_package_status() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        email="partner-register-member@example.test",
        display_name="Regina Register",
    )
    submitted = submit_regular_address_mutation(
        client,
        participant_token,
        quarter="2031-Q1",
        submitted_on="2030-12-31",
    )
    approve_mutation(client, submitted["id"])
    package = package_mutations(client, quarter="2031-Q1")

    response = client.get("/api/partner/member-register", headers=PARTNER_HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "leg_id": "basadingen",
        "leg_name": "SunTerra LEG Basadingen",
        "members": [
            {
                "participant_id": participant_token.removeprefix("dev:participant:"),
                "display_name": "Regina Register",
                "membership_status": "active",
                "reporting_address": {
                    "street": "Registerweg 4",
                    "postal_code": "8254",
                    "city": "Basadingen",
                    "country": "CH",
                },
                "latest_package_status": {
                    "package_id": package["package_id"],
                    "quarter": "2031-Q1",
                    "effective_date": "2031-04-01",
                    "status": "created",
                },
            },
        ],
    }


def test_partner_member_register_redacts_private_internal_consent_file_and_actor_data() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        email="partner-register-private@example.test",
        display_name="Rita Redacted",
    )
    participant_id = participant_token.removeprefix("dev:participant:")
    contact_response = client.patch(
        "/api/participants/me/contact-channels",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "phone_number": "+41 52 555 77 66",
            "preferred_contact_channel": "phone",
        },
    )
    assert contact_response.status_code == 200
    document = client.post(
        "/api/admin/document-versions",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_key": "portal_terms",
            "title": "Portal Nutzungsbedingungen",
            "version": "2031-02-01",
            "content": "private consent document content",
            "context": "participant_onboarding",
        },
    ).json()
    consent_response = client.post(
        "/api/participants/me/consent-evidence",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "document_version_id": document["id"],
            "context": "participant_onboarding",
            "accepted": True,
        },
    )
    assert consent_response.status_code == 201
    submitted = submit_regular_address_mutation(
        client,
        participant_token,
        quarter="2031-Q2",
        submitted_on="2031-03-31",
        street="Redaktionsweg 9",
    )
    evidence_response = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/file-evidence",
        headers=LEG_HEADERS,
        json={
            "document_type": "mutation_review_supporting_document",
            "purpose": "mutation_review",
            "version": "2031-04-01",
            "filename": "secret-proof.txt",
            "content_type": "text/plain",
            "content_base64": b64encode(b"secret file evidence").decode("ascii"),
        },
    )
    assert evidence_response.status_code == 201
    approve_mutation(client, submitted["id"])
    package = package_mutations(client, quarter="2031-Q2")
    status_response = client.post(
        f"/api/partner/mutation-packages/{package['package_id']}/status",
        headers=PARTNER_HEADERS,
        json={"status": "question", "reason": "private EW ticket"},
    )
    assert status_response.status_code == 200
    rejected = submit_regular_address_mutation(
        client,
        participant_token,
        quarter="2031-Q3",
        submitted_on="2031-06-30",
        street="Rejected Secret 1",
    )
    review_response = client.post(
        f"/api/admin/mutation-requests/{rejected['id']}/review-decision",
        headers=LEG_HEADERS,
        json={"decision": "rejected", "reason": "internal review reason"},
    )
    assert review_response.status_code == 200

    response = client.get("/api/partner/member-register", headers=PARTNER_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "leg_id": "basadingen",
        "leg_name": "SunTerra LEG Basadingen",
        "members": [
            {
                "participant_id": participant_id,
                "display_name": "Rita Redacted",
                "membership_status": "active",
                "reporting_address": {
                    "street": "Redaktionsweg 9",
                    "postal_code": "8254",
                    "city": "Basadingen",
                    "country": "CH",
                },
                "latest_package_status": {
                    "package_id": package["package_id"],
                    "quarter": "2031-Q2",
                    "effective_date": "2031-07-01",
                    "status": "question",
                },
            },
        ],
    }
    assert_keys_absent(
        payload,
        {
            "email",
            "phone_number",
            "preferred_contact_channel",
            "consent_evidence",
            "audit_events",
            "reviewed_at",
            "review",
            "review_reason",
            "file_evidence",
            "content_base64",
            "hash",
            "artifact_url",
            "artifact_urls",
            "actor_id",
            "reason",
            "reference",
        },
    )
    rendered_payload = json.dumps(payload, sort_keys=True)
    for prohibited_text in [
        "partner-register-private@example.test",
        "+41 52 555 77 66",
        "phone",
        "private consent document content",
        "secret-proof.txt",
        "secret file evidence",
        package["hash"],
        "dev-leg-admin",
        "dev-partner-admin",
        "private EW ticket",
        "Rejected Secret 1",
        "internal review reason",
    ]:
        assert prohibited_text not in rendered_payload


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer dev:participant",
        "Bearer dev:leg_admin",
        "Bearer dev:leg_admin",
    ],
)
def test_partner_member_register_denies_non_partner_roles(authorization: str) -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        email="partner-register-rbac@example.test",
    )
    submitted = submit_regular_address_mutation(
        client,
        participant_token,
        quarter="2031-Q4",
        submitted_on="2031-09-30",
    )
    approve_mutation(client, submitted["id"])
    package_mutations(client, quarter="2031-Q4")

    response = client.get(
        "/api/partner/member-register",
        headers={"Authorization": authorization},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Role is not allowed"}
