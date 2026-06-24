import base64
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def test_login_issues_jwt_and_me_resolves_user() -> None:
    client = TestClient(app)

    login = client.post(
        "/api/auth/login",
        json={"email": "leg-admin@example.test", "password": "SunTerra123!"},
    )

    assert login.status_code == 200
    payload = login.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"].count(".") == 2
    assert payload["expires_in_seconds"] == 8 * 60 * 60
    assert payload["user"]["role"] == "leg_admin"
    _header, token_payload, _signature = payload["access_token"].split(".")
    claims = json.loads(
        base64.urlsafe_b64decode(token_payload + "=" * (-len(token_payload) % 4)),
    )
    assert claims["exp"] - claims["iat"] == 8 * 60 * 60

    me = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )

    assert me.status_code == 200
    assert me.json()["email"] == "leg-admin@example.test"


def test_login_token_is_bound_to_configured_secret_key(monkeypatch) -> None:
    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "issue-35-secret-a")
    client = TestClient(app)

    token = client.post(
        "/api/auth/login",
        json={"email": "leg-admin@example.test", "password": "SunTerra123!"},
    ).json()["access_token"]

    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "issue-35-secret-b")
    rejected = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rejected.status_code == 401

    monkeypatch.setenv("SUNTERRA_SECRET_KEY", "issue-35-secret-a")
    accepted = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["email"] == "leg-admin@example.test"


def test_login_rejects_wrong_password_and_inactive_user() -> None:
    client = TestClient(app)

    wrong_password = client.post(
        "/api/auth/login",
        json={"email": "leg-admin@example.test", "password": "wrong"},
    )
    assert wrong_password.status_code == 401

    platform = client.post(
        "/api/auth/login",
        json={"email": "platform-admin@example.test", "password": "SunTerra123!"},
    ).json()["access_token"]
    user = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": "inactive-leg-admin@example.test",
            "display_name": "Inactive LEG Admin",
            "role": "leg_admin",
            "password": "Start123!",
        },
    ).json()
    deactivated = client.patch(
        f"/api/admin/users/{user['id']}",
        headers={"Authorization": f"Bearer {platform}"},
        json={"active": False},
    )
    assert deactivated.status_code == 200

    inactive_login = client.post(
        "/api/auth/login",
        json={
            "email": "inactive-leg-admin@example.test",
            "password": "Start123!",
        },
    )
    assert inactive_login.status_code == 401


def test_email_first_self_service_and_verified_account_setup() -> None:
    client = TestClient(app)

    started = client.post(
        "/api/auth/self-service-onboarding-requests",
        json={"email": "email-first@example.test"},
    )

    assert started.status_code == 201
    onboarding = started.json()
    assert onboarding["participant_status"] == "pending_email_verification"
    assert onboarding["access_token"].count(".") == 2

    setup_before_verification = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={"display_name": "Email First", "password": "Start123!"},
    )
    assert setup_before_verification.status_code == 403

    verified = client.post(
        f"/api/auth/email-verifications/{onboarding['dev_email_verification_token']}/verify",
    )
    assert verified.status_code == 200

    setup_checkpoint = client.get(
        "/api/participants/me/identity-checkpoint?action=membership_activation",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
    )
    membership_before_setup = client.get(
        "/api/participants/me/membership",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
    )
    assert setup_checkpoint.status_code == 200
    assert setup_checkpoint.json() == {
        "action": "membership_activation",
        "required_level": "account_setup",
        "current_level": "email_verified",
        "satisfied": False,
    }
    assert membership_before_setup.status_code == 403
    assert membership_before_setup.json() == {"detail": "Account setup required"}

    setup = client.post(
        "/api/auth/participant-account-setup",
        headers={"Authorization": f"Bearer {onboarding['access_token']}"},
        json={"display_name": "Email First", "password": "Start123!"},
    )
    assert setup.status_code == 200
    assert setup.json()["user"]["display_name"] == "Email First"

    login = client.post(
        "/api/auth/login",
        json={"email": "email-first@example.test", "password": "Start123!"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "participant"


def test_platform_admin_manages_user_accounts_but_not_partner_creation() -> None:
    client = TestClient(app)
    platform = client.post(
        "/api/auth/login",
        json={"email": "platform-admin@example.test", "password": "SunTerra123!"},
    ).json()["access_token"]

    created = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": "new-platform@example.test",
            "display_name": "New Platform",
            "role": "platform_admin",
            "password": "Start123!",
        },
    )

    assert created.status_code == 201
    account = created.json()
    assert account["role"] == "platform_admin"
    assert "password_hash" not in account

    listed = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
    )
    assert listed.status_code == 200
    assert any(user["email"] == "new-platform@example.test" for user in listed.json())

    updated = client.patch(
        f"/api/admin/users/{account['id']}",
        headers={"Authorization": f"Bearer {platform}"},
        json={"display_name": "Renamed Platform", "active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Renamed Platform"
    assert updated.json()["active"] is False

    partner_attempt = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": "partner-via-platform@example.test",
            "display_name": "Partner Via Platform",
            "role": "partner_admin",
            "password": "Start123!",
        },
    )
    assert partner_attempt.status_code == 400


