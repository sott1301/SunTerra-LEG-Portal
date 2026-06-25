from fastapi.testclient import TestClient

from sunterra_leg_portal.auth import CurrentUser, Role, create_access_token
from sunterra_leg_portal.main import USER_ACCOUNTS, UserAccountRecord
from sunterra_leg_portal.main import app


def test_leg_admin_can_invite_participant_for_basadingen() -> None:
    response = TestClient(app).post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "anna.mueller@example.test", "display_name": "Anna Mueller"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload.pop("token")
    assert payload == {
        "email": "anna.mueller@example.test",
        "display_name": "Anna Mueller",
        "leg_id": "basadingen",
        "status": "pending_email_verification",
    }


def test_production_participant_invitation_sends_smtp_acceptance_link(
    monkeypatch,
) -> None:
    sent_messages = []
    recipient_email = "smtp.invited@example.test"

    class FakeSmtp:
        def __init__(self, _host: str, _port: int, timeout: int):
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setenv("SUNTERRA_ENV", "production")
    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "smtp-production-secret")
    monkeypatch.setenv("SUNTERRA_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SUNTERRA_SMTP_PORT", "587")
    monkeypatch.setenv("SUNTERRA_SMTP_FROM_EMAIL", "noreply@portal.example.test")
    monkeypatch.setenv("SUNTERRA_PUBLIC_BASE_URL", "https://portal.example.test")
    monkeypatch.setattr("smtplib.SMTP", FakeSmtp)
    monkeypatch.setitem(
        USER_ACCOUNTS,
        "smtp-invitation-admin",
        UserAccountRecord(
            id="smtp-invitation-admin",
            email="smtp-invitation-admin@example.test",
            display_name="SMTP Invitation Admin",
            role=Role.LEG_ADMIN,
            active=True,
        ),
    )
    admin_token = create_access_token(
        CurrentUser(
            id="smtp-invitation-admin",
            email="smtp-invitation-admin@example.test",
            display_name="SMTP Invitation Admin",
            role=Role.LEG_ADMIN,
            mfa_satisfied=True,
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": recipient_email, "display_name": "SMTP Invited"},
    )

    assert response.status_code == 201
    invitation = response.json()
    assert len(sent_messages) == 1
    message_body = sent_messages[0].get_content()
    acceptance_url = (
        "https://portal.example.test/api/auth/invitations/"
        f"{invitation['token']}/accept"
    )
    assert acceptance_url in message_body
    acceptance_response = client.get(
        acceptance_url.removeprefix("https://portal.example.test"),
    )

    assert acceptance_response.status_code == 200
    assert acceptance_response.json()["participant_id"]
    events_response = client.get(
        f"/api/admin/communication-events?recipient_email={recipient_email}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert events_response.status_code == 200
    assert [event["status"] for event in events_response.json()] == [
        "sent",
        "sent",
    ]


def test_production_participant_invitation_email_failure_is_visible(
    monkeypatch,
) -> None:
    recipient_email = "smtp.invitation.failure@example.test"

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
    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "smtp-production-secret")
    monkeypatch.setenv("SUNTERRA_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SUNTERRA_SMTP_PORT", "587")
    monkeypatch.setenv("SUNTERRA_SMTP_FROM_EMAIL", "noreply@portal.example.test")
    monkeypatch.setattr("smtplib.SMTP", FailingSmtp)
    monkeypatch.setitem(
        USER_ACCOUNTS,
        "smtp-invitation-failure-admin",
        UserAccountRecord(
            id="smtp-invitation-failure-admin",
            email="smtp-invitation-failure-admin@example.test",
            display_name="SMTP Invitation Failure Admin",
            role=Role.LEG_ADMIN,
            active=True,
        ),
    )
    admin_token = create_access_token(
        CurrentUser(
            id="smtp-invitation-failure-admin",
            email="smtp-invitation-failure-admin@example.test",
            display_name="SMTP Invitation Failure Admin",
            role=Role.LEG_ADMIN,
            mfa_satisfied=True,
        ),
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": recipient_email, "display_name": "SMTP Failure"},
    )
    events_response = client.get(
        f"/api/admin/communication-events?recipient_email={recipient_email}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Email delivery failed"}
    assert events_response.status_code == 200
    assert [event["status"] for event in events_response.json()] == ["failed"]


def test_production_invitation_acceptance_email_failure_is_visible(
    monkeypatch,
) -> None:
    recipient_email = "smtp.accept.failure@example.test"
    sent_messages = []

    class FailingSecondSmtp:
        def __init__(self, _host: str, _port: int, timeout: int):
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def send_message(self, message):
            sent_messages.append(message)
            if len(sent_messages) == 2:
                raise RuntimeError("smtp unavailable")

    monkeypatch.setenv("SUNTERRA_ENV", "production")
    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "smtp-production-secret")
    monkeypatch.setenv("SUNTERRA_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SUNTERRA_SMTP_PORT", "587")
    monkeypatch.setenv("SUNTERRA_SMTP_FROM_EMAIL", "noreply@portal.example.test")
    monkeypatch.setattr("smtplib.SMTP", FailingSecondSmtp)
    monkeypatch.setitem(
        USER_ACCOUNTS,
        "smtp-accept-failure-admin",
        UserAccountRecord(
            id="smtp-accept-failure-admin",
            email="smtp-accept-failure-admin@example.test",
            display_name="SMTP Accept Failure Admin",
            role=Role.LEG_ADMIN,
            active=True,
        ),
    )
    admin_token = create_access_token(
        CurrentUser(
            id="smtp-accept-failure-admin",
            email="smtp-accept-failure-admin@example.test",
            display_name="SMTP Accept Failure Admin",
            role=Role.LEG_ADMIN,
            mfa_satisfied=True,
        ),
    )
    client = TestClient(app, raise_server_exceptions=False)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": recipient_email, "display_name": "SMTP Accept Failure"},
    ).json()

    response = client.post(f"/api/auth/invitations/{invitation['token']}/accept")
    events_response = client.get(
        f"/api/admin/communication-events?recipient_email={recipient_email}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Email delivery failed"}
    assert events_response.status_code == 200
    assert [event["status"] for event in events_response.json()] == [
        "sent",
        "failed",
    ]


