import { useEffect, useState } from "react";

import "./styles.css";

type HealthStatus = {
  status: string;
  service: string;
  version: string;
};

type BackendState =
  | { kind: "checking" }
  | { kind: "connected"; health: HealthStatus }
  | { kind: "offline" };

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export function App() {
  const [backend, setBackend] = useState<BackendState>({ kind: "checking" });

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
    </main>
  );
}
