from fastapi.testclient import TestClient

from sunterra_leg_portal.auth import CurrentUser, Role, create_access_token
from sunterra_leg_portal.main import USER_ACCOUNTS, UserAccountRecord, app


def start_self_service_onboarding(client: TestClient, email: str = "selina.frei@example.test") -> dict:
    return client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": email,
            "display_name": "Selina Frei",
        },
    ).json()


def address_mutation_payload() -> dict:
    return {
        "mutation_type": "address",
        "mode": "regular",
        "requested_quarter": "2026-Q3",
        "submitted_on": "2026-06-15",
        "new_address": {
            "street": "Netzweg 56",
            "postal_code": "8254",
            "city": "Basadingen",
            "country": "CH",
        },
    }


def test_public_user_can_start_self_service_onboarding_without_invitation() -> None:
    response = TestClient(app).post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "selina.frei@example.test",
            "display_name": "Selina Frei",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload.pop("participant_id")
    assert payload.pop("dev_email_verification_token")
    assert payload["access_token"].count(".") == 2
    assert not payload["access_token"].startswith("dev:participant:")
    assert payload == {
        "access_token": payload["access_token"],
        "token_type": "bearer",
        "participant_status": "pending_email_verification",
        "identity_checkpoint": {
            "required_level": "email_verified",
            "current_level": "unverified",
            "satisfied": False,
        },
    }


def test_production_public_registration_requires_explicit_rollout_gate(monkeypatch) -> None:
    monkeypatch.setenv("SUNTERRA_ENV", "production")
    monkeypatch.setenv("SUNTERRA_REGISTRATION_MODE", "public")
    monkeypatch.delenv("SUNTERRA_PUBLIC_ROLLOUT_APPROVED", raising=False)

    response = TestClient(app).post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "public.gate@example.test",
            "display_name": "Public Gate",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Public rollout gate incomplete"}


def test_production_public_registration_can_start_after_explicit_rollout_gate(
    monkeypatch,
) -> None:
    sent_messages: list[str] = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            assert host == "smtp.example.test"
            assert port == 587
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def starttls(self) -> None:
            return None

        def send_message(self, message) -> None:
            sent_messages.append(message["To"])

    monkeypatch.setenv("SUNTERRA_ENV", "production")
    monkeypatch.setenv("SUNTERRA_REGISTRATION_MODE", "public")
    monkeypatch.setenv("SUNTERRA_PUBLIC_ROLLOUT_APPROVED", "1")
    monkeypatch.setenv("SUNTERRA_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SUNTERRA_SMTP_PORT", "587")
    monkeypatch.setenv("SUNTERRA_SMTP_FROM_EMAIL", "portal@example.test")
    monkeypatch.setattr("smtplib.SMTP", FakeSmtp)

    response = TestClient(app).post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "public.gate.approved@example.test",
            "display_name": "Public Gate Approved",
        },
    )

    assert response.status_code == 201
    assert response.json()["participant_status"] == "pending_email_verification"
    assert sent_messages == ["public.gate.approved@example.test"]


def test_pilot_mode_records_interest_for_non_allowlisted_email(monkeypatch) -> None:
    monkeypatch.setenv("SUNTERRA_REGISTRATION_MODE", "pilot")
    client = TestClient(app)
    email = "pilot.interest@example.test"

    response = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={"email": email, "display_name": "Pilot Interest"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Start123!"},
    )
    interests = client.get(
        "/api/admin/interest-records",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload.pop("id")
    assert payload.pop("created_at")
    assert payload == {
        "email": email,
        "display_name": "Pilot Interest",
        "status": "interest_recorded",
    }
    assert login.status_code == 401
    assert interests.status_code == 200
    assert any(record["email"] == email for record in interests.json())


def test_pilot_mode_allows_env_allowlisted_email(monkeypatch) -> None:
    monkeypatch.setenv("SUNTERRA_REGISTRATION_MODE", "pilot")
    monkeypatch.setenv(
        "SUNTERRA_PILOT_ALLOWLIST_EMAILS",
        "pilot.allowed@example.test, another.allowed@example.test",
    )

    response = TestClient(app).post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "pilot.allowed@example.test",
            "display_name": "Pilot Allowed",
        },
    )

    assert response.status_code == 201
    assert response.json()["participant_status"] == "pending_email_verification"


