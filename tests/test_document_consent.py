from fastapi.testclient import TestClient
import pytest

from sunterra_leg_portal import main as portal
from sunterra_leg_portal.main import app


@pytest.fixture(autouse=True)
def preserve_document_consent_state():
    document_versions = dict(portal.DOCUMENT_VERSIONS)
    consent_evidence = {
        participant_id: list(evidence)
        for participant_id, evidence in portal.CONSENT_EVIDENCE.items()
    }

    yield

    portal.DOCUMENT_VERSIONS.clear()
    portal.DOCUMENT_VERSIONS.update(document_versions)
    portal.CONSENT_EVIDENCE.clear()
    portal.CONSENT_EVIDENCE.update(consent_evidence)


def verified_participant_token(client: TestClient, email: str) -> tuple[str, str]:
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": email, "display_name": "Consent Tester"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")
    setup = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {accepted['access_token']}"},
        json={"display_name": "Consent Tester", "password": "Start123!"},
    )

    assert setup.status_code == 200
    setup_payload = setup.json()
    return setup_payload["access_token"], setup_payload["user"]["id"]


def publish_document_version(
    client: TestClient,
    *,
    document_key: str,
    title: str,
    version: str,
    content: str,
) -> dict:
    return client.post(
        "/api/admin/document-versions",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_key": document_key,
            "title": title,
            "version": version,
            "content": content,
            "context": "participant_onboarding",
        },
    ).json()


def accept_document(client: TestClient, participant_token: str, document_id: str) -> None:
    response = client.post(
        "/api/participants/me/consent-evidence",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "document_version_id": document_id,
            "context": "participant_onboarding",
            "accepted": True,
        },
    )

    assert response.status_code == 201


