import { render, screen, within } from "@testing-library/react";
import { vi } from "vitest";
import type { QueueItem } from "../../api/types";
import queue from "../../mocks/queue.json";
import { renderAt } from "../../test/render";
import { useConsole } from "../../store";
import App from "../../App";
import { PriorityPill } from "./chips";
import { QueueCard } from "./QueueCard";

vi.mock("./IncidentMap", () => ({ IncidentMap: () => <div data-testid="map-stub" /> }));

const base = (queue as QueueItem[])[0];

beforeEach(() => {
  useConsole.setState({ queue: [], incidents: [], incident: null, selectedIncidentId: null, selectedCallId: null, loaded: false });
});

describe("priority pill thresholds", () => {
  it.each([
    [100, "high"],
    [80, "high"],
    [79, "mid"],
    [50, "mid"],
    [49, "low"],
    [0, "low"],
  ])("priority %i is %s and shows its number", (priority, tone) => {
    const { container } = render(<PriorityPill priority={priority} />);
    const pill = container.querySelector("[data-tone]")!;
    expect(pill.getAttribute("data-tone")).toBe(tone);
    expect(pill.textContent).toContain(String(priority));
  });
});

describe("Critical badge", () => {
  it("shows the word Critical and the stripe at severity 0.9+", () => {
    render(<QueueCard item={{ ...base, severity: 1 }} origin={base.received_at} selected={false} onSelect={() => {}} />);
    const card = screen.getByRole("button");
    expect(within(card).getByText("● Critical")).toBeTruthy();
    expect(card.getAttribute("data-critical")).toBe("true");
  });

  it("is absent below 0.9", () => {
    render(<QueueCard item={{ ...base, severity: 0.8 }} origin={base.received_at} selected={false} onSelect={() => {}} />);
    expect(screen.queryByText("● Critical")).toBeNull();
  });
});

describe("console pages render from the mocks", () => {
  it("operator shows the queue, the incident and the dispatch package", async () => {
    renderAt("/operator", <App />);
    expect(await screen.findByRole("heading", { name: /Queue/ })).toBeTruthy();
    expect(await screen.findByText("8 calls")).toBeTruthy();
    expect(await screen.findByRole("heading", { name: /Dispatch package/ })).toBeTruthy();
    expect(screen.getByTestId("map-stub")).toBeTruthy();
    expect((await screen.findAllByText("● Critical")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/New info/).length).toBeGreaterThan(0);
  });

  it("officer shows the briefing and the leads board", async () => {
    renderAt("/officer", <App />);
    expect(await screen.findByRole("heading", { name: "Briefing" })).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Leads" })).toBeTruthy();
    expect(screen.getByText("Known")).toBeTruthy();
  });

  it("sim shows scenarios, controls and metrics", async () => {
    renderAt("/sim", <App />);
    expect(await screen.findByRole("heading", { name: "Replay a scenario." })).toBeTruthy();
    expect(screen.getByRole("radio", { name: /Mass Ave robbery/ }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByRole("button", { name: /Start/ })).toBeTruthy();
    expect(await screen.findByText("Collapse rate")).toBeTruthy();
  });
});
