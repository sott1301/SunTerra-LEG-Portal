from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def start_self_service_onboarding(client: TestClient, email: str = "selina.frei@example.test") -> dict:
    return client.post(
        "/api/auth/self-service-onboarding-requests",
        json={
            "email": email,
            "display_name": "Selina Frei",
        },
    ).json()


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
        "membership_status": "active",
        "billing_notice": "Abrechnung und Inkasso bleiben bei Gemeinde/EW.",
    }


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
