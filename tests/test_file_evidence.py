from base64 import b64encode
from hashlib import sha256

from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def verified_participant_token(client: TestClient, email: str) -> str:
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": email, "display_name": "File Evidence Tester"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    return accepted["access_token"]


def submit_regular_address_mutation(
    client: TestClient,
    participant_token: str,
) -> dict:
    response = client.post(
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

    return response.json()


def attach_mutation_file_evidence(
    client: TestClient,
    mutation_request_id: str,
    content: bytes,
) -> dict:
    response = client.post(
        f"/api/admin/mutation-requests/{mutation_request_id}/file-evidence",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_type": "mutation_review_supporting_document",
            "purpose": "mutation_review",
            "version": "2026-06-22",
            "filename": "address-proof.txt",
            "content_type": "text/plain",
            "content_base64": b64encode(content).decode("ascii"),
        },
    )

    return response.json()


def test_leg_admin_can_attach_configured_evidence_to_mutation_request() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "file-evidence-attach@example.test",
    )
    submitted = submit_regular_address_mutation(client, participant_token)
    content = b"Mutation review address proof"

    response = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/file-evidence",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_type": "mutation_review_supporting_document",
            "purpose": "mutation_review",
            "version": "2026-06-22",
            "filename": "address-proof.txt",
            "content_type": "text/plain",
            "content_base64": b64encode(content).decode("ascii"),
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload.pop("id")
    assert payload.pop("created_at")
    assert payload == {
        "mutation_request_id": submitted["id"],
        "participant_id": participant_token.removeprefix("dev:participant:"),
        "document_type": "mutation_review_supporting_document",
        "purpose": "mutation_review",
        "version": "2026-06-22",
        "filename": "address-proof.txt",
        "content_type": "text/plain",
        "sha256_hash": sha256(content).hexdigest(),
        "access_protection": "mutation_review_owner_and_leg_admin",
        "retention_status": "retained_for_mutation_review",
    }


def test_free_form_file_evidence_document_type_and_purpose_are_rejected() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "file-evidence-free-form@example.test",
    )
    submitted = submit_regular_address_mutation(client, participant_token)

    response = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/file-evidence",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_type": "miscellaneous_upload",
            "purpose": "free_form_archive",
            "version": "draft",
            "filename": "notes.txt",
            "content_type": "text/plain",
            "content_base64": b64encode(b"uncontrolled notes").decode("ascii"),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "File evidence document type and purpose are not configured",
    }


def test_file_evidence_metadata_and_content_are_role_scoped() -> None:
    client = TestClient(app)
    owner_token = verified_participant_token(
        client,
        "file-evidence-owner@example.test",
    )
    other_participant_token = verified_participant_token(
        client,
        "file-evidence-other-participant@example.test",
    )
    submitted = submit_regular_address_mutation(client, owner_token)
    content = b"Owner-visible mutation review evidence"
    attached = attach_mutation_file_evidence(client, submitted["id"], content)
    metadata_path = (
        f"/api/mutation-requests/{submitted['id']}/file-evidence/{attached['id']}"
    )
    content_path = f"{metadata_path}/content"

    for token in [owner_token, "dev:leg_admin"]:
        metadata_response = client.get(
            metadata_path,
            headers={"Authorization": f"Bearer {token}"},
        )
        content_response = client.get(
            content_path,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert metadata_response.status_code == 200
        assert metadata_response.json() == attached
        assert content_response.status_code == 200
        assert content_response.json() == {
            **attached,
            "content_base64": b64encode(content).decode("ascii"),
        }

    for token in ["dev:partner_admin", other_participant_token]:
        metadata_response = client.get(
            metadata_path,
            headers={"Authorization": f"Bearer {token}"},
        )
        content_response = client.get(
            content_path,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert metadata_response.status_code == 403
        assert content_response.status_code == 403
