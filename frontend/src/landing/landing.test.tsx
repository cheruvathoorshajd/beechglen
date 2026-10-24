import { screen, within } from "@testing-library/react";
import { vi } from "vitest";
import { renderAt } from "../test/render";
import { setSession } from "../auth/session";
import App from "../App";

vi.mock("../components/console/IncidentMap", () => ({ IncidentMap: () => <div data-testid="map-stub" /> }));

describe("landing", () => {
  it("shows every section from V2_SCREENS.md", () => {
    renderAt("/", <App />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Every call heard. New facts first.");
    for (const name of [
      "Big incidents arrive as many small, separate calls.",
      "From many calls to one incident.",
      "Built to sort the calls, and to show its work.",
      "Local problems, handled on purpose.",
      "What this prototype can't do yet.",
      "How would you like to start?",
    ]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
    const nav = screen.getByRole("navigation", { name: "Sections" });
    expect(within(nav).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([
      "#problem",
      "#how",
      "#novelties",
      "#massachusetts",
      "#limits",
    ]);
  });

  it("lists the seven README Massachusetts rows in a real table", () => {
    renderAt("/", <App />);
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(8);
    expect(within(table).getByRole("columnheader", { name: "How Nexus911 handles it" })).toBeTruthy();
  });

  it("states it is a prototype with synthetic data", () => {
    renderAt("/", <App />);
    expect(screen.getAllByText(/Prototype/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Synthetic data only/)).toBeTruthy();
  });

  it("CTAs go to sign-in without a session", () => {
    renderAt("/", <App />);
    expect(screen.getByRole("link", { name: "Get started" }).getAttribute("href")).toBe("/signin");
    expect(screen.getByRole("link", { name: /Run the demo/ }).getAttribute("href")).toBe("/signin");
    expect(screen.getByRole("link", { name: "Sign in" }).getAttribute("href")).toBe("/signin");
  });

  it("CTAs read Open the console with a session", () => {
    setSession({ kind: "local", name: "Dennis" });
    renderAt("/", <App />);
    expect(screen.getByRole("link", { name: "Open the console" }).getAttribute("href")).toBe("/operator");
    expect(screen.getByRole("link", { name: /Run the demo/ }).getAttribute("href")).toBe("/welcome");
    expect(screen.queryByRole("link", { name: "Sign in" })).toBeNull();
  });
});
