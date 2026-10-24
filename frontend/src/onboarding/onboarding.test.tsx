import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../api/client";
import { renderAt } from "../test/render";
import { STEP_KEY, isOnboarded, setSession } from "../auth/session";
import App from "../App";

vi.mock("../components/console/IncidentMap", () => ({ IncidentMap: () => <div data-testid="map-stub" /> }));

const dennis = { kind: "local", name: "Dennis" } as const;

function start() {
  setSession(dennis);
  renderAt("/welcome", <App />);
}

const heading = () => screen.getByRole("heading", { level: 1 });
const continueButton = () => screen.getByRole("button", { name: /^Continue/ });

describe("onboarding", () => {
  it("greets by name and moves focus to each step's heading", async () => {
    start();
    expect(screen.getByRole("dialog", { name: "Welcome to Nexus911" })).toBeTruthy();
    expect(screen.getByText(/Welcome, Dennis\./)).toBeTruthy();
    expect(document.activeElement).toBe(heading());
    expect(heading().textContent).toBe("Many calls. One incident.");

    fireEvent.click(continueButton());
    expect(heading().textContent).toBe("Every fact shows its evidence.");
    expect(document.activeElement).toBe(heading());
    expect(screen.getByText("83% · 7 sources")).toBeTruthy();
    expect(window.sessionStorage.getItem(STEP_KEY)).toBe("read");

    fireEvent.click(continueButton());
    expect(heading().textContent).toBe("How would you like to start?");
    expect(document.activeElement).toBe(heading());
    expect(await screen.findByText("Server reachable")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(heading().textContent).toBe("Every fact shows its evidence.");
    expect(document.activeElement).toBe(heading());
  });

  it("Escape skips the intro and opens the console", async () => {
    start();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(isOnboarded(dennis)).toBe(true);
    expect(window.sessionStorage.getItem(STEP_KEY)).toBeNull();
    expect(await screen.findByRole("heading", { name: /Queue/ })).toBeTruthy();
  });

  it("a refresh mid-wizard returns to the same step", () => {
    window.sessionStorage.setItem(STEP_KEY, "read");
    start();
    expect(heading().textContent).toBe("Every fact shows its evidence.");
  });

  it("server down: notice, demo disabled, console selected, Try again", async () => {
    const metrics = vi.spyOn(api, "metrics").mockRejectedValue(new TypeError("Failed to fetch"));
    window.sessionStorage.setItem(STEP_KEY, "start");
    start();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Can't reach the Nexus911 server");
    expect(screen.getByRole("radio", { name: /Run the Mass Ave robbery demo/ }).getAttribute("aria-disabled")).toBe("true");
    expect(screen.getByRole("radio", { name: /Open the operator console/ }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByRole("button", { name: /Open the console/ })).toBeTruthy();

    metrics.mockRestore();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Server reachable")).toBeTruthy();
  });

  it("arrow keys move between the start choices", async () => {
    window.sessionStorage.setItem(STEP_KEY, "start");
    start();
    await screen.findByText("Server reachable");
    const group = screen.getByRole("radiogroup", { name: "How to start" });
    fireEvent.keyDown(group, { key: "ArrowDown" });
    expect(screen.getByRole("radio", { name: /Open the operator console/ }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByRole("button", { name: /Open the console/ })).toBeTruthy();
  });

  it("running the demo resets, starts the robbery at the chosen speed and finishes", async () => {
    const reset = vi.spyOn(api, "reset");
    const startSim = vi.spyOn(api, "startSim");
    window.sessionStorage.setItem(STEP_KEY, "start");
    start();
    await screen.findByText("Server reachable");
    fireEvent.click(screen.getByRole("radio", { name: "20×" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Run the demo/ }));
    });
    await waitFor(() => expect(isOnboarded(dennis)).toBe(true));
    expect(reset).toHaveBeenCalled();
    expect(startSim).toHaveBeenCalledWith({ scenario_id: "mass_ave_robbery", speed: 20 });
  });
});