def test_leg_admin_can_allow_interest_email_for_later_onboarding(monkeypatch) -> None:
    monkeypatch.setenv("SUNTERRA_REGISTRATION_MODE", "pilot")
    client = TestClient(app)
    email = "pilot.reviewed@example.test"
    first_attempt = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={"email": email, "display_name": "Pilot Reviewed"},
    )
    allowlisted = client.post(
        "/api/admin/pilot-allowlist",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": email},
    )
    second_attempt = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={"email": email, "display_name": "Pilot Reviewed"},
    )

    assert first_attempt.status_code == 202
    assert allowlisted.status_code == 201
    assert allowlisted.json()["email"] == email
    assert second_attempt.status_code == 201
    assert second_attempt.json()["participant_status"] == "pending_email_verification"


def test_unverified_self_service_participant_can_read_membership_checkpoint_but_not_membership() -> None:
    client = TestClient(app)
    onboarding = start_self_service_onboarding(
        client,
        email="checkpoint.blocked@example.test",
    )

    membership_response = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
    )
    checkpoint_response = client.get(
        "/api/participants/me/identity-checkpoint?action=membership_activation",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
    )

    assert membership_response.status_code == 403
    assert membership_response.json() == {"detail": "Email verification required"}
    assert checkpoint_response.status_code == 200
    assert checkpoint_response.json() == {
        "action": "membership_activation",
        "required_level": "email_verified",
        "current_level": "unverified",
        "satisfied": False,
    }


def test_email_verification_requires_account_setup_before_membership_access() -> None:
    client = TestClient(app)
    onboarding = start_self_service_onboarding(
        client,
        email="checkpoint.verified@example.test",
    )

    verification_response = client.post(
        (
            "/api/auth/email-verifications/"
            f"{onboarding['dev_email_verification_token']}/verify"
        ),
    )
    checkpoint_response = client.get(
        "/api/participants/me/identity-checkpoint?action=membership_activation",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
    )
    membership_before_setup = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
    )

    assert verification_response.status_code == 200
    assert verification_response.json() == {
        "participant_id": onboarding["participant_id"],
        "email_verified": True,
    }
    assert checkpoint_response.status_code == 200
    assert checkpoint_response.json() == {
        "action": "membership_activation",
        "required_level": "account_setup",
        "current_level": "email_verified",
        "satisfied": False,
    }
    assert membership_before_setup.status_code == 403
    assert membership_before_setup.json() == {"detail": "Account setup required"}

    setup_response = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={"display_name": "Selina Frei", "password": "Start123!"},
    )
    assert setup_response.status_code == 200
    setup_token = setup_response.json()["access_token"]
    membership_after_setup = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {setup_token}"},
    )

    assert membership_after_setup.status_code == 200
    assert membership_after_setup.json() == {
        "participant_id": onboarding["participant_id"],
        "display_name": "Selina Frei",
        "email": "checkpoint.verified@example.test",
        "leg_id": "basadingen",
        "leg_name": "SunTerra LEG Basadingen",
        "membership_status": "pending_eligibility_review",
        "eligibility_status": "pending_review",
        "eligibility_review_reason": None,
        "billing_notice": "Abrechnung und Inkasso bleiben bei Gemeinde/EW.",
    }


