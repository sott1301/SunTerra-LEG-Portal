import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("Portal shell", () => {
  afterEach(() => {
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
