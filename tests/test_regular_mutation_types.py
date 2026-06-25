from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def verified_participant_token(client: TestClient, email: str) -> str:
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": email, "display_name": "Regular Mutation Tester"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    return accepted["access_token"]


def approve_mutation_request(client: TestClient, mutation_request_id: str) -> None:
    response = client.post(
        f"/api/admin/mutation-requests/{mutation_request_id}/package-readiness",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"ready": True, "reason": "Paketbereit-Check bestanden."},
    )

    assert response.status_code == 200


def test_verified_participant_can_submit_regular_meter_point_mutation() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-meter-point@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "meter_point",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "metering_code": "CH-1008901234500000000000000000123",
        },
    )

    assert response.status_code == 201
    submitted = response.json()
    assert submitted["mutation_type"] == "meter_point"
    assert submitted["participant_deadline"] == "2026-06-30"
    assert submitted["effective_date"] == "2026-10-01"
    assert submitted["mutation_details"] == {
        "metering_code": "CH-1008901234500000000000000000123",
    }

    history_response = client.get(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
    )

    assert history_response.status_code == 200
    assert history_response.json() == [
        {
            **submitted,
            "reviewed_at": None,
            "review_reason": None,
            "audit_events": [],
        },
    ]


def test_regular_meter_point_mutation_requires_metering_code() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-meter-point-invalid@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "meter_point",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "metering_code": "   ",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Meter point mutation requires metering_code",
    }


def test_verified_participant_can_submit_regular_role_mutation() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-role@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "role",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "requested_role": "prosumer",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["mutation_type"] == "role"
    assert payload["participant_deadline"] == "2026-06-30"
    assert payload["effective_date"] == "2026-10-01"
    assert payload["mutation_details"] == {"requested_role": "prosumer"}


def test_regular_role_mutation_rejects_unknown_requested_role() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-role-invalid@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "role",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "requested_role": "auditor",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "Role mutation requested_role must be one of owner, producer, "
            "prosumer, tenant"
        ),
    }


def test_verified_participant_can_submit_regular_generation_asset_mutation() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-generation-asset@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "generation_asset",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "technology": "photovoltaic",
            "installed_capacity_kw": 12.5,
            "commissioned_on": "2026-05-20",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["mutation_type"] == "generation_asset"
    assert payload["participant_deadline"] == "2026-06-30"
    assert payload["effective_date"] == "2026-10-01"
    assert payload["mutation_details"] == {
        "technology": "photovoltaic",
        "installed_capacity_kw": 12.5,
        "commissioned_on": "2026-05-20",
    }


def test_regular_generation_asset_mutation_requires_positive_capacity() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-generation-asset-invalid@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "generation_asset",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "technology": "photovoltaic",
            "installed_capacity_kw": 0,
            "commissioned_on": "2026-05-20",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "Generation asset mutation requires technology, positive "
            "installed_capacity_kw, and commissioned_on"
        ),
    }


def test_verified_participant_can_submit_regular_entry_mutation() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-entry@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "entry",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "reason": "Neue Teilnahme ab Quartalswechsel",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["mutation_type"] == "entry"
    assert payload["quarter_end"] == "2026-09-30"
    assert payload["participant_deadline"] == "2026-06-30"
    assert payload["effective_date"] == "2026-10-01"
    assert payload["mutation_details"] == {
        "reason": "Neue Teilnahme ab Quartalswechsel",
    }


def test_regular_entry_mutation_requires_reason() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-entry-invalid@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "entry",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "reason": "",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Entry mutation requires reason"}


def test_non_entry_mutation_requires_package_ready_check_before_packaging() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-package-ready@example.test",
    )
    submitted = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "role",
            "mode": "regular",
            "requested_quarter": "2031-Q1",
            "submitted_on": "2030-12-31",
            "requested_role": "producer",
        },
    ).json()
    entry = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "entry",
            "mode": "regular",
            "requested_quarter": "2031-Q1",
            "submitted_on": "2030-12-31",
            "reason": "Neue Teilnahme.",
        },
    ).json()

    package_before_check = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2031-Q1"},
    )
    entry_ready = client.post(
        f"/api/admin/mutation-requests/{entry['id']}/package-readiness",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"ready": True, "reason": "Eintritt braucht LEG-Freigabe."},
    )
    package_ready = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/package-readiness",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"ready": True, "reason": "Paketbereit-Check bestanden."},
    )
    package = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2031-Q1"},
    )

    assert submitted["status"] == "submitted"
    assert entry["status"] == "submitted"
    assert package_before_check.status_code == 400
    assert package_before_check.json() == {
        "detail": "No package-ready un-packaged mutation requests for quarter",
    }
    assert entry_ready.status_code == 400
    assert entry_ready.json() == {
        "detail": "Entry mutations require LEG approval before package readiness",
    }
    assert package_ready.status_code == 200
    assert package_ready.json()["status"] == "package_ready"
    assert package_ready.json()["review_reason"] == "Paketbereit-Check bestanden."
    assert package.status_code == 201
    assert [record["mutation_request_id"] for record in package.json()["records"]] == [
        submitted["id"],
    ]


