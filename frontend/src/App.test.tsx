import { render, screen } from "@testing-library/react";
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
