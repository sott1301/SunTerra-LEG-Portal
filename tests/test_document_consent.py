from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


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
