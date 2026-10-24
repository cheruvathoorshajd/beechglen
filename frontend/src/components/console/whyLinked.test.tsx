import { fireEvent, render, screen, within } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../../api/client";
import type { LinkDecision } from "../../api/types";
import explain from "../../mocks/explain.json";
import { renderAt } from "../../test/render";
import { markOnboarded, setSession } from "../../auth/session";
import App from "../../App";
import { WhyLinkedModal, explainOutcome } from "./WhyLinkedModal";

vi.mock("./IncidentMap", () => ({ IncidentMap: () => <div data-testid="map-stub" /> }));

const base = explain as LinkDecision;
const decision = (overrides: Partial<LinkDecision>): LinkDecision => ({ ...base, ...overrides });
const unscored = { geo: null, time: null, type: null, entity: null };

describe("Why linked?", () => {
  it("opens from the incident panel and shows every component with its share", async () => {
    setSession({ kind: "guest" });
    markOnboarded({ kind: "guest" });
    renderAt("/operator", <App />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Why linked?" }))[0]);

    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByTestId("why-outcome");
    const table = within(dialog).getByRole("table");
    for (const label of ["Place", "Time", "Type", "Details"]) {
      expect(within(table).getByText(label)).toBeTruthy();
    }
    expect(within(table).getByText("p_same")).toBeTruthy();
    expect(within(dialog).getByText(/Decided by/)).toBeTruthy();
  });

  it("explains a call that started an incident with nothing to compare", async () => {
    vi.spyOn(api, "explain").mockResolvedValue(decision({ band: "new", p_same: 0, components: unscored, gates: [] }));
    render(<WhyLinkedModal callId="c-0001" onClose={() => {}} />);
    expect((await screen.findByTestId("why-outcome")).textContent).toMatch(/No open incident was within range/);
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("shows the type gate cap for the fire call", async () => {
    vi.spyOn(api, "explain").mockResolvedValue(base);
    render(<WhyLinkedModal callId={base.call_id} onClose={() => {}} />);
    expect(await screen.findByText("Different emergency types are never merged")).toBeTruthy();
    expect(screen.getByText(/capped at 0\.49/)).toBeTruthy();
  });

  it("shows an error instead of an empty dialog when the request fails", async () => {
    vi.spyOn(api, "explain").mockRejectedValue(new Error("Server unreachable"));
    render(<WhyLinkedModal callId="c-0009" onClose={() => {}} />);
    expect((await screen.findByRole("alert")).textContent).toContain("Server unreachable");
  });

  it("words every band", () => {
    const scored = { geo: 1, time: 0.95, type: 1, entity: 1 };
    expect(explainOutcome(decision({ band: "auto", p_same: 0.99, components: scored, gates: [] }), null)).toMatch(/on its own/);
    expect(explainOutcome(decision({ band: "suggest", p_same: 0.7, components: scored, gates: [] }), null)).toMatch(/waits for an operator/);
    expect(
      explainOutcome(decision({ band: "suggest", p_same: 0.96, components: scored, gates: ["low_location_confidence"] }), null),
    ).toMatch(/location is unresolved/);
    expect(explainOutcome(decision({ band: "confirmed", p_same: 0.7, components: scored, gates: [] }), null)).toMatch(/operator confirmed/);
    expect(explainOutcome(decision({ band: "new", p_same: 0.3, components: scored, gates: [] }), null)).toMatch(/below the 0\.50/);
    expect(explainOutcome(decision({ band: "new", p_same: 0.8, components: scored, gates: ["operator_split"] }), null)).toMatch(/split/);
  });
});
