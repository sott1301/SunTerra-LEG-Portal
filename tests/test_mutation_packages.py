from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def verified_participant_token(
    client: TestClient,
    email: str,
    display_name: str = "Package Export Tester",
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
    *,
    street: str = "Hauptstrasse 7",
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
                "street": street,
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    )


def approve_mutation_request(client: TestClient, mutation_request_id: str):
    return client.post(
        f"/api/admin/mutation-requests/{mutation_request_id}/review-decision",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"decision": "approved"},
    )


def drain_existing_approved_q3_mutations(client: TestClient) -> None:
    response = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2026-Q3"},
    )

    assert response.status_code in {201, 400}
    if response.status_code == 400:
        assert response.json() == {
            "detail": "No approved un-packaged mutation requests for quarter",
        }


def create_approved_mutation_package(
    client: TestClient,
    *,
    email: str,
    street: str = "Hauptstrasse 7",
) -> dict:
    drain_existing_approved_q3_mutations(client)
    participant_token = verified_participant_token(client, email)
    submitted = submit_regular_address_mutation(
        client,
        participant_token,
        street=street,
    ).json()
    approved = approve_mutation_request(client, submitted["id"])
    response = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2026-Q3"},
    )

    assert approved.status_code == 200
    assert response.status_code == 201

    return response.json()


def stable_package_snapshot(package: dict) -> dict:
    snapshot = {
        **package,
        "package_id": "<package-id>",
        "generated_at": "<generated-at>",
        "hash": "<hash>",
        "records": [
            {
                **record,
                "mutation_request_id": "<mutation-request-id>",
                "participant_id": "<participant-id>",
            }
            for record in package["records"]
        ],
        "status_history": [
            {
                **event,
                "created_at": "<generated-at>",
            }
            for event in package["status_history"]
        ],
    }

    return snapshot


def stable_artifact_text(text: str, package: dict) -> str:
    stable_text = text
    replacements = {
        package["package_id"]: "<package-id>",
        package["generated_at"]: "<generated-at>",
        package["hash"]: "<hash>",
    }
    for record in package["records"]:
        replacements[record["mutation_request_id"]] = "<mutation-request-id>"
        replacements[record["participant_id"]] = "<participant-id>"

    for original, replacement in replacements.items():
        stable_text = stable_text.replace(original, replacement)

    return stable_text


def pdf_text_stream(pdf_bytes: bytes) -> str:
    pdf_text = pdf_bytes.decode("latin-1")
    return pdf_text.split("stream\n", maxsplit=1)[1].split(
        "\nendstream",
        maxsplit=1,
    )[0]