def test_self_service_participant_needs_network_topology_eligibility_approval() -> None:
    client = TestClient(app)
    onboarding = start_self_service_onboarding(
        client,
        email="eligibility.pending@example.test",
    )
    client.post(
        (
            "/api/auth/email-verifications/"
            f"{onboarding['dev_email_verification_token']}/verify"
        ),
    )
    setup_response = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={"display_name": "Eligibility Pending", "password": "Start123!"},
    )
    token = setup_response.json()["access_token"]

    pending_membership = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {token}"},
    )
    blocked_mutation = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {token}"},
        json=address_mutation_payload(),
    )
    approved = client.post(
        f"/api/admin/participants/{onboarding['participant_id']}/eligibility-review",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "decision": "approved",
            "reason": "Adresse liegt im verbundenen Netzgebiet.",
        },
    )
    active_membership = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {token}"},
    )
    submitted_mutation = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {token}"},
        json=address_mutation_payload(),
    )

    assert pending_membership.status_code == 200
    assert pending_membership.json()["membership_status"] == "pending_eligibility_review"
    assert pending_membership.json()["eligibility_status"] == "pending_review"
    assert pending_membership.json()["eligibility_review_reason"] is None
    assert blocked_mutation.status_code == 403
    assert blocked_mutation.json() == {
        "detail": "Network topology eligibility review required",
    }
    assert approved.status_code == 200
    assert approved.json() == {
        "participant_id": onboarding["participant_id"],
        "eligibility_status": "approved",
        "eligibility_review_reason": "Adresse liegt im verbundenen Netzgebiet.",
    }
    assert active_membership.status_code == 200
    assert active_membership.json()["membership_status"] == "active"
    assert active_membership.json()["eligibility_status"] == "approved"
    assert submitted_mutation.status_code == 201


def test_network_topology_list_prechecks_matching_self_service_participant() -> None:
    client = TestClient(app)
    imported = client.post(
        "/api/admin/network-topology-entries",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "source_name": "Rollout-Liste Basadingen 2026",
            "entries": [
                {
                    "metering_point_id": "CH-SUNTERRA-8254-0001",
                    "street": "Netzweg 56",
                    "postal_code": "8254",
                    "city": "Basadingen",
                },
            ],
        },
    )
    onboarding = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "topology.match@example.test",
            "display_name": "Topology Match",
            "metering_point_id": "CH-SUNTERRA-8254-0001",
            "street": "Netzweg 56",
            "postal_code": "8254",
            "city": "Basadingen",
        },
    ).json()
    client.post(
        (
            "/api/auth/email-verifications/"
            f"{onboarding['dev_email_verification_token']}/verify"
        ),
    )
    setup_response = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={"display_name": "Topology Match", "password": "Start123!"},
    )
    token = setup_response.json()["access_token"]

    membership = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {token}"},
    )
    mutation = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {token}"},
        json=address_mutation_payload(),
    )

    assert imported.status_code == 201
    assert imported.json()["source_name"] == "Rollout-Liste Basadingen 2026"
    assert imported.json()["imported_entries"] == 1
    assert membership.status_code == 200
    assert membership.json()["membership_status"] == "active"
    assert membership.json()["eligibility_status"] == "approved"
    assert (
        membership.json()["eligibility_review_reason"]
        == "Netzwerktopologie vorgeprueft: Rollout-Liste Basadingen 2026"
    )
    assert mutation.status_code == 201


