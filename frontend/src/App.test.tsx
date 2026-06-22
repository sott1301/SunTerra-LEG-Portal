import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("Portal shell", () => {
  afterEach(() => {
    window.localStorage.clear();
    vi.unstubAllGlobals();
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

    render(<App />);

    expect(
      screen.getByRole("heading", { name: "SunTerra LEG Portal" }),
    ).toBeTruthy();
    expect(screen.getByText("Mitglieder- und Mutationsportal")).toBeTruthy();
    expect(await screen.findByText("Backend verbunden")).toBeTruthy();
    expect(screen.getByText("sunterra-leg-portal 0.1.0")).toBeTruthy();
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

    render(<App />);

    expect(await screen.findByText("Backend verbunden")).toBeTruthy();
    expect(screen.getByText("Anmeldung erforderlich")).toBeTruthy();
    expect(
      screen.getByText("Wähle für die lokale Entwicklung eine Demo-Rolle."),
    ).toBeTruthy();
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

    render(<App />);
    screen.getByRole("button", { name: "Teilnehmer" }).click();

    expect(await screen.findByText("Mein Mitgliederbereich")).toBeTruthy();
    expect(screen.getByText("Teilnehmer Demo")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/me",
      expect.objectContaining({
        headers: { Authorization: "Bearer dev:participant" },
      }),
    );
  });

  it.each([
    ["Teilnehmer", "participant", "Mein Mitgliederbereich", "Teilnehmer Demo"],
    ["LEG Admin", "leg_admin", "LEG Verwaltung", "LEG Admin Demo"],
    [
      "Gemeinde/EW",
      "partner_admin",
      "Gemeinde/EW Arbeitsplatz",
      "Partner Admin Demo",
    ],
    [
      "Plattform",
      "platform_admin",
      "Plattform Administration",
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

      render(<App />);
      screen.getByRole("button", { name: buttonLabel }).click();

      expect(await screen.findByText(workspaceTitle)).toBeTruthy();
      expect(screen.getByText(displayName)).toBeTruthy();
    },
  );

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

    render(<App />);
    screen.getByRole("button", { name: "LEG Admin" }).click();

    expect(await screen.findByText("LEG Verwaltung")).toBeTruthy();

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

  it("veroeffentlicht als Plattform-Admin eine Dokumentversion", async () => {
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

      if (url.endsWith("/api/admin/document-versions")) {
        expect(init?.method).toBe("POST");
        expect(init?.headers).toEqual({
          Authorization: "Bearer dev:platform_admin",
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

    render(<App />);
    screen.getByRole("button", { name: "Plattform" }).click();

    expect(await screen.findByText("Plattform Administration")).toBeTruthy();

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
      .getByRole("button", { name: "Dokumentversion veröffentlichen" })
      .click();

    expect(await screen.findByText("Dokumentversion veröffentlicht")).toBeTruthy();
    expect(screen.getByText("2026-06-22")).toBeTruthy();
    expect(screen.getByText("hash-portal-terms")).toBeTruthy();
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

    render(<App />);
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

    render(<App />);
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

    render(<App />);

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

    render(<App />);

    fireEvent.change(screen.getByLabelText("Einladungstoken"), {
      target: { value: "invite-token-anna" },
    });
    screen
      .getByRole("button", { name: "Einladung annehmen und verifizieren" })
      .click();

    expect(await screen.findByText("Mein Mitgliederbereich")).toBeTruthy();

    const workspace = within(
      screen.getByLabelText("Geschützter Arbeitsbereich"),
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

    render(<App />);

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

    render(<App />);

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

  it("zeigt einen verständlichen Status, wenn das Backend nicht erreichbar ist", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("Network unavailable");
      }),
    );

    render(<App />);

    expect(await screen.findByText("Backend nicht erreichbar")).toBeTruthy();
    expect(
      screen.getByText("Die Portaloberfläche ist geladen."),
    ).toBeTruthy();
  });
});