def test_participant_cannot_invite_participant() -> None:
    response = TestClient(app).post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:participant"},
        json={"email": "blocked@example.test", "display_name": "Blocked Person"},
    )

    assert response.status_code == 403


def test_invited_participant_can_accept_invitation() -> None:
    client = TestClient(app)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "ben.keller@example.test", "display_name": "Ben Keller"},
    ).json()

    response = client.post(f"/api/auth/invitations/{invitation['token']}/accept")

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"].startswith("dev:participant:")
    assert payload["token_type"] == "bearer"
    assert payload["participant_id"]
    assert payload["email_verification_required"] is True


def test_invited_participant_can_verify_email_after_accepting() -> None:
    client = TestClient(app)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "carla.graf@example.test", "display_name": "Carla Graf"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()

    response = client.post(
        f"/api/auth/email-verifications/{invitation['token']}/verify",
    )

    assert response.status_code == 200
    assert response.json() == {
        "participant_id": accepted["participant_id"],
        "email_verified": True,
    }


def test_accepted_unverified_participant_cannot_open_own_membership_workspace() -> None:
    client = TestClient(app)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "clara.steiner@example.test", "display_name": "Clara Steiner"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()

    response = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {accepted['access_token']}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Email verification required"}


def test_verified_invited_participant_can_use_issued_access_token_for_me() -> None:
    client = TestClient(app)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "dario.huber@example.test", "display_name": "Dario Huber"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {accepted['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": accepted["participant_id"],
        "email": "dario.huber@example.test",
        "display_name": "Dario Huber",
        "role": "participant",
        "mfa_satisfied": False,
    }


def test_verified_participant_can_open_own_membership_workspace() -> None:
    client = TestClient(app)
    invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "eva.baumann@example.test", "display_name": "Eva Baumann"},
    ).json()
    accepted = client.post(
        f"/api/auth/invitations/{invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{invitation['token']}/verify")

    response = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {accepted['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "participant_id": accepted["participant_id"],
        "display_name": "Eva Baumann",
        "email": "eva.baumann@example.test",
        "leg_id": "basadingen",
        "leg_name": "SunTerra LEG Basadingen",
        "membership_status": "active",
        "eligibility_status": "approved",
        "eligibility_review_reason": None,
        "billing_notice": "Abrechnung und Inkasso bleiben bei Gemeinde/EW.",
    }


def test_non_participant_cannot_open_participant_membership_workspace() -> None:
    response = TestClient(app).get(
        "/api/participants/me/membership",
        headers={"Authorization": "Bearer dev:leg_admin"},
    )

    assert response.status_code == 403


def test_participant_cannot_read_another_participants_membership() -> None:
    client = TestClient(app)
    first_invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "fiona.meier@example.test", "display_name": "Fiona Meier"},
    ).json()
    first_accepted = client.post(
        f"/api/auth/invitations/{first_invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{first_invitation['token']}/verify")
    second_invitation = client.post(
        "/api/admin/participant-invitations",
        headers={"Authorization": "Bearer dev:leg_admin"},
        json={"email": "gian.wyss@example.test", "display_name": "Gian Wyss"},
    ).json()
    second_accepted = client.post(
        f"/api/auth/invitations/{second_invitation['token']}/accept",
    ).json()
    client.post(f"/api/auth/email-verifications/{second_invitation['token']}/verify")

    response = client.get(
        f"/api/participants/{second_accepted['participant_id']}/membership",
        headers={"Authorization": f"Bearer {first_accepted['access_token']}"},
    )

    assert response.status_code == 403