def test_network_topology_replacement_deactivates_old_matches_and_keeps_manual_review() -> None:
    client = TestClient(app)
    first_import = client.post(
        "/api/admin/network-topology-entries",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "source_name": "Rollout-Liste Alt",
            "entries": [
                {
                    "metering_point_id": "CH-SUNTERRA-OLD-0001",
                    "street": "Alter Netzweg 1",
                    "postal_code": "8254",
                    "city": "Basadingen",
                },
            ],
        },
    )
    second_import = client.post(
        "/api/admin/network-topology-entries",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "source_name": "Rollout-Liste Neu",
            "entries": [
                {
                    "metering_point_id": "CH-SUNTERRA-NEW-0001",
                    "street": "Neuer Netzweg 2",
                    "postal_code": "8254",
                    "city": "Basadingen",
                },
            ],
        },
    )

    old_onboarding = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "topology.old-list@example.test",
            "display_name": "Old Topology",
            "metering_point_id": "CH-SUNTERRA-OLD-0001",
            "street": "Alter Netzweg 1",
            "postal_code": "8254",
            "city": "Basadingen",
        },
    ).json()
    client.post(
        f"/api/auth/email-verifications/{old_onboarding['dev_email_verification_token']}/verify",
    )
    old_setup = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {old_onboarding['access_token']}"},
        json={"display_name": "Old Topology", "password": "Start123!"},
    )
    old_pending_membership = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {old_setup.json()['access_token']}"},
    )
    old_approval = client.post(
        f"/api/admin/participants/{old_onboarding['participant_id']}/eligibility-review",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "decision": "approved",
            "reason": "Manuelle Ausnahme nach Topologie-Ersatz bestaetigt.",
        },
    )
    new_onboarding = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "topology.new-list@example.test",
            "display_name": "New Topology",
            "metering_point_id": "CH-SUNTERRA-NEW-0001",
            "street": "Neuer Netzweg 2",
            "postal_code": "8254",
            "city": "Basadingen",
        },
    ).json()

    assert first_import.status_code == 201
    assert second_import.status_code == 201
    assert old_pending_membership.status_code == 200
    assert old_pending_membership.json()["membership_status"] == "pending_eligibility_review"
    assert old_pending_membership.json()["eligibility_status"] == "pending_review"
    assert old_approval.status_code == 200
    assert old_approval.json()["eligibility_status"] == "approved"
    assert (
        old_approval.json()["eligibility_review_reason"]
        == "Manuelle Ausnahme nach Topologie-Ersatz bestaetigt."
    )
    assert new_onboarding["identity_checkpoint"]["satisfied"] is False

    client.post(
        f"/api/auth/email-verifications/{new_onboarding['dev_email_verification_token']}/verify",
    )
    new_setup = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {new_onboarding['access_token']}"},
        json={"display_name": "New Topology", "password": "Start123!"},
    )
    new_membership = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {new_setup.json()['access_token']}"},
    )

    assert new_membership.status_code == 200
    assert new_membership.json()["membership_status"] == "active"
    assert new_membership.json()["eligibility_status"] == "approved"
    assert (
        new_membership.json()["eligibility_review_reason"]
        == "Netzwerktopologie vorgeprueft: Rollout-Liste Neu"
    )


def test_leg_admin_can_stop_network_topology_eligibility_with_visible_reason() -> None:
    client = TestClient(app)
    onboarding = start_self_service_onboarding(
        client,
        email="eligibility.stopped@example.test",
    )
    client.post(
        (
            "/api/auth/email-verifications/"
            f"{onboarding['dev_email_verification_token']}/verify"
        ),
    )
    setup_response = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={"display_name": "Eligibility Stopped", "password": "Start123!"},
    )
    token = setup_response.json()["access_token"]

    stopped = client.post(
        f"/api/admin/participants/{onboarding['participant_id']}/eligibility-review",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={
            "decision": "stopped",
            "reason": "Adresse liegt ausserhalb des verbundenen Netzgebiets.",
        },
    )
    membership = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {token}"},
    )
    mutation = client.post(
        "/api/participants/me/mutation-requests",
        headers={"Authorization": f"Bearer {token}"},
        json=address_mutation_payload(),
    )
    participant_attempt = client.post(
        f"/api/admin/participants/{onboarding['participant_id']}/eligibility-review",
        headers={"Authorization": f"Bearer {token}"},
        json={"decision": "approved", "reason": "Nicht erlaubt."},
    )

    assert stopped.status_code == 200
    assert stopped.json()["eligibility_status"] == "stopped"
    assert membership.status_code == 200
    assert membership.json()["membership_status"] == "eligibility_stopped"
    assert membership.json()["eligibility_status"] == "stopped"
    assert (
        membership.json()["eligibility_review_reason"]
        == "Adresse liegt ausserhalb des verbundenen Netzgebiets."
    )
    assert mutation.status_code == 403
    assert mutation.json() == {
        "detail": "Network topology eligibility review stopped",
    }
    assert participant_attempt.status_code == 403


