import { type FormEvent, useEffect, useState } from "react";

import "./styles.css";

type HealthStatus = {
  status: string;
  service: string;
  version: string;
};

type Role = "participant" | "leg_admin" | "partner_admin" | "platform_admin";

type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  role: Role;
};

type ParticipantInvitation = {
  token: string;
  email: string;
  display_name: string;
  leg_id: "basadingen";
  status: "pending_email_verification";
};

type InvitationAcceptResponse = {
  access_token: string;
  token_type: "bearer";
  participant_id: string;
  email_verification_required: boolean;
};

type EmailVerificationResponse = {
  participant_id: string;
  email_verified: boolean;
};

type ParticipantMembership = {
  participant_id: string;
  display_name: string;
  email: string;
  leg_id: "basadingen";
  leg_name: string;
  membership_status: "active";
  billing_notice: string;
};

type BackendState =
  | { kind: "checking" }
  | { kind: "connected"; health: HealthStatus }
  | { kind: "offline" };

type SessionState =
  | { kind: "anonymous" }
  | { kind: "authenticated"; token: string; user: CurrentUser };

const demoRoles: Array<{ role: Role; label: string; workspaceTitle: string }> = [
  {
    role: "participant",
    label: "Teilnehmer",
    workspaceTitle: "Mein Mitgliederbereich",
  },
  {
    role: "leg_admin",
    label: "LEG Admin",
    workspaceTitle: "LEG Verwaltung",
  },
  {
    role: "partner_admin",
    label: "Gemeinde/EW",
    workspaceTitle: "Gemeinde/EW Arbeitsplatz",
  },
  {
    role: "platform_admin",
    label: "Plattform",
    workspaceTitle: "Plattform Administration",
  },
];

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
const devTokenStorageKey = "sunterra.devToken";

