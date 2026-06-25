import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

function renderAt(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

describe("Portal shell", () => {
  afterEach(() => {
    window.localStorage.clear();
    window.history.pushState({}, "", "/");
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("zeigt eine deutsche Portal-Shell mit verbundenem Backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        return new Response(
          JSON.stringify({
            status: "ok",
            service: "sunterra-leg-portal",
            version: "0.1.0",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }),
    );

    renderAt("/");

    expect(
      screen.getByRole("heading", { name: "SunTerra LEG Portal" }),
    ).toBeTruthy();
    expect(screen.getByText("Teilnahme starten")).toBeTruthy();
    expect(
      screen.getByText(
        "Mein Portal, LEG-Verwaltung, Gemeinde/EW und Benutzerverwaltung fuehren direkt zu den relevanten Funktionen.",
      ),
    ).toBeTruthy();
    expect(screen.queryByLabelText("Demo-Rollen")).toBeNull();
    expect(screen.queryByRole("button", { name: "Teilnehmer" })).toBeNull();
    expect(await screen.findByText("Backend verbunden")).toBeTruthy();
    expect(screen.getByText("sunterra-leg-portal 0.1.0")).toBeTruthy();
  });

  it("navigiert von der Public Landing zu Registrierung und Login", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        return new Response(
          JSON.stringify({
            status: "ok",
            service: "sunterra-leg-portal",
            version: "0.1.0",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }),
    );

    const { unmount } = renderAt("/");
    expect(await screen.findByText("Backend verbunden")).toBeTruthy();

    const publicLanding = screen.getByRole("region", {
      name: "SunTerra LEG Portal",
    });
    fireEvent.click(
      within(publicLanding).getByRole("button", {
        name: "Teilnahme starten",
      }),
    );

    expect(window.location.pathname).toBe("/registrieren");
    expect(
      screen.getByRole("heading", { name: "Teilnahme starten" }),
    ).toBeTruthy();

    unmount();
    renderAt("/");
    expect(await screen.findByText("Backend verbunden")).toBeTruthy();

    const refreshedPublicLanding = screen.getByRole("region", {
      name: "SunTerra LEG Portal",
    });
    fireEvent.click(
      within(refreshedPublicLanding).getByRole("button", {
        name: "Einloggen",
      }),
    );

    expect(window.location.pathname).toBe("/login");
    expect(screen.getByRole("heading", { name: "Einloggen" })).toBeTruthy();

  });

  it("fordert ueber die oeffentliche Reset-Seite einen Passwort-Link an", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/password-reset/request")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          email: "reset.ui@example.test",
        });

        return new Response(
          JSON.stringify({ status: "password_reset_requested" }),
          {
            status: 202,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/reset-password");

    expect(
      screen.getByRole("heading", { name: "Passwort zuruecksetzen" }),
    ).toBeTruthy();
    fireEvent.change(screen.getByLabelText("E-Mail fuer Passwortreset"), {
      target: { value: "reset.ui@example.test" },
    });
    screen.getByRole("button", { name: "Reset-Link senden" }).click();

    expect(
      await screen.findByText(
        "Wenn ein aktives Konto existiert, wurde ein Reset-Link gesendet.",
      ),
    ).toBeTruthy();
  });

  it("bestaetigt ein neues Passwort mit dem Reset-Token aus dem Link", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/password-reset/confirm")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          token: "reset-token-ui",
          password: "NeuesReset123!",
        });

        return new Response(
          JSON.stringify({ status: "password_reset_completed" }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/reset-password?token=reset-token-ui");

    expect(
      screen.getByRole("heading", { name: "Passwort zuruecksetzen" }),
    ).toBeTruthy();
    expect(screen.getByText("Reset-Token erkannt")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Neues Passwort"), {
      target: { value: "NeuesReset123!" },
    });
    screen.getByRole("button", { name: "Passwort aktualisieren" }).click();

    expect(await screen.findByText("Passwort wurde aktualisiert")).toBeTruthy();
  });

  it("blockiert den geschützten Arbeitsbereich ohne Anmeldung", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        return new Response(
          JSON.stringify({
            status: "ok",
            service: "sunterra-leg-portal",
            version: "0.1.0",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }),
    );

    renderAt("/app");

    expect(await screen.findByText("Backend verbunden")).toBeTruthy();
    expect(screen.getByText("Anmeldung erforderlich")).toBeTruthy();
    expect(
      screen.getByText("Fuer die lokale Entwicklung kann eine Demo-Rolle genutzt werden."),
    ).toBeTruthy();
  });

  it("blendet lokale Demo-Rollen in Production aus", async () => {
    vi.stubEnv("DEV", false);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        return new Response(
          JSON.stringify({
            status: "ok",
            service: "sunterra-leg-portal",
            version: "0.1.0",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }),
    );

    const { unmount } = renderAt("/login");

    expect(await screen.findByText("Backend verbunden")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Einloggen" })).toBeTruthy();
    expect(screen.queryByLabelText("Demo-Rollen")).toBeNull();
    expect(screen.queryByRole("button", { name: "Teilnehmer" })).toBeNull();

    unmount();
    renderAt("/app");

    expect(await screen.findByText("Backend verbunden")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Einloggen" })).toBeTruthy();
    expect(screen.queryByLabelText("Demo-Rollen")).toBeNull();
  });

  it("meldet eine Teilnehmer-Demo-Rolle an und zeigt ihren Arbeitsbereich", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-participant",
            email: "participant@example.test",
            display_name: "Teilnehmer Demo",
            role: "participant",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Teilnehmer" }).click();

    expect(await screen.findByText("Mein Portal")).toBeTruthy();
    expect(screen.getByText("Teilnehmer Demo")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/me",
      expect.objectContaining({
        headers: { Authorization: "Bearer dev:participant" },
      }),
    );
  });

  it("sendet Pilotfeedback aus dem Teilnehmer-Arbeitsbereich", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-participant",
            email: "participant@example.test",
            display_name: "Teilnehmer Demo",
            role: "participant",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/pilot-feedback")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:participant",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          category: "rollout_gate",
          message: "Der Pilotablauf ist bereit fuer das Go/No-Go.",
          context: "mein-portal",
        });

        return new Response(
          JSON.stringify({
            id: "pilot-feedback-1",
            category: "rollout_gate",
            message: "Der Pilotablauf ist bereit fuer das Go/No-Go.",
            context: "mein-portal",
            user_id: "dev-participant",
            user_email: "participant@example.test",
            user_role: "participant",
            status: "submitted",
            created_at: "2026-06-24T21:00:00+00:00",
          }),
          {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Teilnehmer" }).click();

    expect(await screen.findByText("Mein Portal")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Feedback-Kategorie"), {
      target: { value: "rollout_gate" },
    });
    fireEvent.change(screen.getByLabelText("Feedback-Kontext"), {
      target: { value: "mein-portal" },
    });
    fireEvent.change(screen.getByLabelText("Pilotfeedback"), {
      target: { value: "Der Pilotablauf ist bereit fuer das Go/No-Go." },
    });
    screen.getByRole("button", { name: "Pilotfeedback senden" }).click();

    expect(await screen.findByText("Pilotfeedback gespeichert")).toBeTruthy();
    expect(screen.getByText("rollout_gate")).toBeTruthy();
  });

  it("markiert Pilotfeedback im LEG-Admin-Arbeitsbereich als rolloutrelevant erledigt", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-leg-admin",
            email: "leg-admin@example.test",
            display_name: "LEG Admin Demo",
            role: "leg_admin",
            mfa_satisfied: true,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/mutation-requests?status=submitted")) {
        return new Response(JSON.stringify([]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/admin/pilot-feedback/pilot-feedback-1")) {
        expect(init?.method).toBe("PATCH");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          status: "resolved",
          rollout_relevance: "blocks_public_rollout",
          admin_note: "In der Go/No-Go-Liste erledigt.",
        });

        return new Response(
          JSON.stringify({
            id: "pilot-feedback-1",
            category: "rollout_gate",
            message: "Vor dem public rollout fehlt eine klare Betreiberfreigabe.",
            context: "go-no-go",
            user_id: "dev-participant",
            user_email: "participant@example.test",
            user_role: "participant",
            status: "resolved",
            rollout_relevance: "blocks_public_rollout",
            admin_note: "In der Go/No-Go-Liste erledigt.",
            reviewed_at: "2026-06-24T21:30:00+00:00",
            reviewed_by: "dev-leg-admin",
            created_at: "2026-06-24T21:00:00+00:00",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/pilot-feedback")) {
        return new Response(
          JSON.stringify([
            {
              id: "pilot-feedback-1",
              category: "rollout_gate",
              message:
                "Vor dem public rollout fehlt eine klare Betreiberfreigabe.",
              context: "go-no-go",
              user_id: "dev-participant",
              user_email: "participant@example.test",
              user_role: "participant",
              status: "submitted",
              rollout_relevance: null,
              admin_note: null,
              reviewed_at: null,
              reviewed_by: null,
              created_at: "2026-06-24T21:00:00+00:00",
            },
          ]),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "LEG Admin" }).click();

    expect(await screen.findByText("LEG-Verwaltung")).toBeTruthy();
    expect(
      await screen.findByText(
        "Vor dem public rollout fehlt eine klare Betreiberfreigabe.",
      ),
    ).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Bearbeitungsnotiz"), {
      target: { value: "In der Go/No-Go-Liste erledigt." },
    });
    screen.getByRole("button", { name: "Rolloutrelevant erledigen" }).click();

    expect(await screen.findByText("blocks_public_rollout")).toBeTruthy();
    expect(screen.getByText("resolved")).toBeTruthy();
    expect(screen.getByText("In der Go/No-Go-Liste erledigt.")).toBeTruthy();
  });

  it.each([
    ["Teilnehmer", "participant", "Mein Portal", "Teilnehmer Demo"],
    ["LEG Admin", "leg_admin", "LEG-Verwaltung", "LEG Admin Demo"],
    [
      "Gemeinde/EW",
      "partner_admin",
      "Gemeinde/EW",
      "Partner Admin Demo",
    ],
    [
      "Benutzerverwaltung",
      "platform_admin",
      "Benutzerverwaltung",
      "Plattform Admin Demo",
    ],
  ])(
    "zeigt den passenden Workspace für %s",
    async (buttonLabel, role, workspaceTitle, displayName) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
          const url = input.toString();

          if (url.endsWith("/api/me")) {
            expect(init?.headers).toEqual({
              Authorization: `Bearer dev:${role}`,
            });

            return new Response(
              JSON.stringify({
                id: `dev-${role}`,
                email: `${role}@example.test`,
                display_name: displayName,
                role,
              }),
              {
                headers: {
                  "Content-Type": "application/json",
                },
              },
            );
          }

          return new Response(
            JSON.stringify({
              status: "ok",
              service: "sunterra-leg-portal",
              version: "0.1.0",
            }),
            {
              headers: {
                "Content-Type": "application/json",
              },
            },
          );
        }),
      );

      renderAt("/login");
      screen.getByRole("button", { name: buttonLabel }).click();

      expect(await screen.findByText(workspaceTitle)).toBeTruthy();
      expect(screen.getByText(displayName)).toBeTruthy();
    },
  );

  it.each([
    ["participant", "participant@example.test", "Teilnehmer Demo", "Mein Portal"],
    ["leg_admin", "leg-admin@example.test", "LEG Admin Demo", "LEG-Verwaltung"],
    [
      "partner_admin",
      "partner-admin@example.test",
      "Partner Admin Demo",
      "Gemeinde/EW",
    ],
    [
      "platform_admin",
      "platform-admin@example.test",
      "Plattform Admin Demo",
      "Benutzerverwaltung",
    ],
  ])(
    "landet nach Passwort-Login direkt im %s Startbereich",
    async (role, email, displayName, workspaceTitle) => {
      const token = `jwt-${role}`;
      const user = {
        id: `jwt-user-${role}`,
        email,
        display_name: displayName,
        role,
      };
      const fetchMock = vi.fn(
        async (input: RequestInfo | URL, init?: RequestInit) => {
          const url = input.toString();

          if (url.endsWith("/api/auth/login")) {
            expect(init?.method).toBe("POST");
            expect(init?.headers).toEqual({
              "Content-Type": "application/json",
            });
            expect(JSON.parse(init?.body as string)).toEqual({
              email,
              password: "SunTerra123!",
            });

            return new Response(
              JSON.stringify({
                access_token: token,
                token_type: "bearer",
                expires_in_seconds: 28800,
                user,
              }),
              {
                headers: {
                  "Content-Type": "application/json",
                },
              },
            );
          }

          if (url.endsWith("/api/me")) {
            expect(init?.headers).toEqual({
              Authorization: `Bearer ${token}`,
            });

            return new Response(JSON.stringify(user), {
              headers: {
                "Content-Type": "application/json",
              },
            });
          }

          if (url.endsWith("/api/participants/me/membership")) {
            return new Response(
              JSON.stringify({
                participant_id: user.id,
                display_name: displayName,
                email,
                leg_id: "basadingen",
                leg_name: "SunTerra LEG Basadingen",
                membership_status: "active",
                billing_notice: "Abrechnung und Inkasso bleiben bei Gemeinde/EW.",
              }),
              {
                headers: {
                  "Content-Type": "application/json",
                },
              },
            );
          }

          if (
            url.endsWith("/api/documents/current?document_key=portal_terms") ||
            url.endsWith("/api/participants/me/contact-channels")
          ) {
            return new Response(JSON.stringify({ detail: "Not found" }), {
              status: 404,
              headers: {
                "Content-Type": "application/json",
              },
            });
          }

          if (
            url.endsWith("/api/admin/mutation-requests") ||
            url.endsWith("/api/partner/mutation-packages") ||
            url.endsWith("/api/partner/tasks") ||
            url.endsWith("/api/admin/users")
          ) {
            return new Response(JSON.stringify([]), {
              headers: {
                "Content-Type": "application/json",
              },
            });
          }

          if (url.endsWith("/api/partner/member-register")) {
            return new Response(
              JSON.stringify({
                leg_id: "basadingen",
                leg_name: "SunTerra LEG Basadingen",
                members: [],
              }),
              {
                headers: {
                  "Content-Type": "application/json",
                },
              },
            );
          }

          return new Response(
            JSON.stringify({
              status: "ok",
              service: "sunterra-leg-portal",
              version: "0.1.0",
            }),
            {
              headers: {
                "Content-Type": "application/json",
              },
            },
          );
        },
      );
      vi.stubGlobal("fetch", fetchMock);

      renderAt("/login");
      window.localStorage.setItem("sunterra.devToken", "dev:participant");
      fireEvent.change(screen.getByLabelText("E-Mail"), {
        target: { value: email },
      });
      fireEvent.change(screen.getByLabelText("Passwort"), {
        target: { value: "SunTerra123!" },
      });
      screen.getByRole("button", { name: "Einloggen" }).click();

      expect(
        await screen.findByRole("heading", { name: workspaceTitle }),
      ).toBeTruthy();
      expect(screen.getByText(displayName)).toBeTruthy();
      await waitFor(() => expect(window.location.pathname).toBe("/app"));
      expect(window.localStorage.getItem("sunterra.accessToken")).toBe(token);
      expect(window.localStorage.getItem("sunterra.devToken")).toBeNull();
    },
  );

  it("sendet den optionalen TOTP-Code beim Passwort-Login", async () => {
    const user = {
      id: "jwt-user-leg-admin",
      email: "leg-admin@example.test",
      display_name: "LEG Admin Demo",
      role: "leg_admin",
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/login")) {
        expect(JSON.parse(init?.body as string)).toEqual({
          email: "leg-admin@example.test",
          password: "SunTerra123!",
          totp_code: "123456",
        });

        return new Response(
          JSON.stringify({
            access_token: "jwt-leg-admin",
            token_type: "bearer",
            expires_in_seconds: 28800,
            user,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/me")) {
        return new Response(JSON.stringify(user), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");

    fireEvent.change(screen.getByLabelText("E-Mail"), {
      target: { value: "leg-admin@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), {
      target: { value: "SunTerra123!" },
    });
    fireEvent.change(screen.getByLabelText("TOTP-Code"), {
      target: { value: "123456" },
    });
    screen.getByRole("button", { name: "Einloggen" }).click();

    expect(await screen.findByText("LEG-Verwaltung")).toBeTruthy();
  });

  it("fuehrt Admins nach Passwort-Login durch die TOTP-MFA-Einrichtung", async () => {
    const user = {
      id: "jwt-user-leg-admin",
      email: "leg-admin@example.test",
      display_name: "LEG Admin Demo",
      role: "leg_admin",
      mfa_satisfied: false,
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/login")) {
        return new Response(
          JSON.stringify({
            access_token: "jwt-leg-admin-pre-mfa",
            token_type: "bearer",
            expires_in_seconds: 28800,
            user,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/me")) {
        return new Response(JSON.stringify(user), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/auth/mfa/totp/enroll")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer jwt-leg-admin-pre-mfa",
        });

        return new Response(
          JSON.stringify({
            secret: "JBSWY3DPEHPK3PXP",
            otpauth_url:
              "otpauth://totp/SunTerra%20LEG:leg-admin%40example.test?secret=JBSWY3DPEHPK3PXP",
          }),
          {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.includes("/api/admin/")) {
        return new Response(JSON.stringify({ detail: "Admin MFA required" }), {
          status: 403,
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    fireEvent.change(screen.getByLabelText("E-Mail"), {
      target: { value: "leg-admin@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), {
      target: { value: "SunTerra123!" },
    });
    screen.getByRole("button", { name: "Einloggen" }).click();

    expect(
      await screen.findByRole("heading", { name: "TOTP-MFA einrichten" }),
    ).toBeTruthy();
    expect(screen.queryByText("Teilnehmer einladen")).toBeNull();

    screen.getByRole("button", { name: "TOTP-MFA einrichten" }).click();

    expect(await screen.findByText("JBSWY3DPEHPK3PXP")).toBeTruthy();
    expect(
      screen.getByText(
        "otpauth://totp/SunTerra%20LEG:leg-admin%40example.test?secret=JBSWY3DPEHPK3PXP",
      ),
    ).toBeTruthy();
  });

  it("meldet ab und entfernt gespeicherte Tokens", async () => {
    window.localStorage.setItem("sunterra.accessToken", "stored-jwt");
    window.localStorage.setItem("sunterra.devToken", "dev:platform_admin");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer stored-jwt",
        });

        return new Response(
          JSON.stringify({
            id: "platform-admin",
            email: "platform-admin@example.test",
            display_name: "Plattform Admin Demo",
            role: "platform_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/users")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer stored-jwt",
        });

        return new Response(JSON.stringify([]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/app");

    expect(
      await screen.findByRole("heading", { name: "Benutzerverwaltung" }),
    ).toBeTruthy();
    screen.getByRole("button", { name: "Abmelden" }).click();

    await waitFor(() => expect(window.location.pathname).toBe("/"));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "SunTerra LEG Portal" }),
      ).toBeTruthy(),
    );
    expect(window.localStorage.getItem("sunterra.accessToken")).toBeNull();
    expect(window.localStorage.getItem("sunterra.devToken")).toBeNull();
  });

  it("aktualisiert als Platform Admin Anzeigename und Rolle eines Benutzerkontos", async () => {
    let account = {
      id: "leg-admin-1",
      email: "leg-admin-1@example.test",
      display_name: "Leo Admin",
      role: "leg_admin",
      active: true,
      organization: null,
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-platform-admin",
            email: "platform-admin@example.test",
            display_name: "Plattform Admin Demo",
            role: "platform_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/users/leg-admin-1")) {
        expect(init?.method).toBe("PATCH");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:platform_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          display_name: "Lea Admin",
          role: "platform_admin",
        });

        account = {
          ...account,
          display_name: "Lea Admin",
          role: "platform_admin",
        };

        return new Response(JSON.stringify(account), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/admin/users")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:platform_admin",
        });

        return new Response(JSON.stringify([account]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Benutzerverwaltung" }).click();

    const row = await screen.findByLabelText("Konto leg-admin-1@example.test");
    fireEvent.change(within(row).getByLabelText("Anzeigename"), {
      target: { value: "Lea Admin" },
    });
    fireEvent.change(within(row).getByLabelText("Rolle"), {
      target: { value: "platform_admin" },
    });
    within(row).getByRole("button", { name: "Aenderungen speichern" }).click();

    expect(await within(row).findByText("Benutzer aktualisiert")).toBeTruthy();
    expect(within(row).getByDisplayValue("Lea Admin")).toBeTruthy();
    expect(within(row).getByText(/Benutzerverwaltung/)).toBeTruthy();
  });

  it("erstellt als LEG Admin eine Teilnehmer-Einladung", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-leg-admin",
            email: "leg-admin@example.test",
            display_name: "LEG Admin Demo",
            role: "leg_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/participant-invitations")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          email: "anna.keller@example.test",
          display_name: "Anna Keller",
        });

        return new Response(
          JSON.stringify({
            token: "invite-token-anna",
            email: "anna.keller@example.test",
            display_name: "Anna Keller",
            leg_id: "basadingen",
            status: "pending_email_verification",
          }),
          {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "LEG Admin" }).click();

    expect(await screen.findByText("LEG-Verwaltung")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("E-Mail"), {
      target: { value: "anna.keller@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Anzeigename"), {
      target: { value: "Anna Keller" },
    });
    screen.getByRole("button", { name: "Einladung erstellen" }).click();

    expect(await screen.findByText("Einladung erstellt")).toBeTruthy();
    expect(screen.getByText("Anna Keller")).toBeTruthy();
    expect(screen.getByText("invite-token-anna")).toBeTruthy();
  });

  it("zeigt LEG Admins offene Mutationen und erlaubt Genehmigung oder Ablehnung", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-leg-admin",
            email: "leg-admin@example.test",
            display_name: "LEG Admin Demo",
            role: "leg_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/mutation-requests?status=submitted")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
        });

        return new Response(
          JSON.stringify([
            {
              id: "mutation-request-approve",
              participant_id: "participant-anna",
              leg_id: "basadingen",
              mutation_type: "address",
              mode: "regular",
              status: "submitted",
              quarter: "2026-Q3",
              quarter_end: "2026-09-30",
              participant_deadline: "2026-06-30",
              effective_date: "2026-10-01",
              submitted_at: "2026-06-15T12:00:00+00:00",
              reviewed_at: null,
              review_reason: null,
              new_address: {
                street: "Hauptstrasse 7",
                postal_code: "8254",
                city: "Basadingen",
                country: "CH",
              },
              participant: {
                participant_id: "participant-anna",
                display_name: "Anna Keller",
                email: "anna.keller@example.test",
              },
              audit_events: [],
            },
            {
              id: "mutation-request-reject",
              participant_id: "participant-bernd",
              leg_id: "basadingen",
              mutation_type: "address",
              mode: "regular",
              status: "submitted",
              quarter: "2026-Q4",
              quarter_end: "2026-12-31",
              participant_deadline: "2026-09-30",
              effective_date: "2027-01-01",
              submitted_at: "2026-06-16T12:00:00+00:00",
              reviewed_at: null,
              review_reason: null,
              new_address: {
                street: "Dorfstrasse 2",
                postal_code: "8254",
                city: "Basadingen",
                country: "CH",
              },
              participant: {
                participant_id: "participant-bernd",
                display_name: "Bernd Berger",
                email: "bernd.berger@example.test",
              },
              audit_events: [],
            },
          ]),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (
        url.endsWith(
          "/api/admin/mutation-requests/mutation-request-approve/review-decision",
        )
      ) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          decision: "approved",
        });

        return new Response(
          JSON.stringify({
            id: "mutation-request-approve",
            participant_id: "participant-anna",
            leg_id: "basadingen",
            mutation_type: "address",
            mode: "regular",
            status: "approved",
            quarter: "2026-Q3",
            quarter_end: "2026-09-30",
            participant_deadline: "2026-06-30",
            effective_date: "2026-10-01",
            submitted_at: "2026-06-15T12:00:00+00:00",
            reviewed_at: "2026-06-17T12:00:00+00:00",
            review_reason: null,
            new_address: {
              street: "Hauptstrasse 7",
              postal_code: "8254",
              city: "Basadingen",
              country: "CH",
            },
            participant: {
              participant_id: "participant-anna",
              display_name: "Anna Keller",
              email: "anna.keller@example.test",
            },
            audit_events: [],
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (
        url.endsWith(
          "/api/admin/mutation-requests/mutation-request-reject/review-decision",
        )
      ) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          decision: "rejected",
          reason: "Adresse gehoert nicht zum LEG Perimeter.",
        });

        return new Response(
          JSON.stringify({
            id: "mutation-request-reject",
            participant_id: "participant-bernd",
            leg_id: "basadingen",
            mutation_type: "address",
            mode: "regular",
            status: "rejected",
            quarter: "2026-Q4",
            quarter_end: "2026-12-31",
            participant_deadline: "2026-09-30",
            effective_date: "2027-01-01",
            submitted_at: "2026-06-16T12:00:00+00:00",
            reviewed_at: "2026-06-17T12:05:00+00:00",
            review_reason: "Adresse gehoert nicht zum LEG Perimeter.",
            new_address: {
              street: "Dorfstrasse 2",
              postal_code: "8254",
              city: "Basadingen",
              country: "CH",
            },
            participant: {
              participant_id: "participant-bernd",
              display_name: "Bernd Berger",
              email: "bernd.berger@example.test",
            },
            audit_events: [],
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "LEG Admin" }).click();

    expect(await screen.findByText("Offene Mutationen")).toBeTruthy();
    const inbox = within(screen.getByLabelText("Offene Mutationen"));
    const approveRequest = within(inbox.getByText("Anna Keller").closest("div")!);
    const rejectRequest = within(inbox.getByText("Bernd Berger").closest("div")!);
    expect(approveRequest.getByText("Teilnehmerfrist: 2026-06-30")).toBeTruthy();
    expect(rejectRequest.getByText("Teilnehmerfrist: 2026-09-30")).toBeTruthy();

    approveRequest.getByRole("button", { name: "Genehmigen" }).click();
    fireEvent.change(rejectRequest.getByLabelText("Ablehnungsgrund"), {
      target: { value: "Adresse gehoert nicht zum LEG Perimeter." },
    });
    rejectRequest.getByRole("button", { name: "Ablehnen" }).click();

    expect(await screen.findByText("Status: approved")).toBeTruthy();
    expect(await screen.findByText("Status: rejected")).toBeTruthy();
    expect(
      screen.getByText("Adresse gehoert nicht zum LEG Perimeter."),
    ).toBeTruthy();
  });

  it("zeigt LEG Admins Sondermutationen mit Grund und Ereignisdatum im Review-Inbox", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-leg-admin",
            email: "leg-admin@example.test",
            display_name: "LEG Admin Demo",
            role: "leg_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/mutation-requests?status=submitted")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
        });

        return new Response(
          JSON.stringify([
            {
              id: "mutation-request-special-review",
              participant_id: "participant-anna",
              leg_id: "basadingen",
              mutation_type: "move_out",
              mode: "special",
              status: "submitted",
              quarter: null,
              quarter_end: null,
              participant_deadline: null,
              effective_date: "2026-07-12",
              submitted_at: "2026-06-22T12:00:00+00:00",
              reviewed_at: null,
              review_reason: null,
              new_address: null,
              mutation_details: {
                reason: "Auszug wegen Wohnungswechsel.",
                event_date: "2026-07-12",
              },
              participant: {
                participant_id: "participant-anna",
                display_name: "Anna Sonder",
                email: "anna.sonder@example.test",
              },
              audit_events: [],
            },
          ]),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (
        url.endsWith(
          "/api/admin/mutation-requests/mutation-request-special-review/review-decision",
        )
      ) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          decision: "approved",
        });

        return new Response(
          JSON.stringify({
            id: "mutation-request-special-review",
            participant_id: "participant-anna",
            leg_id: "basadingen",
            mutation_type: "move_out",
            mode: "special",
            status: "approved",
            quarter: null,
            quarter_end: null,
            participant_deadline: null,
            effective_date: "2026-07-12",
            submitted_at: "2026-06-22T12:00:00+00:00",
            reviewed_at: "2026-06-22T12:30:00+00:00",
            review_reason: null,
            new_address: null,
            mutation_details: {
              reason: "Auszug wegen Wohnungswechsel.",
              event_date: "2026-07-12",
            },
            participant: {
              participant_id: "participant-anna",
              display_name: "Anna Sonder",
              email: "anna.sonder@example.test",
            },
            audit_events: [],
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "LEG Admin" }).click();

    expect(await screen.findByText("Offene Mutationen")).toBeTruthy();
    const inbox = within(screen.getByLabelText("Offene Mutationen"));
    const specialRequest = within(inbox.getByText("Anna Sonder").closest("div")!);
    expect(specialRequest.getByText("Sondermutation")).toBeTruthy();
    expect(specialRequest.getByText("Auszug")).toBeTruthy();
    expect(specialRequest.getByText("Grund: Auszug wegen Wohnungswechsel.")).toBeTruthy();
    expect(specialRequest.getByText("Ereignisdatum: 2026-07-12")).toBeTruthy();
    expect(specialRequest.getByText("Kein regulaeres Quartal")).toBeTruthy();
    expect(specialRequest.queryByText(/Teilnehmerfrist:/)).toBeNull();

    specialRequest.getByRole("button", { name: "Genehmigen" }).click();

    expect(await specialRequest.findByText("Status: approved")).toBeTruthy();
  });

  it("laedt als LEG Admin kontrollierte Datei-Nachweise fuer Mutationen hoch", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-leg-admin",
            email: "leg-admin@example.test",
            display_name: "LEG Admin Demo",
            role: "leg_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/mutation-requests?status=submitted")) {
        return new Response(
          JSON.stringify([
            {
              id: "mutation-request-evidence",
              participant_id: "participant-anna",
              leg_id: "basadingen",
              mutation_type: "address",
              mode: "regular",
              status: "submitted",
              quarter: "2026-Q3",
              quarter_end: "2026-09-30",
              participant_deadline: "2026-06-30",
              effective_date: "2026-10-01",
              submitted_at: "2026-06-15T12:00:00+00:00",
              reviewed_at: null,
              review_reason: null,
              new_address: {
                street: "Hauptstrasse 7",
                postal_code: "8254",
                city: "Basadingen",
                country: "CH",
              },
              participant: {
                participant_id: "participant-anna",
                display_name: "Anna Keller",
                email: "anna.keller@example.test",
              },
              audit_events: [],
            },
          ]),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (
        url.endsWith(
          "/api/admin/mutation-requests/mutation-request-evidence/file-evidence",
        )
      ) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          document_type: "mutation_review_supporting_document",
          purpose: "mutation_review",
          version: "2026-06-22",
          filename: "address-proof.txt",
          content_type: "text/plain",
          content_base64: window.btoa("Address proof for review"),
        });

        return new Response(
          JSON.stringify({
            id: "file-evidence-ui",
            mutation_request_id: "mutation-request-evidence",
            participant_id: "participant-anna",
            document_type: "mutation_review_supporting_document",
            purpose: "mutation_review",
            version: "2026-06-22",
            filename: "address-proof.txt",
            content_type: "text/plain",
            sha256_hash: "hash-evidence-ui",
            access_protection: "mutation_review_owner_and_leg_admin",
            retention_status: "retained_for_mutation_review",
            created_at: "2026-06-22T12:00:00+00:00",
          }),
          {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "LEG Admin" }).click();

    expect(await screen.findByText("Offene Mutationen")).toBeTruthy();
    const mutation = within(screen.getByText("Anna Keller").closest("div")!);
    fireEvent.change(mutation.getByLabelText("Nachweisversion"), {
      target: { value: "2026-06-22" },
    });
    fireEvent.change(mutation.getByLabelText("Dateiname"), {
      target: { value: "address-proof.txt" },
    });
    fireEvent.change(mutation.getByLabelText("MIME-Typ"), {
      target: { value: "text/plain" },
    });
    fireEvent.change(mutation.getByLabelText("Dateiinhalt"), {
      target: { value: "Address proof for review" },
    });
    mutation.getByRole("button", { name: "Nachweis hochladen" }).click();

    expect(await mutation.findByText("address-proof.txt")).toBeTruthy();
    expect(mutation.getByText("Version 2026-06-22")).toBeTruthy();
    expect(mutation.getByText("Hash hash-evidence-ui")).toBeTruthy();
    expect(mutation.getByText("mutation_review_owner_and_leg_admin")).toBeTruthy();
    expect(mutation.getByText("retained_for_mutation_review")).toBeTruthy();
  });

  it("erstellt als LEG Admin ein Mutationspaket und zeigt Exportlinks", async () => {
    const packageResponse = {
      schema_version: "mutation-package.v1",
      package_id: "package-ui-1",
      leg_id: "basadingen",
      quarter: "2026-Q3",
      effective_date: "2026-10-01",
      records: [],
      hash: "hash-ui-package",
      generated_at: "2026-06-22T12:00:00+00:00",
      status_history: [
        {
          status: "created",
          actor_id: "dev-leg-admin",
          actor_role: "leg_admin",
          created_at: "2026-06-22T12:00:00+00:00",
        },
      ],
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-leg-admin",
            email: "leg-admin@example.test",
            display_name: "LEG Admin Demo",
            role: "leg_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/mutation-requests?status=submitted")) {
        return new Response(JSON.stringify([]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/admin/mutation-packages")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          quarter: "2026-Q3",
        });

        return new Response(JSON.stringify(packageResponse), {
          status: 201,
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/admin/mutation-packages/package-ui-1/json")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
        });

        return new Response(JSON.stringify(packageResponse), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    Object.defineProperty(URL, "createObjectURL", {
      writable: true,
      value: vi.fn(() => "blob:package-ui-json"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      writable: true,
      value: vi.fn(),
    });
    const anchorClick = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    renderAt("/login");
    screen.getByRole("button", { name: "LEG Admin" }).click();

    expect(await screen.findByText("Mutationspakete")).toBeTruthy();
    const packages = within(screen.getByLabelText("Mutationspakete"));
    fireEvent.change(packages.getByLabelText("Paketquartal"), {
      target: { value: "2026-Q3" },
    });
    packages.getByRole("button", { name: "Paket erstellen" }).click();

    expect(await packages.findByText("Paket package-ui-1")).toBeTruthy();
    const createdPackage = within(
      screen.getByLabelText("Erstelltes Mutationspaket"),
    );
    expect(createdPackage.getByText("2026-Q3")).toBeTruthy();
    expect(createdPackage.getByText("Wirksam ab: 2026-10-01")).toBeTruthy();
    expect(createdPackage.getByText("Hash hash-ui-package")).toBeTruthy();
    createdPackage.getByRole("button", { name: "JSON" }).click();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          input.toString().endsWith(
            "/api/admin/mutation-packages/package-ui-1/json",
          ),
        ),
      ).toBe(true),
    );
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(anchorClick).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:package-ui-json");
    expect(createdPackage.getByRole("button", { name: "CSV" })).toBeTruthy();
    expect(createdPackage.getByRole("button", { name: "PDF" })).toBeTruthy();
  });

  it("zeigt Gemeinde/EW Mutationspakete und aktualisiert Paketstatus", async () => {
    const packageSummary = {
      package_id: "package-partner-1",
      leg_id: "basadingen",
      quarter: "2026-Q3",
      effective_date: "2026-10-01",
      generated_at: "2026-06-22T12:00:00+00:00",
      record_count: 1,
      current_status: "created",
      status_updated_at: "2026-06-22T12:00:00+00:00",
    };
    const packageDetail = (status: "created" | "question") => ({
      ...packageSummary,
      current_status: status,
      status_updated_at:
        status === "question"
          ? "2026-06-23T08:30:00+00:00"
          : packageSummary.status_updated_at,
      records: [
        {
          mutation_request_id: "mutation-partner-1",
          participant_id: "participant-anna",
          mutation_type: "address",
          mode: "regular",
          effective_date: "2026-10-01",
          new_address: {
            street: "Detailweg 8",
            postal_code: "8254",
            city: "Basadingen",
            country: "CH",
          },
        },
      ],
      status_history:
        status === "question"
          ? [
              {
                status: "created",
                actor_role: "leg_admin",
                created_at: "2026-06-22T12:00:00+00:00",
                reference: null,
                reason: null,
              },
              {
                status: "question",
                actor_role: "partner_admin",
                created_at: "2026-06-23T08:30:00+00:00",
                reference: "EW-RF-404",
                reason: null,
              },
            ]
          : [
              {
                status: "created",
                actor_role: "leg_admin",
                created_at: "2026-06-22T12:00:00+00:00",
                reference: null,
                reason: null,
              },
            ],
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-partner-admin",
            email: "partner-admin@example.test",
            display_name: "Partner Admin Demo",
            role: "partner_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/partner/mutation-packages")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:partner_admin",
        });

        return new Response(JSON.stringify([packageSummary]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/partner/mutation-packages/package-partner-1/status")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:partner_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          status: "question",
          reference: "EW-RF-404",
        });

        return new Response(JSON.stringify(packageDetail("question")), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/partner/mutation-packages/package-partner-1")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:partner_admin",
        });

        return new Response(JSON.stringify(packageDetail("created")), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Gemeinde/EW" }).click();

    expect(await screen.findByText("Mutationspaket-Eingang")).toBeTruthy();
    const inbox = within(screen.getByLabelText("Mutationspaket-Eingang"));
    expect(inbox.getByText("Paket package-partner-1")).toBeTruthy();
    expect(inbox.getByText("Status: created")).toBeTruthy();

    inbox.getByRole("button", { name: "Details anzeigen" }).click();

    expect(await inbox.findByText("Detailweg 8, 8254 Basadingen, CH")).toBeTruthy();
    fireEvent.change(inbox.getByLabelText("Paketstatus"), {
      target: { value: "question" },
    });
    fireEvent.change(inbox.getByLabelText("Referenz oder Grund"), {
      target: { value: "EW-RF-404" },
    });
    inbox.getByRole("button", { name: "Status aktualisieren" }).click();

    expect((await inbox.findAllByText("Status: question")).length).toBeGreaterThan(0);
    expect(inbox.getByText("EW-RF-404")).toBeTruthy();
  });

  it("zeigt Gemeinde/EW aktive Partner-Aufgaben aus Paket-Follow-ups", async () => {
    const partnerTasks = [
      {
        task_id: "package-task-1:question",
        package_id: "package-task-1",
        leg_id: "basadingen",
        quarter: "2026-Q4",
        effective_date: "2027-01-01",
        status: "question",
        reference: "EW-RF-505",
        reason: null,
        created_at: "2026-09-15T08:30:00+00:00",
        record_count: 1,
      },
    ];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-partner-admin",
            email: "partner-admin@example.test",
            display_name: "Partner Admin Demo",
            role: "partner_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/partner/mutation-packages")) {
        return new Response(JSON.stringify([]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/partner/tasks")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:partner_admin",
        });

        return new Response(JSON.stringify(partnerTasks), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Gemeinde/EW" }).click();

    expect(await screen.findByText("Partner-Aufgaben")).toBeTruthy();
    const tasks = within(screen.getByLabelText("Partner-Aufgaben"));
    expect(tasks.getByText("Paket package-task-1")).toBeTruthy();
    expect(tasks.getByText("Rückfrage")).toBeTruthy();
    expect(tasks.getByText("EW-RF-505")).toBeTruthy();
    expect(tasks.getByText("1 Mutation")).toBeTruthy();
    expect(tasks.queryByText("dev-leg-admin")).toBeNull();
  });

  it("zeigt Gemeinde/EW das Mitgliederregister ohne private Felder", async () => {
    const memberRegister = {
      leg_id: "basadingen",
      leg_name: "SunTerra LEG Basadingen",
      members: [
        {
          participant_id: "participant-rita",
          display_name: "Rita Register",
          membership_status: "active",
          reporting_address: {
            street: "Registerweg 4",
            postal_code: "8254",
            city: "Basadingen",
            country: "CH",
          },
          latest_package_status: {
            package_id: "package-register-1",
            quarter: "2031-Q2",
            effective_date: "2031-07-01",
            status: "processed",
          },
          email: "rita.private@example.test",
          phone_number: "+41 52 555 77 66",
          preferred_contact_channel: "phone",
          consent_evidence: [{ document_hash: "secret-consent-hash" }],
          audit_events: [{ actor_id: "dev-partner-admin" }],
          review_reason: "secret review reason",
          file_evidence: [
            {
              filename: "secret-proof.txt",
              content_base64: "c2VjcmV0LWZpbGUtZXZpZGVuY2U=",
            },
          ],
          hash: "secret-package-hash",
          artifact_urls: {
            json: "https://private-artifact.example.test/package.json",
          },
          actor_id: "dev-leg-admin",
        },
      ],
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-partner-admin",
            email: "partner-admin@example.test",
            display_name: "Partner Admin Demo",
            role: "partner_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/partner/mutation-packages")) {
        return new Response(JSON.stringify([]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/partner/member-register")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:partner_admin",
        });

        return new Response(JSON.stringify(memberRegister), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Gemeinde/EW" }).click();

    expect(await screen.findByText("Mitgliederregister")).toBeTruthy();
    const register = within(screen.getByLabelText("Mitgliederregister"));
    expect(register.getByText("SunTerra LEG Basadingen")).toBeTruthy();
    expect(register.getByText("Rita Register")).toBeTruthy();
    expect(register.getByText("Registerweg 4, 8254 Basadingen, CH")).toBeTruthy();
    expect(register.getByText("Status: active")).toBeTruthy();
    expect(register.getByText("Paket package-register-1")).toBeTruthy();
    expect(register.getByText("2031-Q2")).toBeTruthy();
    expect(register.getByText("Paketstatus: processed")).toBeTruthy();

    const renderedText = document.body.textContent ?? "";
    for (const prohibitedText of [
      "rita.private@example.test",
      "+41 52 555 77 66",
      "phone",
      "secret-consent-hash",
      "dev-partner-admin",
      "secret review reason",
      "secret-proof.txt",
      "c2VjcmV0LWZpbGUtZXZpZGVuY2U=",
      "secret-package-hash",
      "https://private-artifact.example.test/package.json",
      "dev-leg-admin",
    ]) {
      expect(renderedText).not.toContain(prohibitedText);
    }
  });

  it("veroeffentlicht als LEG Admin eine Dokumentversion", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-leg-admin",
            email: "leg-admin@example.test",
            display_name: "LEG Admin Demo",
            role: "leg_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/document-versions")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          document_key: "portal_terms",
          title: "Portal Nutzungsbedingungen",
          version: "2026-06-22",
          content: "Teilnahmebedingungen fuer das Portal.",
          context: "participant_onboarding",
        });

        return new Response(
          JSON.stringify({
            id: "document-version-1",
            document_key: "portal_terms",
            title: "Portal Nutzungsbedingungen",
            version: "2026-06-22",
            document_hash: "hash-portal-terms",
            context: "participant_onboarding",
            published_at: "2026-06-22T12:00:00+00:00",
          }),
          {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "LEG Admin" }).click();

    expect(await screen.findByText("LEG-Verwaltung")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Titel"), {
      target: { value: "Portal Nutzungsbedingungen" },
    });
    fireEvent.change(screen.getByLabelText("Version"), {
      target: { value: "2026-06-22" },
    });
    fireEvent.change(screen.getByLabelText("Inhalt"), {
      target: { value: "Teilnahmebedingungen fuer das Portal." },
    });
    screen
      .getByRole("button", { name: "Dokumentversion veroeffentlichen" })
      .click();

    expect(await screen.findByText("Dokumentversion veroeffentlicht")).toBeTruthy();
    expect(screen.getByText("2026-06-22")).toBeTruthy();
    expect(screen.getByText("hash-portal-terms")).toBeTruthy();
  });

  it("veroeffentlicht als LEG Admin den LEG-Vertrag als Pflichtdokument", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-leg-admin",
            email: "leg-admin@example.test",
            display_name: "LEG Admin Demo",
            role: "leg_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/document-versions")) {
        expect(JSON.parse(init?.body as string)).toEqual({
          document_key: "leg_contract",
          title: "LEG-Vertrag",
          version: "2026-06-24",
          content: "Vertrag fuer die verbindliche Teilnahme.",
          context: "participant_onboarding",
        });

        return new Response(
          JSON.stringify({
            id: "document-version-contract",
            document_key: "leg_contract",
            title: "LEG-Vertrag",
            version: "2026-06-24",
            document_hash: "hash-leg-contract",
            context: "participant_onboarding",
            published_at: "2026-06-24T12:00:00+00:00",
          }),
          {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "LEG Admin" }).click();

    expect(await screen.findByText("LEG-Verwaltung")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Dokumenttyp"), {
      target: { value: "leg_contract" },
    });
    fireEvent.change(screen.getByLabelText("Titel"), {
      target: { value: "LEG-Vertrag" },
    });
    fireEvent.change(screen.getByLabelText("Version"), {
      target: { value: "2026-06-24" },
    });
    fireEvent.change(screen.getByLabelText("Inhalt"), {
      target: { value: "Vertrag fuer die verbindliche Teilnahme." },
    });
    screen
      .getByRole("button", { name: "Dokumentversion veroeffentlichen" })
      .click();

    expect(await screen.findByText("Dokumentversion veroeffentlicht")).toBeTruthy();
    expect(screen.getByText("hash-leg-contract")).toBeTruthy();
  });

  it("warnt LEG Admins vor Datenzugriff und erstellt Gemeinde/EW Zugang", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "dev-leg-admin",
            email: "leg-admin@example.test",
            display_name: "LEG Admin Demo",
            role: "leg_admin",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/admin/partner-admin-users")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:leg_admin",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          email: "ew-admin@example.test",
          display_name: "EW Admin",
          organization: "Gemeinde/EW Basadingen",
          password: "Start123!",
        });

        return new Response(
          JSON.stringify({
            id: "partner-admin-created",
            email: "ew-admin@example.test",
            display_name: "EW Admin",
            role: "partner_admin",
            active: true,
            organization: "Gemeinde/EW Basadingen",
          }),
          {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "LEG Admin" }).click();

    expect(await screen.findByText("LEG-Verwaltung")).toBeTruthy();
    expect(
      screen.getByText(
        "Warnung: Dieser Zugang erhaelt Zugriff auf Gemeinde/EW-Aufgaben, Mutationspakete und rollenbezogene Mitgliederdaten der LEG.",
      ),
    ).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Gemeinde/EW E-Mail"), {
      target: { value: "ew-admin@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Gemeinde/EW Anzeigename"), {
      target: { value: "EW Admin" },
    });
    fireEvent.change(screen.getByLabelText("Organisation / Verantwortung"), {
      target: { value: "Gemeinde/EW Basadingen" },
    });
    fireEvent.change(screen.getByLabelText("Startpasswort"), {
      target: { value: "Start123!" },
    });
    screen.getByRole("button", { name: "Gemeinde/EW Zugang erstellen" }).click();

    expect(await screen.findByText("Gemeinde/EW Zugang erstellt")).toBeTruthy();
    expect(screen.getByText("ew-admin@example.test")).toBeTruthy();
  });

  it("zeigt Teilnehmern die aktuelle Dokumentversion vor Zustimmung", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "participant-anna",
            email: "anna.keller@example.test",
            display_name: "Anna Keller",
            role: "participant",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/documents/current?document_key=portal_terms")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:participant",
        });

        return new Response(
          JSON.stringify({
            id: "document-version-current",
            document_key: "portal_terms",
            title: "Portal Nutzungsbedingungen",
            version: "2026-06-22",
            content: "Bitte lies diese Bedingungen vor der Zustimmung.",
            document_hash: "hash-current-document",
            context: "participant_onboarding",
            published_at: "2026-06-22T12:00:00+00:00",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Teilnehmer" }).click();

    expect(await screen.findByText("Portal Nutzungsbedingungen")).toBeTruthy();
    expect(screen.getByText("Version 2026-06-22")).toBeTruthy();
    expect(
      screen.getByText("Bitte lies diese Bedingungen vor der Zustimmung."),
    ).toBeTruthy();
    expect(screen.getByText("hash-current-document")).toBeTruthy();
    expect(
      screen.getByLabelText("Ich stimme dieser Dokumentversion zu"),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Zustimmen" })).toBeTruthy();
  });

  it("zeigt Teilnehmern alle aktuellen Pflichtdokumente vor Zustimmung", async () => {
    const currentDocuments = {
      privacy_notice: {
        id: "document-version-privacy",
        document_key: "privacy_notice",
        title: "Datenschutzhinweis",
        version: "2026-06-24",
        content: "Datenschutzhinweis fuer den SunTerra LEG Pilot.",
        document_hash: "hash-privacy-notice",
        context: "participant_onboarding",
        published_at: "2026-06-24T12:00:00+00:00",
      },
      portal_terms: {
        id: "document-version-terms",
        document_key: "portal_terms",
        title: "Portal-Nutzungsbedingungen",
        version: "2026-06-24",
        content: "Nutzungsbedingungen fuer den digitalen Kanal.",
        document_hash: "hash-portal-terms",
        context: "participant_onboarding",
        published_at: "2026-06-24T12:01:00+00:00",
      },
      leg_contract: {
        id: "document-version-contract",
        document_key: "leg_contract",
        title: "LEG-Vertrag",
        version: "2026-06-24",
        content: "Vertrag fuer die verbindliche Teilnahme.",
        document_hash: "hash-leg-contract",
        context: "participant_onboarding",
        published_at: "2026-06-24T12:02:00+00:00",
      },
    };
    const requestedDocumentKeys: string[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "participant-anna",
            email: "anna.keller@example.test",
            display_name: "Anna Keller",
            role: "participant",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.includes("/api/documents/current")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:participant",
        });
        const documentKey = new URL(url, "http://localhost").searchParams.get(
          "document_key",
        ) as keyof typeof currentDocuments;
        requestedDocumentKeys.push(documentKey);

        return new Response(JSON.stringify(currentDocuments[documentKey]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Teilnehmer" }).click();

    expect(await screen.findByText("Datenschutzhinweis")).toBeTruthy();
    expect(screen.getByText("Portal-Nutzungsbedingungen")).toBeTruthy();
    expect(screen.getByText("LEG-Vertrag")).toBeTruthy();
    expect(
      screen.getAllByLabelText("Ich stimme dieser Dokumentversion zu"),
    ).toHaveLength(3);
    expect(requestedDocumentKeys).toEqual([
      "privacy_notice",
      "portal_terms",
      "leg_contract",
    ]);
  });

  it("laedt bestehende Zustimmungshistorie beim Teilnehmer-Login", async () => {
    const documents = {
      privacy_notice: {
        id: "document-version-privacy",
        document_key: "privacy_notice",
        title: "Datenschutzhinweis",
        version: "2026-06-24",
        content: "Datenschutzhinweis fuer den SunTerra LEG Pilot.",
        document_hash: "hash-privacy-notice",
        context: "participant_onboarding",
        published_at: "2026-06-24T12:00:00+00:00",
      },
      portal_terms: {
        id: "document-version-terms",
        document_key: "portal_terms",
        title: "Portal-Nutzungsbedingungen",
        version: "2026-06-24",
        content: "Nutzungsbedingungen fuer den digitalen Kanal.",
        document_hash: "hash-portal-terms",
        context: "participant_onboarding",
        published_at: "2026-06-24T12:01:00+00:00",
      },
      leg_contract: {
        id: "document-version-contract",
        document_key: "leg_contract",
        title: "LEG-Vertrag",
        version: "2026-06-24",
        content: "Vertrag fuer die verbindliche Teilnahme.",
        document_hash: "hash-leg-contract",
        context: "participant_onboarding",
        published_at: "2026-06-24T12:02:00+00:00",
      },
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "participant-anna",
            email: "anna.keller@example.test",
            display_name: "Anna Keller",
            role: "participant",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.includes("/api/documents/current")) {
        const documentKey = new URL(url, "http://localhost").searchParams.get(
          "document_key",
        ) as keyof typeof documents;

        return new Response(JSON.stringify(documents[documentKey]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/participants/me/consent-evidence")) {
        return new Response(
          JSON.stringify([
            {
              participant_id: "participant-anna",
              document_version_id: "document-version-privacy",
              document_key: "privacy_notice",
              version: "2026-06-24",
              document_hash: "hash-privacy-notice",
              context: "participant_onboarding",
              accepted_at: "2026-06-24T12:05:00+00:00",
            },
          ]),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Teilnehmer" }).click();

    expect(await screen.findByText("Datenschutzhinweis")).toBeTruthy();
    expect(await screen.findByText("Einwilligung gespeichert")).toBeTruthy();
    const history = within(screen.getByLabelText("Einwilligungshistorie"));
    expect(history.getByText("hash-privacy-notice")).toBeTruthy();
  });

  it("speichert Teilnehmer-Zustimmung und zeigt Version und Hash in der Historie", async () => {
    const evidence = {
      participant_id: "participant-anna",
      document_version_id: "document-version-current",
      document_key: "portal_terms",
      version: "2026-06-22",
      document_hash: "hash-current-document",
      context: "participant_onboarding",
      accepted_at: "2026-06-22T12:05:00+00:00",
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "participant-anna",
            email: "anna.keller@example.test",
            display_name: "Anna Keller",
            role: "participant",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/documents/current?document_key=portal_terms")) {
        return new Response(
          JSON.stringify({
            id: "document-version-current",
            document_key: "portal_terms",
            title: "Portal Nutzungsbedingungen",
            version: "2026-06-22",
            content: "Bitte lies diese Bedingungen vor der Zustimmung.",
            document_hash: "hash-current-document",
            context: "participant_onboarding",
            published_at: "2026-06-22T12:00:00+00:00",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/participants/me/consent-evidence")) {
        if (init?.method === "POST") {
          expect(init.headers).toEqual({
            Authorization: "Bearer dev:participant",
            "Content-Type": "application/json",
          });
          expect(JSON.parse(init.body as string)).toEqual({
            document_version_id: "document-version-current",
            context: "participant_onboarding",
            accepted: true,
          });

          return new Response(JSON.stringify(evidence), {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          });
        }

        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:participant",
        });

        return new Response(JSON.stringify([evidence]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Teilnehmer" }).click();

    expect(await screen.findByText("Portal Nutzungsbedingungen")).toBeTruthy();
    fireEvent.click(
      screen.getByLabelText("Ich stimme dieser Dokumentversion zu"),
    );
    screen.getByRole("button", { name: "Zustimmen" }).click();

    expect(await screen.findByText("Einwilligung gespeichert")).toBeTruthy();
    const history = within(screen.getByLabelText("Einwilligungshistorie"));
    expect(history.getByText("Version 2026-06-22")).toBeTruthy();
    expect(history.getByText("hash-current-document")).toBeTruthy();
  });

  it("akzeptiert und verifiziert eine Teilnehmer-Einladung per Token", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/invitations/invite-token-anna/accept")) {
        expect(init?.method).toBe("POST");

        return new Response(
          JSON.stringify({
            access_token: "participant-access-anna",
            token_type: "bearer",
            participant_id: "participant-anna",
            email_verification_required: true,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (
        url.endsWith("/api/auth/email-verifications/invite-token-anna/verify")
      ) {
        expect(init?.method).toBe("POST");

        return new Response(
          JSON.stringify({
            participant_id: "participant-anna",
            email_verified: true,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");

    fireEvent.change(screen.getByLabelText("Einladungstoken"), {
      target: { value: "invite-token-anna" },
    });
    screen
      .getByRole("button", { name: "Einladung annehmen und verifizieren" })
      .click();

    expect(await screen.findByText("E-Mail verifiziert")).toBeTruthy();
    expect(screen.getByText("participant-anna")).toBeTruthy();
  });

  it("zeigt nach dem Onboarding den eigenen Teilnehmer-Kontext mit Abrechnungshinweis", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/invitations/invite-token-anna/accept")) {
        return new Response(
          JSON.stringify({
            access_token: "participant-access-anna",
            token_type: "bearer",
            participant_id: "participant-anna",
            email_verification_required: true,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (
        url.endsWith("/api/auth/email-verifications/invite-token-anna/verify")
      ) {
        return new Response(
          JSON.stringify({
            participant_id: "participant-anna",
            email_verified: true,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/participants/me/membership")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer participant-access-anna",
        });

        return new Response(
          JSON.stringify({
            participant_id: "participant-anna",
            display_name: "Anna Keller",
            email: "anna.keller@example.test",
            leg_id: "basadingen",
            leg_name: "SunTerra LEG Basadingen",
            membership_status: "active",
            billing_notice: "Abrechnung und Inkasso bleiben bei Gemeinde/EW.",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");

    fireEvent.change(screen.getByLabelText("Einladungstoken"), {
      target: { value: "invite-token-anna" },
    });
    screen
      .getByRole("button", { name: "Einladung annehmen und verifizieren" })
      .click();

    expect(await screen.findByText("Mein Portal")).toBeTruthy();

    const workspace = within(
      screen.getByLabelText("Geschuetzter Arbeitsbereich"),
    );
    expect(workspace.getByText("Anna Keller")).toBeTruthy();
    expect(workspace.getByText("anna.keller@example.test")).toBeTruthy();
    expect(workspace.getByText("SunTerra LEG Basadingen")).toBeTruthy();
    expect(
      workspace.getByText("Abrechnung und Inkasso bleiben bei Gemeinde/EW."),
    ).toBeTruthy();
  });

  it("zeigt eingeladenen Teilnehmern nach Verifizierung die aktuelle Dokumentversion vor Zustimmung", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/invitations/invite-token-anna/accept")) {
        return new Response(
          JSON.stringify({
            access_token: "participant-access-anna",
            token_type: "bearer",
            participant_id: "participant-anna",
            email_verification_required: true,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (
        url.endsWith("/api/auth/email-verifications/invite-token-anna/verify")
      ) {
        return new Response(
          JSON.stringify({
            participant_id: "participant-anna",
            email_verified: true,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/participants/me/membership")) {
        return new Response(
          JSON.stringify({
            participant_id: "participant-anna",
            display_name: "Anna Keller",
            email: "anna.keller@example.test",
            leg_id: "basadingen",
            leg_name: "SunTerra LEG Basadingen",
            membership_status: "active",
            billing_notice: "Abrechnung und Inkasso bleiben bei Gemeinde/EW.",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/documents/current?document_key=portal_terms")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer participant-access-anna",
        });

        return new Response(
          JSON.stringify({
            id: "document-version-onboarding",
            document_key: "portal_terms",
            title: "Portal Nutzungsbedingungen",
            version: "2026-06-22",
            content: "Bitte lies diese Bedingungen vor der Zustimmung.",
            document_hash: "hash-onboarding-document",
            context: "participant_onboarding",
            published_at: "2026-06-22T12:00:00+00:00",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");

    fireEvent.change(screen.getByLabelText("Einladungstoken"), {
      target: { value: "invite-token-anna" },
    });
    screen
      .getByRole("button", { name: "Einladung annehmen und verifizieren" })
      .click();

    expect(await screen.findByText("Portal Nutzungsbedingungen")).toBeTruthy();
    expect(screen.getByText("Version 2026-06-22")).toBeTruthy();
    expect(screen.getByText("hash-onboarding-document")).toBeTruthy();
    expect(
      screen.getByLabelText("Ich stimme dieser Dokumentversion zu"),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Zustimmen" })).toBeTruthy();
  });

  it("speichert Zustimmung eingeladener Teilnehmer mit issued Access Token und zeigt die Historie", async () => {
    const evidence = {
      participant_id: "participant-anna",
      document_version_id: "document-version-onboarding",
      document_key: "portal_terms",
      version: "2026-06-22",
      document_hash: "hash-onboarding-document",
      context: "participant_onboarding",
      accepted_at: "2026-06-22T12:05:00+00:00",
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/invitations/invite-token-anna/accept")) {
        return new Response(
          JSON.stringify({
            access_token: "participant-access-anna",
            token_type: "bearer",
            participant_id: "participant-anna",
            email_verification_required: true,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (
        url.endsWith("/api/auth/email-verifications/invite-token-anna/verify")
      ) {
        return new Response(
          JSON.stringify({
            participant_id: "participant-anna",
            email_verified: true,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/participants/me/membership")) {
        return new Response(
          JSON.stringify({
            participant_id: "participant-anna",
            display_name: "Anna Keller",
            email: "anna.keller@example.test",
            leg_id: "basadingen",
            leg_name: "SunTerra LEG Basadingen",
            membership_status: "active",
            billing_notice: "Abrechnung und Inkasso bleiben bei Gemeinde/EW.",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/documents/current?document_key=portal_terms")) {
        return new Response(
          JSON.stringify({
            id: "document-version-onboarding",
            document_key: "portal_terms",
            title: "Portal Nutzungsbedingungen",
            version: "2026-06-22",
            content: "Bitte lies diese Bedingungen vor der Zustimmung.",
            document_hash: "hash-onboarding-document",
            context: "participant_onboarding",
            published_at: "2026-06-22T12:00:00+00:00",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/participants/me/consent-evidence")) {
        if (init?.method === "POST") {
          expect(init.headers).toEqual({
            Authorization: "Bearer participant-access-anna",
            "Content-Type": "application/json",
          });
          expect(JSON.parse(init.body as string)).toEqual({
            document_version_id: "document-version-onboarding",
            context: "participant_onboarding",
            accepted: true,
          });

          return new Response(JSON.stringify(evidence), {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          });
        }

        expect(init?.headers).toEqual({
          Authorization: "Bearer participant-access-anna",
        });

        return new Response(JSON.stringify([evidence]), {
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");

    fireEvent.change(screen.getByLabelText("Einladungstoken"), {
      target: { value: "invite-token-anna" },
    });
    screen
      .getByRole("button", { name: "Einladung annehmen und verifizieren" })
      .click();

    expect(await screen.findByText("Portal Nutzungsbedingungen")).toBeTruthy();
    fireEvent.click(
      screen.getByLabelText("Ich stimme dieser Dokumentversion zu"),
    );
    screen.getByRole("button", { name: "Zustimmen" }).click();

    expect(await screen.findByText("Einwilligung gespeichert")).toBeTruthy();
    const history = within(screen.getByLabelText("Einwilligungshistorie"));
    expect(history.getByText("Version 2026-06-22")).toBeTruthy();
    expect(history.getByText("hash-onboarding-document")).toBeTruthy();
  });

  it("zeigt Kontaktkanaele im Teilnehmerbereich und speichert direkte Updates", async () => {
    let saveAttempts = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "participant-anna",
            email: "anna.keller@example.test",
            display_name: "Anna Keller",
            role: "participant",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/documents/current?document_key=portal_terms")) {
        return new Response(JSON.stringify({ detail: "Document version not found" }), {
          status: 404,
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/participants/me/contact-channels")) {
        if (init?.method === "PATCH") {
          saveAttempts += 1;
          expect(init.headers).toEqual({
            Authorization: "Bearer dev:participant",
            "Content-Type": "application/json",
          });
          expect(JSON.parse(init.body as string)).toEqual({
            phone_number: "+41 52 555 99 88",
            preferred_contact_channel: "phone",
          });

          if (saveAttempts === 1) {
            return new Response(
              JSON.stringify({ detail: "Kontaktkanaele konnten nicht gespeichert werden" }),
              {
                status: 400,
                headers: {
                  "Content-Type": "application/json",
                },
              },
            );
          }

          return new Response(
            JSON.stringify({
              participant_id: "participant-anna",
              email: "anna.keller@example.test",
              phone_number: "+41 52 555 99 88",
              preferred_contact_channel: "phone",
              audit_events: [
                {
                  id: "contact-audit-1",
                  action: "participant.contact_channels_updated",
                  actor_role: "participant",
                  created_at: "2026-06-22T12:00:00+00:00",
                  from_status: null,
                  to_status: null,
                  reason: null,
                },
              ],
            }),
            {
              headers: {
                "Content-Type": "application/json",
              },
            },
          );
        }

        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:participant",
        });

        return new Response(
          JSON.stringify({
            participant_id: "participant-anna",
            email: "anna.keller@example.test",
            phone_number: "+41 52 555 01 23",
            preferred_contact_channel: "email",
            audit_events: [],
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Teilnehmer" }).click();

    expect(await screen.findByText("Kontaktkanäle")).toBeTruthy();
    const contactChannels = within(screen.getByLabelText("Kontaktkanäle"));
    expect(
      contactChannels.getByText("Aktuelle Telefonnummer: +41 52 555 01 23"),
    ).toBeTruthy();
    expect(contactChannels.getByText("Aktueller Kanal: E-Mail")).toBeTruthy();

    fireEvent.change(contactChannels.getByLabelText("Telefonnummer"), {
      target: { value: "+41 52 555 99 88" },
    });
    fireEvent.change(contactChannels.getByLabelText("Bevorzugter Kanal"), {
      target: { value: "phone" },
    });
    contactChannels
      .getByRole("button", { name: "Kontaktkanäle speichern" })
      .click();

    expect(
      await contactChannels.findByText(
        "Kontaktkanaele konnten nicht gespeichert werden",
      ),
    ).toBeTruthy();

    contactChannels
      .getByRole("button", { name: "Kontaktkanäle speichern" })
      .click();

    expect(await contactChannels.findByText("Kontaktkanäle gespeichert")).toBeTruthy();
    expect(
      contactChannels.getByText("Aktuelle Telefonnummer: +41 52 555 99 88"),
    ).toBeTruthy();
    expect(contactChannels.getByText("Aktueller Kanal: Telefon")).toBeTruthy();
  });

  it("reicht als Teilnehmer eine regulaere Adressmutation ein und zeigt Status, Frist und Wirksamkeitsdatum", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "participant-anna",
            email: "anna.keller@example.test",
            display_name: "Anna Keller",
            role: "participant",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/documents/current?document_key=portal_terms")) {
        return new Response(JSON.stringify({ detail: "Document version not found" }), {
          status: 404,
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/participants/me/mutation-requests")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:participant",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          mutation_type: "address",
          mode: "regular",
          requested_quarter: "2026-Q3",
          new_address: {
            street: "Hauptstrasse 7",
            postal_code: "8254",
            city: "Basadingen",
            country: "CH",
          },
        });

        return new Response(
          JSON.stringify({
            id: "mutation-request-1",
            participant_id: "participant-anna",
            leg_id: "basadingen",
            mutation_type: "address",
            mode: "regular",
            status: "submitted",
            quarter: "2026-Q3",
            quarter_end: "2026-09-30",
            participant_deadline: "2026-06-30",
            effective_date: "2026-10-01",
            submitted_at: "2026-06-15T12:00:00+00:00",
            new_address: {
              street: "Hauptstrasse 7",
              postal_code: "8254",
              city: "Basadingen",
              country: "CH",
            },
          }),
          {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Teilnehmer" }).click();

    expect(await screen.findByText("Mein Portal")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Quartal"), {
      target: { value: "2026-Q3" },
    });
    fireEvent.change(screen.getByLabelText("Strasse"), {
      target: { value: "Hauptstrasse 7" },
    });
    fireEvent.change(screen.getByLabelText("PLZ"), {
      target: { value: "8254" },
    });
    fireEvent.change(screen.getByLabelText("Ort"), {
      target: { value: "Basadingen" },
    });
    fireEvent.change(screen.getByLabelText("Land"), {
      target: { value: "CH" },
    });
    screen.getByRole("button", { name: "Adressmutation einreichen" }).click();

    expect(await screen.findByText("Meine Mutationen")).toBeTruthy();
    const mutations = within(screen.getByLabelText("Meine Mutationen"));
    expect(mutations.getByText("2026-Q3")).toBeTruthy();
    expect(mutations.getByText("Status: submitted")).toBeTruthy();
    expect(mutations.getByText("Teilnehmerfrist: 2026-06-30")).toBeTruthy();
    expect(mutations.getByText("Wirksam ab: 2026-10-01")).toBeTruthy();
  });

  it("reicht als Teilnehmer eine Sondermutation ein und zeigt Grund und Ereignisdatum", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: "participant-anna",
            email: "anna.keller@example.test",
            display_name: "Anna Keller",
            role: "participant",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/documents/current?document_key=portal_terms")) {
        return new Response(JSON.stringify({ detail: "Document version not found" }), {
          status: 404,
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      if (url.endsWith("/api/participants/me/mutation-requests")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:participant",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          mutation_type: "move_out",
          mode: "special",
          event_date: "2026-07-12",
          reason: "Auszug wegen Wohnungswechsel.",
        });

        return new Response(
          JSON.stringify({
            id: "mutation-request-special",
            participant_id: "participant-anna",
            leg_id: "basadingen",
            mutation_type: "move_out",
            mode: "special",
            status: "submitted",
            quarter: null,
            quarter_end: null,
            participant_deadline: null,
            effective_date: "2026-07-12",
            submitted_at: "2026-06-22T12:00:00+00:00",
            reviewed_at: null,
            review_reason: null,
            new_address: null,
            mutation_details: {
              reason: "Auszug wegen Wohnungswechsel.",
              event_date: "2026-07-12",
            },
            audit_events: [],
          }),
          {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    screen.getByRole("button", { name: "Teilnehmer" }).click();

    expect(await screen.findByText("Mein Portal")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Mutationsmodus"), {
      target: { value: "special" },
    });
    fireEvent.change(screen.getByLabelText("Sondermutationstyp"), {
      target: { value: "move_out" },
    });
    fireEvent.change(screen.getByLabelText("Ereignisdatum"), {
      target: { value: "2026-07-12" },
    });
    fireEvent.change(screen.getByLabelText("Begruendung"), {
      target: { value: "Auszug wegen Wohnungswechsel." },
    });
    screen.getByRole("button", { name: "Sondermutation einreichen" }).click();

    expect(await screen.findByText("Meine Mutationen")).toBeTruthy();
    const mutations = within(screen.getByLabelText("Meine Mutationen"));
    expect(mutations.getByText("Sondermutation")).toBeTruthy();
    expect(mutations.getByText("Auszug")).toBeTruthy();
    expect(mutations.getByText("Grund: Auszug wegen Wohnungswechsel.")).toBeTruthy();
    expect(mutations.getByText("Ereignisdatum: 2026-07-12")).toBeTruthy();
    expect(mutations.getByText("Kein regulaeres Quartal")).toBeTruthy();
    expect(mutations.getByText("Status: submitted")).toBeTruthy();
    expect(mutations.getByText("Wirksam ab: 2026-07-12")).toBeTruthy();
  });

  it("zeigt beim Self-Service den Identitätscheckpoint und schaltet Mitgliedschaft erst nach Verifizierung frei", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/self-service-onboarding-requests")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          email: "selina.frei@example.test",
        });

        return new Response(
          JSON.stringify({
            access_token: "self-service-access",
            token_type: "bearer",
            participant_id: "participant-selina",
            participant_status: "pending_email_verification",
            identity_checkpoint: {
              required_level: "email_verified",
              current_level: "unverified",
              satisfied: false,
            },
            dev_email_verification_token: "dev-self-service-token",
          }),
          {
            status: 201,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (
        url.endsWith(
          "/api/auth/email-verifications/dev-self-service-token/verify",
        )
      ) {
        return new Response(
          JSON.stringify({
            participant_id: "participant-selina",
            email_verified: true,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (
        url.endsWith(
          "/api/participants/me/identity-checkpoint?action=membership_activation",
        )
      ) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer self-service-access",
        });

        return new Response(
          JSON.stringify({
            action: "membership_activation",
            required_level: "account_setup",
            current_level: "email_verified",
            satisfied: false,
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/auth/participant-account-setup")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer self-service-access",
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          display_name: "Selina Frei",
          password: "SicheresPasswort123!",
        });

        return new Response(
          JSON.stringify({
            access_token: "participant-setup-access",
            token_type: "bearer",
            expires_in_seconds: 28800,
            user: {
              id: "participant-selina",
              email: "selina.frei@example.test",
              display_name: "Selina Frei",
              role: "participant",
            },
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/me")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer participant-setup-access",
        });

        return new Response(
          JSON.stringify({
            id: "participant-selina",
            email: "selina.frei@example.test",
            display_name: "Selina Frei",
            role: "participant",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      if (url.endsWith("/api/participants/me/membership")) {
        expect(init?.headers).toEqual({
          Authorization: "Bearer participant-setup-access",
        });

        return new Response(
          JSON.stringify({
            participant_id: "participant-selina",
            display_name: "Selina Frei",
            email: "selina.frei@example.test",
            leg_id: "basadingen",
            leg_name: "SunTerra LEG Basadingen",
            membership_status: "active",
            billing_notice: "Abrechnung und Inkasso bleiben bei Gemeinde/EW.",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/registrieren");

    fireEvent.change(screen.getByLabelText("Self-Service E-Mail"), {
      target: { value: "selina.frei@example.test" },
    });
    screen.getByRole("button", { name: "Self-Service starten" }).click();

    expect(await screen.findByText("Identitaetspruefung")).toBeTruthy();
    expect(screen.getByText("Erforderlich: email_verified")).toBeTruthy();
    expect(screen.getByText("Aktuell: unverified")).toBeTruthy();
    expect(screen.getByText("Checkpoint offen")).toBeTruthy();
    expect(screen.getByText("dev-self-service-token")).toBeTruthy();
    expect(screen.queryByText("Mein Portal")).toBeNull();

    screen.getByRole("button", { name: "Dev E-Mail verifizieren" }).click();

    expect(
      await screen.findByRole("heading", { name: "Konto einrichten" }),
    ).toBeTruthy();
    expect(screen.getByText("Erforderlich: account_setup")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Anzeigename"), {
      target: { value: "Selina Frei" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), {
      target: { value: "SicheresPasswort123!" },
    });
    screen.getByRole("button", { name: "Konto einrichten" }).click();

    expect(await screen.findByText("Mein Portal")).toBeTruthy();
    expect(screen.getByText("Selina Frei")).toBeTruthy();
    expect(screen.getByText("selina.frei@example.test")).toBeTruthy();
  });

  it("sendet Netzwerktopologie-Daten aus dem Self-Service-Formular mit", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/self-service-onboarding-requests")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          email: "topologie@example.test",
          display_name: "Topologie Test",
          metering_point_id: "CH-1008901234500000000000000000999",
          street: "Solarweg 7",
          postal_code: "8254",
          city: "Basadingen",
        });

        return new Response(
          JSON.stringify({
            id: "interest-record-topology",
            email: "topologie@example.test",
            display_name: "Topologie Test",
            status: "interest_recorded",
            created_at: "2026-06-24T20:00:00+00:00",
          }),
          {
            status: 202,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/registrieren");

    fireEvent.change(screen.getByLabelText("Self-Service E-Mail"), {
      target: { value: "topologie@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Self-Service Anzeigename"), {
      target: { value: "Topologie Test" },
    });
    fireEvent.change(screen.getByLabelText("Messpunkt-ID"), {
      target: { value: "CH-1008901234500000000000000000999" },
    });
    fireEvent.change(screen.getByLabelText("Strasse"), {
      target: { value: "Solarweg 7" },
    });
    fireEvent.change(screen.getByLabelText("PLZ"), {
      target: { value: "8254" },
    });
    fireEvent.change(screen.getByLabelText("Ort"), {
      target: { value: "Basadingen" },
    });
    screen.getByRole("button", { name: "Self-Service starten" }).click();

    expect(
      await screen.findByRole("heading", {
        name: "Interessensmeldung gespeichert",
      }),
    ).toBeTruthy();
  });

  it("zeigt im Pilotmodus eine Interessensmeldung ohne Account-Schritte", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();

      if (url.endsWith("/api/auth/self-service-onboarding-requests")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          "Content-Type": "application/json",
        });
        expect(JSON.parse(init?.body as string)).toEqual({
          email: "interesse@example.test",
          display_name: "Pilot Interesse",
        });

        return new Response(
          JSON.stringify({
            id: "interest-record-1",
            email: "interesse@example.test",
            display_name: "Pilot Interesse",
            status: "interest_recorded",
            created_at: "2026-06-24T20:00:00+00:00",
          }),
          {
            status: 202,
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

      return new Response(
        JSON.stringify({
          status: "ok",
          service: "sunterra-leg-portal",
          version: "0.1.0",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/registrieren");

    fireEvent.change(screen.getByLabelText("Self-Service E-Mail"), {
      target: { value: "interesse@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Self-Service Anzeigename"), {
      target: { value: "Pilot Interesse" },
    });
    screen.getByRole("button", { name: "Self-Service starten" }).click();

    expect(
      await screen.findByRole("heading", {
        name: "Interessensmeldung gespeichert",
      }),
    ).toBeTruthy();
    expect(screen.getByText("interesse@example.test")).toBeTruthy();
    expect(screen.getByText("Pilot Interesse")).toBeTruthy();
    expect(screen.queryByText("Identitätsprüfung")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Konto einrichten" })).toBeNull();
  });

  it("zeigt einen verständlichen Status, wenn das Backend nicht erreichbar ist", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("Network unavailable");
      }),
    );

    renderAt("/login");

    expect(await screen.findByText("Backend nicht erreichbar")).toBeTruthy();
    expect(
      screen.getByText("Die Portaloberflaeche ist geladen."),
    ).toBeTruthy();
  });
});

it("reicht als Teilnehmer eine regulaere Rollenmutation ein und zeigt Typ und Details", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input.toString();

    if (url.endsWith("/api/me")) {
      return new Response(
        JSON.stringify({
          id: "participant-anna",
          email: "anna.keller@example.test",
          display_name: "Anna Keller",
          role: "participant",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    }

    if (url.endsWith("/api/documents/current?document_key=portal_terms")) {
      return new Response(JSON.stringify({ detail: "Document version not found" }), {
        status: 404,
        headers: {
          "Content-Type": "application/json",
        },
      });
    }

    if (url.endsWith("/api/participants/me/mutation-requests")) {
      expect(init?.method).toBe("POST");
      expect(init?.headers).toEqual({
        Authorization: "Bearer dev:participant",
        "Content-Type": "application/json",
      });
      expect(JSON.parse(init?.body as string)).toEqual({
        mutation_type: "role",
        mode: "regular",
        requested_quarter: "2026-Q3",
        requested_role: "owner",
      });

      return new Response(
        JSON.stringify({
          id: "mutation-request-role",
          participant_id: "participant-anna",
          leg_id: "basadingen",
          mutation_type: "role",
          mode: "regular",
          status: "submitted",
          quarter: "2026-Q3",
          quarter_end: "2026-09-30",
          participant_deadline: "2026-06-30",
          effective_date: "2026-10-01",
          submitted_at: "2026-06-15T12:00:00+00:00",
          new_address: null,
          mutation_details: {
            requested_role: "owner",
          },
        }),
        {
          status: 201,
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    }

    return new Response(
      JSON.stringify({
        status: "ok",
        service: "sunterra-leg-portal",
        version: "0.1.0",
      }),
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );
  });
  vi.stubGlobal("fetch", fetchMock);

  renderAt("/login");
  screen.getByRole("button", { name: "Teilnehmer" }).click();

  expect(await screen.findByText("Mein Portal")).toBeTruthy();

  fireEvent.change(screen.getByLabelText("Mutationstyp"), {
    target: { value: "role" },
  });
  fireEvent.change(screen.getByLabelText("Quartal"), {
    target: { value: "2026-Q3" },
  });
  fireEvent.change(screen.getByLabelText("Gewuenschte Rolle"), {
    target: { value: "owner" },
  });
  screen.getByRole("button", { name: "Mutation einreichen" }).click();

  expect(await screen.findByText("Meine Mutationen")).toBeTruthy();
  const mutations = within(screen.getByLabelText("Meine Mutationen"));
  expect(mutations.getByText("Rollenmutation")).toBeTruthy();
  expect(mutations.getByText("Rolle: Eigentuemer")).toBeTruthy();
  expect(mutations.getByText("Wirksam ab: 2026-10-01")).toBeTruthy();
});