def test_leg_and_platform_admin_can_read_auditable_identity_verification_state() -> None:
    client = TestClient(app)
    onboarding = start_self_service_onboarding(
        client,
        email="identity.audit@example.test",
    )
    client.post(
        (
            "/api/auth/email-verifications/"
            f"{onboarding['dev_email_verification_token']}/verify"
        ),
    )

    for admin_role in ("leg_admin", "platform_admin"):
        response = client.get(
            f"/api/admin/participants/{onboarding['participant_id']}/identity-verification",
            headers={"Authorization": f"Bearer dev:{admin_role}"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload.pop("verified_at")
        assert payload == {
            "participant_id": onboarding["participant_id"],
            "email": "identity.audit@example.test",
            "display_name": "Selina Frei",
            "leg_id": "basadingen",
            "source": "self_service_onboarding",
            "required_level": "email_verified",
            "current_level": "email_verified",
            "satisfied": True,
        }


def test_self_service_start_queues_only_allowed_verification_email_event() -> None:
    client = TestClient(app)
    recipient_email = "self.service.communication@example.test"

    start_self_service_onboarding(client, email=recipient_email)
    events_response = client.get(
        f"/api/admin/communication-events?recipient_email={recipient_email}",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert events_response.status_code == 200
    events = events_response.json()
    assert [event["event_type"] for event in events] == ["email_verification"]
    assert [event["channel"] for event in events] == ["email"]
    assert [event["status"] for event in events] == ["queued"]
    assert {
        "deadline_reminder",
        "mutation_status_update",
    }.isdisjoint({event["event_type"] for event in events})


def test_production_self_service_sends_verification_email_through_smtp(
    monkeypatch,
) -> None:
    sent_messages = []
    recipient_email = "smtp.self.service@example.test"

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: int):
            assert host == "smtp.example.test"
            assert port == 587
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setenv("SUNTERRA_ENV", "production")
    monkeypatch.setenv("SUNTERRA_PUBLIC_ROLLOUT_APPROVED", "1")
    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "smtp-production-secret")
    monkeypatch.setenv("SUNTERRA_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SUNTERRA_SMTP_PORT", "587")
    monkeypatch.setenv("SUNTERRA_SMTP_FROM_EMAIL", "noreply@portal.example.test")
    monkeypatch.setattr("smtplib.SMTP", FakeSmtp)
    monkeypatch.setitem(
        USER_ACCOUNTS,
        "smtp-admin",
        UserAccountRecord(
            id="smtp-admin",
            email="smtp-admin@example.test",
            display_name="SMTP Admin",
            role=Role.LEG_ADMIN,
            active=True,
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={"email": recipient_email, "display_name": "SMTP Self Service"},
    )
    admin_token = create_access_token(
        CurrentUser(
            id="smtp-admin",
                email="smtp-admin@example.test",
                display_name="SMTP Admin",
                role=Role.LEG_ADMIN,
                mfa_satisfied=True,
            ),
        )
    events_response = client.get(
        f"/api/admin/communication-events?recipient_email={recipient_email}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    assert len(sent_messages) == 1
    message = sent_messages[0]
    assert message["To"] == recipient_email
    assert message["From"] == "noreply@portal.example.test"
    assert message["Subject"]
    assert events_response.status_code == 200
    assert [event["status"] for event in events_response.json()] == ["sent"]


def test_production_self_service_response_hides_development_verification_token(
    monkeypatch,
) -> None:
    class FakeSmtp:
        def __init__(self, _host: str, _port: int, timeout: int):
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def send_message(self, _message):
            return None

    monkeypatch.setenv("SUNTERRA_ENV", "production")
    monkeypatch.setenv("SUNTERRA_PUBLIC_ROLLOUT_APPROVED", "1")
    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "smtp-production-secret")
    monkeypatch.setenv("SUNTERRA_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SUNTERRA_SMTP_PORT", "587")
    monkeypatch.setenv("SUNTERRA_SMTP_FROM_EMAIL", "noreply@portal.example.test")
    monkeypatch.setattr("smtplib.SMTP", FakeSmtp)

    response = TestClient(app).post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "smtp.hidden-token@example.test",
            "display_name": "SMTP Hidden Token",
        },
    )

    assert response.status_code == 201
    assert response.json()["dev_email_verification_token"] is None