def test_platform_admin_updates_internal_account_and_resets_start_password() -> None:
    client = TestClient(app)
    platform = client.post(
        "/api/auth/login",
        json={"email": "platform-admin@example.test", "password": "SunTerra123!"},
    ).json()["access_token"]
    email = f"managed-leg-admin-{uuid4().hex}@example.test"

    created = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": email,
            "display_name": "Managed LEG Admin",
            "role": "leg_admin",
            "password": "Start123!",
        },
    )

    assert created.status_code == 201
    account = created.json()
    assert account["role"] == "leg_admin"

    updated = client.patch(
        f"/api/admin/users/{account['id']}",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "display_name": "Managed Platform Admin",
            "role": "platform_admin",
            "active": False,
        },
    )

    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Managed Platform Admin"
    assert updated.json()["role"] == "platform_admin"
    assert updated.json()["active"] is False

    reactivated = client.patch(
        f"/api/admin/users/{account['id']}",
        headers={"Authorization": f"Bearer {platform}"},
        json={"active": True},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["active"] is True

    reset = client.post(
        f"/api/admin/users/{account['id']}/reset-password",
        headers={"Authorization": f"Bearer {platform}"},
        json={"password": "ChangedStart123!"},
    )
    assert reset.status_code == 200
    assert reset.json()["email"] == email
    assert "password_hash" not in reset.json()

    old_password = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Start123!"},
    )
    assert old_password.status_code == 401

    new_password = client.post(
        "/api/auth/login",
        json={"email": email, "password": "ChangedStart123!"},
    )
    assert new_password.status_code == 200
    assert new_password.json()["user"]["display_name"] == "Managed Platform Admin"
    assert new_password.json()["user"]["role"] == "platform_admin"


@pytest.mark.parametrize("role", ["participant", "partner_admin"])
def test_platform_admin_cannot_create_membership_or_partner_accounts(role: str) -> None:
    client = TestClient(app)
    platform = client.post(
        "/api/auth/login",
        json={"email": "platform-admin@example.test", "password": "SunTerra123!"},
    ).json()["access_token"]

    created = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "email": f"forbidden-{role}-{uuid4().hex}@example.test",
            "display_name": "Forbidden User",
            "role": role,
            "password": "Start123!",
        },
    )

    assert created.status_code == 400


def test_non_platform_users_cannot_use_user_management_apis() -> None:
    client = TestClient(app)
    leg_admin = client.post(
        "/api/auth/login",
        json={"email": "leg-admin@example.test", "password": "SunTerra123!"},
    ).json()["access_token"]

    listed = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {leg_admin}"},
    )
    created = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {leg_admin}"},
        json={
            "email": f"forbidden-leg-admin-{uuid4().hex}@example.test",
            "display_name": "Forbidden LEG Admin",
            "role": "leg_admin",
            "password": "Start123!",
        },
    )
    updated = client.patch(
        "/api/admin/users/dev-leg-admin",
        headers={"Authorization": f"Bearer {leg_admin}"},
        json={"display_name": "Forbidden Update"},
    )
    reset = client.post(
        "/api/admin/users/dev-leg-admin/reset-password",
        headers={"Authorization": f"Bearer {leg_admin}"},
        json={"password": "ForbiddenStart123!"},
    )

    assert listed.status_code == 403
    assert created.status_code == 403
    assert updated.status_code == 403
    assert reset.status_code == 403


def test_leg_admin_creates_partner_admin_and_publishes_documents() -> None:
    client = TestClient(app)
    leg_admin = client.post(
        "/api/auth/login",
        json={"email": "leg-admin@example.test", "password": "SunTerra123!"},
    ).json()["access_token"]

    partner = client.post(
        "/api/admin/partner-admin-users",
        headers={"Authorization": f"Bearer {leg_admin}"},
        json={
            "email": "ew-admin@example.test",
            "display_name": "EW Admin",
            "organization": "Gemeinde/EW Basadingen",
            "password": "Start123!",
        },
    )

    assert partner.status_code == 201
    assert partner.json()["role"] == "partner_admin"
    assert partner.json()["organization"] == "Gemeinde/EW Basadingen"

    partner_login = client.post(
        "/api/auth/login",
        json={"email": "ew-admin@example.test", "password": "Start123!"},
    )
    assert partner_login.status_code == 200
    assert partner_login.json()["user"]["role"] == "partner_admin"

    published = client.post(
        "/api/admin/document-versions",
        headers={"Authorization": f"Bearer {leg_admin}"},
        json={
            "document_key": "portal_terms",
            "title": "Teilnahmebedingungen",
            "version": "2026-06",
            "content": "Dokumentinhalt",
            "context": "participant_onboarding",
        },
    )
    assert published.status_code == 201

    platform = client.post(
        "/api/auth/login",
        json={"email": "platform-admin@example.test", "password": "SunTerra123!"},
    ).json()["access_token"]
    forbidden = client.post(
        "/api/admin/document-versions",
        headers={"Authorization": f"Bearer {platform}"},
        json={
            "document_key": "portal_terms",
            "title": "Nicht Plattform",
            "version": "2026-07",
            "content": "Nicht erlaubt",
            "context": "participant_onboarding",
        },
    )
    assert forbidden.status_code == 403

    readable = client.get(
        "/api/admin/document-versions",
        headers={"Authorization": f"Bearer {platform}"},
    )
    assert readable.status_code == 200
    assert any(document["version"] == "2026-06" for document in readable.json())