def test_leg_admin_can_package_one_approved_regular_address_mutation_for_quarter() -> None:
    client = TestClient(app)
    drain_existing_approved_q3_mutations(client)
    participant_token = verified_participant_token(
        client,
        "mutation-package-create@example.test",
    )
    submitted = submit_regular_address_mutation(client, participant_token).json()
    approved = approve_mutation_request(client, submitted["id"])

    response = client.post(
        "/api/admin/mutation-packages",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"quarter": "2026-Q3"},
    )

    assert approved.status_code == 200
    assert response.status_code == 201
    payload = response.json()
    assert payload["schema_version"] == "mutation-package.v1"
    assert payload["package_id"]
    assert payload["leg_id"] == "basadingen"
    assert payload["quarter"] == "2026-Q3"
    assert payload["effective_date"] == "2026-10-01"
    assert payload["generated_at"]
    assert payload["hash"]
    assert payload["records"] == [
        {
            "mutation_request_id": submitted["id"],
            "participant_id": participant_token.removeprefix("dev:participant:"),
            "mutation_type": "address",
            "mode": "regular",
            "effective_date": "2026-10-01",
            "new_address": {
                "street": "Hauptstrasse 7",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
            "mutation_details": {
                "street": "Hauptstrasse 7",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    ]
    creation_event = payload["status_history"][0]
    assert creation_event["status"] == "created"
    assert creation_event["actor_role"] == "leg_admin"
    assert creation_event["actor_id"] == "dev-leg-admin"
    assert creation_event["created_at"] == payload["generated_at"]


def test_leg_admin_can_download_json_artifact_for_mutation_package() -> None:
    client = TestClient(app)
    package = create_approved_mutation_package(
        client,
        email="mutation-package-json@example.test",
        street="Dorfstrasse 11",
    )

    response = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/json",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == package
    assert stable_package_snapshot(response.json()) == {
        "schema_version": "mutation-package.v1",
        "package_id": "<package-id>",
        "leg_id": "basadingen",
        "quarter": "2026-Q3",
        "effective_date": "2026-10-01",
        "records": [
            {
                "mutation_request_id": "<mutation-request-id>",
                "participant_id": "<participant-id>",
                "mutation_type": "address",
                "mode": "regular",
                "effective_date": "2026-10-01",
                "new_address": {
                    "street": "Dorfstrasse 11",
                    "postal_code": "8254",
                    "city": "Basadingen",
                    "country": "CH",
                },
                "mutation_details": {
                    "street": "Dorfstrasse 11",
                    "postal_code": "8254",
                    "city": "Basadingen",
                    "country": "CH",
                },
            },
        ],
        "hash": "<hash>",
        "generated_at": "<generated-at>",
        "status_history": [
            {
                "status": "created",
                "actor_id": "dev-leg-admin",
                "actor_role": "leg_admin",
                "created_at": "<generated-at>",
            },
        ],
    }


def test_leg_admin_can_download_csv_artifact_for_mutation_package() -> None:
    client = TestClient(app)
    package = create_approved_mutation_package(
        client,
        email="mutation-package-csv@example.test",
        street="Oberdorf 3",
    )

    response = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/csv",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert stable_artifact_text(response.text, package) == (
        "schema_version,package_id,leg_id,quarter,effective_date,hash,"
        "generated_at,record_index,mutation_request_id,participant_id,"
        "mutation_type,mode,record_effective_date,mutation_details_json,"
        "street,postal_code,city,country,status,status_actor_id,"
        "status_actor_role,status_created_at\n"
        "mutation-package.v1,<package-id>,basadingen,2026-Q3,2026-10-01,"
        "<hash>,<generated-at>,1,<mutation-request-id>,<participant-id>,"
        'address,regular,2026-10-01,"{""city"":""Basadingen"",'
        '""country"":""CH"",""postal_code"":""8254"",'
        '""street"":""Oberdorf 3""}",Oberdorf 3,8254,Basadingen,CH,'
        "created,dev-leg-admin,leg_admin,<generated-at>\n"
    )


def test_leg_admin_can_download_pdf_artifact_for_mutation_package() -> None:
    client = TestClient(app)
    package = create_approved_mutation_package(
        client,
        email="mutation-package-pdf@example.test",
        street="Bahnhofstrasse 5",
    )

    response = client.get(
        f"/api/admin/mutation-packages/{package['package_id']}/pdf",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-1.4\n")
    assert stable_artifact_text(pdf_text_stream(response.content), package) == (
        "BT\n"
        "/F1 10 Tf\n"
        "40 800 Td\n"
        "(MutationPackage Export) Tj\n"
        "0 -14 Td\n"
        "(schema_version: mutation-package.v1) Tj\n"
        "0 -14 Td\n"
        "(package_id: <package-id>) Tj\n"
        "0 -14 Td\n"
        "(leg_id: basadingen) Tj\n"
        "0 -14 Td\n"
        "(quarter: 2026-Q3) Tj\n"
        "0 -14 Td\n"
        "(effective_date: 2026-10-01) Tj\n"
        "0 -14 Td\n"
        "(hash: <hash>) Tj\n"
        "0 -14 Td\n"
        "(generated_at: <generated-at>) Tj\n"
        "0 -14 Td\n"
        "(record 1: <mutation-request-id> <participant-id> address regular "
        '2026-10-01 {"city":"Basadingen","country":"CH",'
        '"postal_code":"8254","street":"Bahnhofstrasse 5"} '
        "Bahnhofstrasse 5, 8254 Basadingen, CH) Tj\n"
        "0 -14 Td\n"
        "(status: created by dev-leg-admin leg_admin at <generated-at>) Tj\n"
        "ET"
    )


def test_existing_package_artifacts_stay_immutable_after_later_same_quarter_package() -> None:
    client = TestClient(app)
    package_a = create_approved_mutation_package(
        client,
        email="mutation-package-immutable-a@example.test",
        street="Kirchweg 1",
    )
    json_a = client.get(
        f"/api/admin/mutation-packages/{package_a['package_id']}/json",
        headers={"Authorization": "Bearer dev:leg_admin"},
    ).content
    csv_a = client.get(
        f"/api/admin/mutation-packages/{package_a['package_id']}/csv",
        headers={"Authorization": "Bearer dev:leg_admin"},
    ).content
    pdf_a = client.get(
        f"/api/admin/mutation-packages/{package_a['package_id']}/pdf",
        headers={"Authorization": "Bearer dev:leg_admin"},
    ).content

    package_b = create_approved_mutation_package(
        client,
        email="mutation-package-immutable-b@example.test",
        street="Rebenweg 8",
    )

    assert package_b["package_id"] != package_a["package_id"]
    assert package_b["records"] == [
        {
            **package_b["records"][0],
            "new_address": {
                "street": "Rebenweg 8",
                "postal_code": "8254",
                "city": "Basadingen",
                "country": "CH",
            },
        },
    ]
    assert (
        client.get(
            f"/api/admin/mutation-packages/{package_a['package_id']}/json",
            headers={"Authorization": "Bearer dev:leg_admin"},
        ).content
        == json_a
    )
    assert (
        client.get(
            f"/api/admin/mutation-packages/{package_a['package_id']}/csv",
            headers={"Authorization": "Bearer dev:leg_admin"},
        ).content
        == csv_a
    )
    assert (
        client.get(
            f"/api/admin/mutation-packages/{package_a['package_id']}/pdf",
            headers={"Authorization": "Bearer dev:leg_admin"},
        ).content
        == pdf_a
    )