def test_non_entry_package_readiness_can_request_clarification_or_stop_invalid() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-package-readiness-stop@example.test",
    )
    incomplete = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "role",
            "mode": "regular",
            "requested_quarter": "2031-Q3",
            "submitted_on": "2031-06-30",
            "requested_role": "producer",
        },
    ).json()
    erroneous = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "meter_point",
            "mode": "regular",
            "requested_quarter": "2031-Q3",
            "submitted_on": "2031-06-30",
            "metering_code": "CH-1008901234500000000000000000999",
        },
    ).json()

    clarification = client.post(
        f"/api/admin/mutation-requests/{incomplete['id']}/package-readiness",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "ready": False,
            "status": "needs_clarification",
            "reason": "Vollmacht fehlt.",
        },
    )
    stopped = client.post(
        f"/api/admin/mutation-requests/{erroneous['id']}/package-readiness",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "ready": False,
            "status": "stopped_invalid",
            "reason": "Messpunkt gehoert nicht zur Teilnehmeradresse.",
        },
    )
    package = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2031-Q3"},
    )
    participant_history = client.get(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
    )

    assert clarification.status_code == 200
    assert clarification.json()["status"] == "needs_clarification"
    assert clarification.json()["review_reason"] == "Vollmacht fehlt."
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped_invalid"
    assert (
        stopped.json()["review_reason"]
        == "Messpunkt gehoert nicht zur Teilnehmeradresse."
    )
    assert package.status_code == 400
    assert package.json() == {
        "detail": "No package-ready un-packaged mutation requests for quarter",
    }
    assert participant_history.status_code == 200
    statuses = {
        record["id"]: (record["status"], record["review_reason"])
        for record in participant_history.json()
    }
    assert statuses[incomplete["id"]] == ("needs_clarification", "Vollmacht fehlt.")
    assert statuses[erroneous["id"]] == (
        "stopped_invalid",
        "Messpunkt gehoert nicht zur Teilnehmeradresse.",
    )


def test_legacy_approved_non_entry_mutation_is_not_packageable() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-approved-not-packageable@example.test",
    )
    submitted = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "address",
            "mode": "regular",
            "requested_quarter": "2031-Q2",
            "submitted_on": "2031-03-31",
            "new_address": {
                "street": "Bypassweg 9",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    ).json()
    reviewed = client.post(
        f"/api/admin/mutation-requests/{submitted['id']}/review-decision",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"decision": "approved"},
    )

    package = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2031-Q2"},
    )

    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "approved"
    assert package.status_code == 400
    assert package.json() == {
        "detail": "No package-ready un-packaged mutation requests for quarter",
    }


def test_verified_participant_can_submit_regular_exit_mutation() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-exit@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "exit",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "reason": "Austritt per Quartalsende",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["mutation_type"] == "exit"
    assert payload["quarter_end"] == "2026-09-30"
    assert payload["participant_deadline"] == "2026-06-30"
    assert payload["effective_date"] == "2026-09-30"
    assert payload["mutation_details"] == {"reason": "Austritt per Quartalsende"}


def test_regular_exit_mutation_requires_reason() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-exit-invalid@example.test",
    )

    response = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "exit",
            "mode": "regular",
            "requested_quarter": "2026-Q3",
            "submitted_on": "2026-06-15",
            "reason": " ",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Exit mutation requires reason"}


def test_regular_role_mutation_package_serializes_stable_details() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-role-package@example.test",
    )
    submitted = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "role",
            "mode": "regular",
            "requested_quarter": "2028-Q1",
            "submitted_on": "2027-12-31",
            "requested_role": "producer",
        },
    ).json()
    approve_mutation_request(client, submitted["id"])

    response = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2028-Q1"},
    )

    assert response.status_code == 201
    package = response.json()
    assert package["records"] == [
        {
            "mutation_request_id": submitted["id"],
            "participant_id": participant_token.removeprefix("dev:participant:"),
            "mutation_type": "role",
            "mode": "regular",
            "effective_date": "2028-04-01",
            "new_address": None,
            "mutation_details": {"requested_role": "producer"},
        },
    ]


def test_regular_role_mutation_package_csv_serializes_stable_details() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-role-package-csv@example.test",
    )
    submitted = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "role",
            "mode": "regular",
            "requested_quarter": "2028-Q2",
            "submitted_on": "2028-03-31",
            "requested_role": "tenant",
        },
    ).json()
    approve_mutation_request(client, submitted["id"])
    package = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2028-Q2"},
    ).json()

    response = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/csv",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert response.status_code == 200
    assert "mutation_details_json" in response.text.splitlines()[0]
    assert '"{""requested_role"":""tenant""}"' in response.text


def test_regular_role_mutation_package_pdf_serializes_stable_details() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-role-package-pdf@example.test",
    )
    submitted = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "role",
            "mode": "regular",
            "requested_quarter": "2028-Q3",
            "submitted_on": "2028-06-30",
            "requested_role": "owner",
        },
    ).json()
    approve_mutation_request(client, submitted["id"])
    package = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2028-Q3"},
    ).json()

    response = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/pdf",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert response.status_code == 200
    pdf_text = response.content.decode("latin-1")
    assert '{"requested_role":"owner"}' in pdf_text


def test_partner_member_register_handles_non_address_mutation_package() -> None:
    client = TestClient(app)
    participant_token = verified_participant_token(
        client,
        "regular-role-register@example.test",
    )
    submitted = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {participant_token}"},
        json={
            "mutation_type": "role",
            "mode": "regular",
            "requested_quarter": "2028-Q4",
            "submitted_on": "2028-09-30",
            "requested_role": "producer",
        },
    ).json()
    approve_mutation_request(client, submitted["id"])
    package = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2028-Q4"},
    ).json()

    response = client.get(
        "/api/partner/member-register",
        headers={"Authorization": "Bearer dev:partner_admin"},
    )

    assert response.status_code == 200
    participant_id = participant_token.removeprefix("dev:participant:")
    participant_rows = [
        member
        for member in response.json()["members"]
        if member["participant_id"] == participant_id
    ]
    assert participant_rows == [
        {
            "participant_id": participant_id,
            "display_name": "Regular Mutation Tester",
            "membership_status": "active",
            "reporting_address": None,
            "latest_package_status": {
                "package_id": package["package_id"],
                "quarter": "2028-Q4",
                "effective_date": "2029-01-01",
                "status": "created",
            },
        },
    ]