export function App() {
  const [backend, setBackend] = useState<BackendState>({ kind: "checking" });
  const [session, setSession] = useState<SessionState>({ kind: "anonymous" });
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteDisplayName, setInviteDisplayName] = useState("");
  const [participantInvitation, setParticipantInvitation] =
    useState<ParticipantInvitation | null>(null);
  const [onboardingToken, setOnboardingToken] = useState("");
  const [emailVerification, setEmailVerification] =
    useState<EmailVerificationResponse | null>(null);
  const [participantMembership, setParticipantMembership] =
    useState<ParticipantMembership | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadHealth() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/health`);
        const health = (await response.json()) as HealthStatus;

        if (isMounted) {
          setBackend({ kind: "connected", health });
        }
      } catch {
        if (isMounted) {
          setBackend({ kind: "offline" });
        }
      }
    }

    void loadHealth();

    return () => {
      isMounted = false;
    };
  }, []);

  async function loadCurrentUser(token: string) {
    const response = await fetch(`${apiBaseUrl}/api/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      window.localStorage.removeItem(devTokenStorageKey);
      setSession({ kind: "anonymous" });
      return;
    }

    const user = (await response.json()) as CurrentUser;
    setSession({ kind: "authenticated", token, user });
  }

  function loginAs(role: Role) {
    const token = `dev:${role}`;
    window.localStorage.setItem(devTokenStorageKey, token);
    void loadCurrentUser(token);
  }

  async function createParticipantInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    const response = await fetch(
      `${apiBaseUrl}/api/admin/participant-invitations`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: inviteEmail,
          display_name: inviteDisplayName,
        }),
      },
    );

    if (response.ok) {
      const invitation = (await response.json()) as ParticipantInvitation;
      setParticipantInvitation(invitation);
    }
  }

  async function acceptParticipantInvitation(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const acceptResponse = await fetch(
      `${apiBaseUrl}/api/auth/invitations/${onboardingToken}/accept`,
      {
        method: "POST",
      },
    );
    const acceptance =
      (await acceptResponse.json()) as InvitationAcceptResponse;

    if (!acceptance.email_verification_required) {
      return;
    }

    const verifyResponse = await fetch(
      `${apiBaseUrl}/api/auth/email-verifications/${onboardingToken}/verify`,
      {
        method: "POST",
      },
    );
    const verification =
      (await verifyResponse.json()) as EmailVerificationResponse;
    setEmailVerification(verification);

    if (!verification.email_verified) {
      return;
    }

    const membershipResponse = await fetch(
      `${apiBaseUrl}/api/participants/me/membership`,
      {
        headers: {
          Authorization: `Bearer ${acceptance.access_token}`,
        },
      },
    );
    const membership =
      (await membershipResponse.json()) as Partial<ParticipantMembership>;

    if (membership.membership_status) {
      setParticipantMembership(membership as ParticipantMembership);
    }
  }

  const activeWorkspace =
    session.kind === "authenticated"
      ? demoRoles.find((demoRole) => demoRole.role === session.user.role)
      : undefined;

  return (
    <main className="portal-shell">
      <section className="hero-band" aria-labelledby="portal-title">
        <p className="eyebrow">SunTerra LEG Basadingen</p>
        <h1 id="portal-title">SunTerra LEG Portal</h1>
        <p className="subtitle">Mitglieder- und Mutationsportal</p>
      </section>

      <section className="status-panel" aria-label="Systemstatus">
        <span
          className={`status-dot status-dot--${backend.kind}`}
          aria-hidden="true"
        />
        <div>
          <p className="status-label">
            {backend.kind === "connected"
              ? "Backend verbunden"
              : backend.kind === "offline"
                ? "Backend nicht erreichbar"
                : "Verbindung wird geprüft"}
          </p>
          {backend.kind === "connected" ? (
            <p className="status-detail">
              {backend.health.service} {backend.health.version}
            </p>
          ) : backend.kind === "offline" ? (
            <p className="status-detail">Die Portaloberfläche ist geladen.</p>
          ) : null}
        </div>
      </section>

      <section className="workspace-panel" aria-label="Geschützter Arbeitsbereich">
        {participantMembership ? (
          <div className="membership-workspace">
            <h2>Mein Mitgliederbereich</h2>
            <p>{participantMembership.display_name}</p>
            <dl className="membership-details">
              <div>
                <dt>E-Mail</dt>
                <dd>{participantMembership.email}</dd>
              </div>
              <div>
                <dt>LEG</dt>
                <dd>{participantMembership.leg_name}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>Mitgliedschaft aktiv</dd>
              </div>
            </dl>
            <p className="billing-notice">
              {participantMembership.billing_notice}
            </p>
            {emailVerification ? (
              <div className="invitation-result" role="status">
                <p>E-Mail verifiziert</p>
                <p>{emailVerification.participant_id}</p>
              </div>
            ) : null}
          </div>
        ) : session.kind === "authenticated" && activeWorkspace ? (
          <div>
            <h2>{activeWorkspace.workspaceTitle}</h2>
            <p>{session.user.display_name}</p>
            {session.user.role === "leg_admin" ? (
              <form
                className="invitation-form"
                onSubmit={createParticipantInvitation}
              >
                <label>
                  E-Mail
                  <input
                    type="email"
                    value={inviteEmail}
                    onChange={(event) => setInviteEmail(event.target.value)}
                    required
                  />
                </label>
                <label>
                  Anzeigename
                  <input
                    type="text"
                    value={inviteDisplayName}
                    onChange={(event) =>
                      setInviteDisplayName(event.target.value)
                    }
                    required
                  />
                </label>
                <button type="submit">Einladung erstellen</button>
                {participantInvitation ? (
                  <div className="invitation-result" role="status">
                    <p>Einladung erstellt</p>
                    <p>{participantInvitation.display_name}</p>
                    <p>{participantInvitation.token}</p>
                  </div>
                ) : null}
              </form>
            ) : null}
          </div>
        ) : (
          <>
            <div>
              <h2>Anmeldung erforderlich</h2>
              <p>Wähle für die lokale Entwicklung eine Demo-Rolle.</p>
            </div>
            <div className="role-actions" aria-label="Demo-Rollen">
              {demoRoles.map((demoRole) => (
                <button
                  key={demoRole.role}
                  type="button"
                  onClick={() => loginAs(demoRole.role)}
                >
                  {demoRole.label}
                </button>
              ))}
            </div>
            <form
              className="invitation-form"
              onSubmit={acceptParticipantInvitation}
            >
              <label>
                Einladungstoken
                <input
                  type="text"
                  value={onboardingToken}
                  onChange={(event) => setOnboardingToken(event.target.value)}
                  required
                />
              </label>
              <button type="submit">Einladung annehmen und verifizieren</button>
              {emailVerification ? (
                <div className="invitation-result" role="status">
                  <p>E-Mail verifiziert</p>
                  <p>{emailVerification.participant_id}</p>
                </div>
              ) : null}
            </form>
          </>
        )}
      </section>
    </main>
  );
}
