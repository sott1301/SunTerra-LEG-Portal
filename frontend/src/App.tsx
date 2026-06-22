import { useEffect, useState } from "react";

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

type BackendState =
  | { kind: "checking" }
  | { kind: "connected"; health: HealthStatus }
  | { kind: "offline" };

type SessionState =
  | { kind: "anonymous" }
  | { kind: "authenticated"; user: CurrentUser };

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
    setSession({ kind: "authenticated", user });
  }

  function loginAs(role: Role) {
    const token = `dev:${role}`;
    window.localStorage.setItem(devTokenStorageKey, token);
    void loadCurrentUser(token);
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
        {session.kind === "authenticated" && activeWorkspace ? (
          <div>
            <h2>{activeWorkspace.workspaceTitle}</h2>
            <p>{session.user.display_name}</p>
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
          </>
        )}
      </section>
    </main>
  );
}