def test_leg_admin_can_publish_document_version_for_portal_use() -> None:
    response = TestClient(app).post(
        "/api/admin/document-versions",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_key": "portal_terms",
            "title": "Portal Nutzungsbedingungen",
            "version": "2026-06-22",
            "content": "Teilnahmebedingungen fuer das SunTerra LEG Portal.",
            "context": "participant_onboarding",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload.pop("id")
    assert payload.pop("document_hash")
    assert payload.pop("published_at")
    assert payload == {
        "document_key": "portal_terms",
        "title": "Portal Nutzungsbedingungen",
        "version": "2026-06-22",
        "context": "participant_onboarding",
    }


def test_verified_participant_can_view_current_document_before_consent() -> None:
    client = TestClient(app)
    participant_token, _participant_id = verified_participant_token(
        client,
        "view-current-doc@example.test",
    )
    published = client.post(
        "/api/admin/document-versions",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_key": "portal_terms",
            "title": "Portal Nutzungsbedingungen",
            "version": "2026-06-23",
            "content": "Aktuelle Teilnahmebedingungen vor Zustimmung.",
            "context": "participant_onboarding",
        },
    ).json()

    response = client.get(
        "/api/documents/current?document_key=portal_terms",
        headers={"Authorization": f"Bearer {participant_token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": published["id"],
        "document_key": "portal_terms",
        "title": "Portal Nutzungsbedingungen",
        "version": "2026-06-23",
        "content": "Aktuelle Teilnahmebedingungen vor Zustimmung.",
        "document_hash": published["document_hash"],
        "context": "participant_onboarding",
        "published_at": published["published_at"],
    }


def test_participant_consent_records_exact_document_version_and_hash() -> None:
    client = TestClient(app)
    participant_token, participant_id = verified_participant_token(
        client,
        "consent-version-hash@example.test",
    )
    first_document = client.post(
        "/api/admin/document-versions",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_key": "portal_terms",
            "title": "Portal Nutzungsbedingungen",
            "version": "2026-06-24",
            "content": "Erste verbindliche Version.",
            "context": "participant_onboarding",
        },
    ).json()
    client.post(
        "/api/admin/document-versions",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_key": "portal_terms",
            "title": "Portal Nutzungsbedingungen",
            "version": "2026-06-25",
            "content": "Neuere Version, noch nicht akzeptiert.",
            "context": "participant_onboarding",
        },
    )

    response = client.post(
        "/api/participants/me/consent-evidence",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "document_version_id": first_document["id"],
            "context": "participant_onboarding",
            "accepted": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload.pop("accepted_at")
    assert payload == {
        "participant_id": participant_id,
        "document_version_id": first_document["id"],
        "document_key": "portal_terms",
        "version": "2026-06-24",
        "document_hash": first_document["document_hash"],
        "context": "participant_onboarding",
    }


def test_current_required_document_lookup_ignores_other_document_contexts() -> None:
    client = TestClient(app)
    participant_token, _participant_id = verified_participant_token(
        client,
        "context-scoped-current-document@example.test",
    )
    required_document = publish_document_version(
        client,
        document_key="portal_terms",
        title="Portal-Nutzungsbedingungen",
        version="2026-06-24",
        content="Teilnahmebedingungen fuer das Portal.",
    )
    client.post(
        "/api/admin/document-versions",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_key": "portal_terms",
            "title": "Interne Portal-Hinweise",
            "version": "2026-06-25",
            "content": "Interner Kontext, nicht fuer Teilnehmerzustimmung.",
            "context": "internal_review",
        },
    )

    response = client.get(
        "/api/documents/current?document_key=portal_terms",
        headers={"Authorization": f"Bearer {participant_token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == required_document["id"]
    assert response.json()["context"] == "participant_onboarding"


def test_participant_can_view_own_consent_history() -> None:
    client = TestClient(app)
    first_token, _first_participant_id = verified_participant_token(
        client,
        "own-history@example.test",
    )
    second_token, _second_participant_id = verified_participant_token(
        client,
        "foreign-history@example.test",
    )
    first_document = client.post(
        "/api/admin/document-versions",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_key": "portal_terms",
            "title": "Portal Nutzungsbedingungen",
            "version": "2026-06-26",
            "content": "Historie fuer ersten Teilnehmer.",
            "context": "participant_onboarding",
        },
    ).json()
    second_document = client.post(
        "/api/admin/document-versions",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "document_key": "portal_terms",
            "title": "Portal Nutzungsbedingungen",
            "version": "2026-06-27",
            "content": "Historie fuer zweiten Teilnehmer.",
            "context": "participant_onboarding",
        },
    ).json()
    first_evidence = client.post(
        "/api/participants/me/consent-evidence",
        headers={"Authorization": f"Bearer {first_token}"},
        json={
            "document_version_id": first_document["id"],
            "context": "participant_onboarding",
            "accepted": True,
        },
    ).json()
    client.post(
        "/api/participants/me/consent-evidence",
        headers={"Authorization": f"Bearer {second_token}"},
        json={
            "document_version_id": second_document["id"],
            "context": "participant_onboarding",
            "accepted": True,
        },
    )

    response = client.get(
        "/api/participants/me/consent-evidence",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert response.status_code == 200
    assert response.json() == [first_evidence]


def test_participant_cannot_submit_binding_mutation_until_all_required_documents_are_accepted() -> None:
    client = TestClient(app)
    participant_token, participant_id = verified_participant_token(
        client,
        "required-documents-before-mutation@example.test",
    )
    privacy_notice = publish_document_version(
        client,
        document_key="privacy_notice",
        title="Datenschutzhinweis",
        version="2026-06-24",
        content="Datenschutzhinweis fuer den SunTerra LEG Pilot.",
    )
    portal_terms = publish_document_version(
        client,
        document_key="portal_terms",
        title="Portal-Nutzungsbedingungen",
        version="2026-06-24",
        content="Nutzungsbedingungen fuer das SunTerra LEG Portal.",
    )
    leg_contract = publish_document_version(
        client,
        document_key="leg_contract",
        title="LEG-Vertrag",
        version="2026-06-24",
        content="LEG-Vertrag fuer die verbindliche Teilnahme.",
    )
    accept_document(client, participant_token, privacy_notice["id"])
    accept_document(client, participant_token, portal_terms["id"])

    blocked = client.post(
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

    assert blocked.status_code == 403
    assert blocked.json() == {
        "detail": (
            "Required documents must be accepted before submitting binding "
            "mutations: leg_contract"
        ),
    }

    accept_document(client, participant_token, leg_contract["id"])

    submitted = client.post(
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

    assert submitted.status_code == 201
    assert submitted.json()["participant_id"] == participant_id


def test_participant_cannot_submit_binding_mutation_when_required_document_suite_is_incomplete() -> None:
    client = TestClient(app)
    participant_token, _participant_id = verified_participant_token(
        client,
        "partial-required-documents-before-mutation@example.test",
    )
    privacy_notice = publish_document_version(
        client,
        document_key="privacy_notice",
        title="Datenschutzhinweis",
        version="2026-06-24",
        content="Datenschutzhinweis fuer den SunTerra LEG Pilot.",
    )
    portal_terms = publish_document_version(
        client,
        document_key="portal_terms",
        title="Portal-Nutzungsbedingungen",
        version="2026-06-24",
        content="Nutzungsbedingungen fuer das SunTerra LEG Portal.",
    )
    accept_document(client, participant_token, privacy_notice["id"])
    accept_document(client, participant_token, portal_terms["id"])

    blocked = client.post(
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

    assert blocked.status_code == 403
    assert blocked.json() == {
        "detail": (
            "Required documents must be accepted before submitting binding "
            "mutations: leg_contract"
        ),
    }


def test_participant_membership_stays_pending_until_required_documents_are_accepted() -> None:
    client = TestClient(app)
    participant_token, _participant_id = verified_participant_token(
        client,
        "required-documents-before-active-membership@example.test",
    )
    documents = [
        publish_document_version(
            client,
            document_key="privacy_notice",
            title="Datenschutzhinweis",
            version="2026-06-24",
            content="Datenschutzhinweis fuer die Mitgliedschaft.",
        ),
        publish_document_version(
            client,
            document_key="portal_terms",
            title="Portal-Nutzungsbedingungen",
            version="2026-06-24",
            content="Portal-Nutzungsbedingungen fuer die Mitgliedschaft.",
        ),
        publish_document_version(
            client,
            document_key="leg_contract",
            title="LEG-Vertrag",
            version="2026-06-24",
            content="LEG-Vertrag fuer die Mitgliedschaft.",
        ),
    ]

    before_consent = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {participant_token}"},
    )
    for document in documents:
        accept_document(client, participant_token, document["id"])
    after_consent = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {participant_token}"},
    )

    assert before_consent.status_code == 200
    assert before_consent.json()["membership_status"] == "pending_required_documents"
    assert after_consent.status_code == 200
    assert after_consent.json()["membership_status"] == "active"


def test_leg_admin_can_audit_participant_required_document_consent_without_partner_access() -> None:
    client = TestClient(app)
    participant_token, participant_id = verified_participant_token(
        client,
        "required-documents-audit@example.test",
    )
    documents = [
        publish_document_version(
            client,
            document_key="privacy_notice",
            title="Datenschutzhinweis",
            version="2026-06-24",
            content="Datenschutzhinweis fuer den Audit.",
        ),
        publish_document_version(
            client,
            document_key="portal_terms",
            title="Portal-Nutzungsbedingungen",
            version="2026-06-24",
            content="Portal-Nutzungsbedingungen fuer den Audit.",
        ),
        publish_document_version(
            client,
            document_key="leg_contract",
            title="LEG-Vertrag",
            version="2026-06-24",
            content="LEG-Vertrag fuer den Audit.",
        ),
    ]
    for document in documents:
        accept_document(client, participant_token, document["id"])

    partner_response = client.get(
        f"/api/admin/participants/{participant_id}/consent-evidence",
        headers={"Authorization": "Bearer dev:partner_admin"},
    )
    admin_response = client.get(
        f"/api/admin/participants/{participant_id}/consent-evidence",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert partner_response.status_code == 403
    assert admin_response.status_code == 200
    payload = admin_response.json()
    assert [item["document_key"] for item in payload] == [
        "privacy_notice",
        "portal_terms",
        "leg_contract",
    ]
    assert [item["document_hash"] for item in payload] == [
        document["document_hash"] for document in documents
    ]
    assert all("content" not in item for item in payload)