def test_production_self_service_email_verification_uses_smtp_link(
    monkeypatch,
) -> None:
    sent_messages = []

    class FakeSmtp:
        def __init__(self, _host: str, _port: int, timeout: int):
            assert timeout == 10
            pass

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setenv("SUNTERRA_ENV", "production")
    monkeypatch.setenv("SUNTERRA_PUBLIC_ROLLOUT_APPROVED", "1")
    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "smtp-production-secret")
    monkeypatch.setenv("SUNTERRA_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SUNTERRA_SMTP_PORT", "587")
    monkeypatch.setenv("SUNTERRA_SMTP_FROM_EMAIL", "noreply@portal.example.test")
    monkeypatch.setenv("SUNTERRA_PUBLIC_BASE_URL", "https://portal.example.test")
    monkeypatch.setattr("smtplib.SMTP", FakeSmtp)

    client = TestClient(app)
    onboarding_response = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": "smtp.link@example.test",
            "display_name": "SMTP Link",
        },
    )

    assert onboarding_response.status_code == 201
    assert onboarding_response.json()["dev_email_verification_token"] is None
    assert len(sent_messages) == 1
    message_body = sent_messages[0].get_content()
    marker = "https://portal.example.test/api/auth/email-verifications/"
    assert marker in message_body
    token = message_body.split(marker, maxsplit=1)[1].split("/verify", maxsplit=1)[0]

    verification_response = client.get(
        f"/api/auth/email-verifications/{token}/verify",
    )

    assert verification_response.status_code == 200
    assert verification_response.json() == {
        "participant_id": onboarding_response.json()["participant_id"],
        "email_verified": True,
    }


def test_production_self_service_email_delivery_failure_is_visible(
    monkeypatch,
) -> None:
    recipient_email = "smtp.failure@example.test"

    class FailingSmtp:
        def __init__(self, _host: str, _port: int, timeout: int):
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def send_message(self, _message):
            raise RuntimeError("smtp unavailable")

    monkeypatch.setenv("SUNTERRA_ENV", "production")
    monkeypatch.setenv("SUNTERRA_PUBLIC_ROLLOUT_APPROVED", "1")
    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "smtp-production-secret")
    monkeypatch.setenv("SUNTERRA_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SUNTERRA_SMTP_PORT", "587")
    monkeypatch.setenv("SUNTERRA_SMTP_FROM_EMAIL", "noreply@portal.example.test")
    monkeypatch.setattr("smtplib.SMTP", FailingSmtp)
    monkeypatch.setitem(
        USER_ACCOUNTS,
        "smtp-failure-admin",
        UserAccountRecord(
            id="smtp-failure-admin",
            email="smtp-failure-admin@example.test",
            display_name="SMTP Failure Admin",
            role=Role.LEG_ADMIN,
            active=True,
        ),
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={"email": recipient_email, "display_name": "SMTP Failure"},
    )
    admin_token = create_access_token(
        CurrentUser(
            id="smtp-failure-admin",
                email="smtp-failure-admin@example.test",
                display_name="SMTP Failure Admin",
                role=Role.LEG_ADMIN,
                mfa_satisfied=True,
            ),
        )
    events_response = client.get(
        f"/api/admin/communication-events?recipient_email={recipient_email}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Email delivery failed"}
    assert events_response.status_code == 200
    assert [event["status"] for event in events_response.json()] == ["failed"]
