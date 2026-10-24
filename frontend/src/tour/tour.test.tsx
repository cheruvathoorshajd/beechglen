import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../api/client";
import type { SimStatus } from "../api/types";
import App from "../App";
import { markOnboarded, setSession } from "../auth/session";
import { realDuration, simPhase } from "../pages/Sim";
import { useConsole } from "../store";
import { renderAt } from "../test/render";
import { FeatureTour, isTourSeen, openTour } from "./FeatureTour";
import { TOURS } from "./tours";

vi.mock("../components/console/IncidentMap", () => ({ IncidentMap: () => <div data-testid="map-stub" /> }));

const status = (over: Partial<SimStatus>): SimStatus => ({
  scenario_id: "mass_ave_robbery",
  running: false,
  speed: 10,
  t_offset_s: 0,
  sim_time: null,
  calls_sent: 0,
  calls_total: 12,
  ...over,
});

beforeEach(() => {
  useConsole.setState({ queue: [], incidents: [], incident: null, selectedIncidentId: null, selectedCallId: null, loaded: false, simStatus: null });
  setSession({ kind: "guest" });
  markOnboarded({ kind: "guest" });
});

const tourTitle = () => screen.getByRole("heading", { level: 2, name: (_, el) => el.id === "tour-title" });

describe("feature tours", () => {
  it("every step of every tour has a title and an explanation", () => {
    for (const tour of Object.values(TOURS)) {
      expect(tour.steps.length).toBeGreaterThan(3);
      for (const step of tour.steps) {
        expect(step.target).toMatch(/^[a-z-]+$/);
        expect(step.title.length).toBeGreaterThan(3);
        expect(step.body.length).toBeGreaterThan(40);
      }
    }
  });

  it("opens on the first visit, and Skip remembers it", async () => {
    vi.useFakeTimers();
    try {
      const { unmount } = render(<FeatureTour id="officer" auto />);
      act(() => {
        vi.advanceTimersByTime(700);
      });
      expect(screen.getByRole("dialog")).toBeTruthy();
      expect(tourTitle().textContent).toBe(TOURS.officer.steps[0].title);
      fireEvent.click(screen.getByRole("button", { name: "Skip tour" }));
      expect(screen.queryByRole("dialog")).toBeNull();
      expect(isTourSeen("officer")).toBe(true);
      unmount();

      render(<FeatureTour id="officer" auto />);
      act(() => {
        vi.advanceTimersByTime(700);
      });
      expect(screen.queryByRole("dialog")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("Next, Back, arrow keys and Done walk the steps; Escape skips", () => {
    render(<FeatureTour id="sim" auto={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Open the Simulation guide" }));
    const steps = TOURS.sim.steps;
    expect(tourTitle().textContent).toBe(steps[0].title);
    expect(document.activeElement).toBe(tourTitle());
    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(tourTitle().textContent).toBe(steps[1].title);
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(tourTitle().textContent).toBe(steps[0].title);
    fireEvent.keyDown(tourTitle(), { key: "ArrowRight" });
    expect(tourTitle().textContent).toBe(steps[1].title);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(isTourSeen("sim")).toBe(true);
  });

  it("the last step says Done and closes", () => {
    render(<FeatureTour id="officer" auto={false} />);
    act(() => openTour("officer", TOURS.officer.steps[TOURS.officer.steps.length - 1].target));
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("a step whose feature isn't on screen yet still explains it", () => {
    render(<FeatureTour id="operator" auto={false} />);
    act(() => openTour("operator", "call-actions"));
    expect(tourTitle().textContent).toBe("Confirm and Split");
    expect(screen.getByText(/sit on each call row/)).toBeTruthy();
  });

  it("each Sim feature has a ? that opens the guide at that feature", async () => {
    renderAt("/sim", <App />);
    await screen.findByRole("heading", { name: "Replay a scenario." });
    for (const [label, title] of [
      ["About speed", "Speed"],
      ["About mass-event mode", "Mass-event mode"],
      ["About replay progress", "Replay progress"],
      ["About the replay controls", "Start, Stop and Reset"],
    ]) {
      fireEvent.click(screen.getByRole("button", { name: label }));
      expect(tourTitle().textContent).toBe(title);
      fireEvent.click(screen.getByRole("button", { name: "Skip tour" }));
    }
  });

  it("the Operator and Officer pages have a guide", async () => {
    renderAt("/operator", <App />);
    fireEvent.click(await screen.findByRole("button", { name: "Open the Operator console guide" }));
    expect(tourTitle().textContent).toBe(TOURS.operator.steps[0].title);
  });
});

describe("simulation page", () => {
  it("Start clears the console first, then starts the chosen scenario and speed", async () => {
    const reset = vi.spyOn(api, "reset");
    const startSim = vi.spyOn(api, "startSim");
    renderAt("/sim", <App />);
    await screen.findByRole("heading", { name: "Replay a scenario." });
    fireEvent.click(screen.getByRole("radio", { name: /Pike crash/ }));
    fireEvent.click(screen.getByRole("radio", { name: "20×" }));
    reset.mockClear();
    startSim.mockClear();
    fireEvent.click(screen.getByRole("button", { name: /^Start/ }));
    await waitFor(() => expect(startSim).toHaveBeenCalledWith({ scenario_id: "pike_crash", speed: 20 }));
    expect(reset).toHaveBeenCalled();
    expect(reset.mock.invocationCallOrder[0]).toBeLessThan(startSim.mock.invocationCallOrder[0]);
  });

  it("shows how long the scenario takes at the chosen speed", async () => {
    renderAt("/sim", <App />);
    await screen.findByRole("heading", { name: "Replay a scenario." });
    expect(screen.getByText(/12 calls over 12:00 min of call time · about 1:12 min at 10×/)).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: "1×" }));
    expect(screen.getByText(/1× is real time/)).toBeTruthy();
  });

  it("shows running, stopped and finished replays in words with a progress bar", async () => {
    renderAt("/sim", <App />);
    await screen.findByRole("heading", { name: "Replay a scenario." });
    act(() => useConsole.setState({ simStatus: status({ running: true, calls_sent: 3, t_offset_s: 70 }) }));
    expect(screen.getByText(/3 of 12 calls in\. Waiting for the next call/)).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Calls replayed" }).getAttribute("aria-valuenow")).toBe("3");

    act(() => useConsole.setState({ simStatus: status({ calls_sent: 4 }) }));
    expect(screen.getByText(/Stopped after 4 of 12 calls/)).toBeTruthy();

    act(() => useConsole.setState({ simStatus: status({ calls_sent: 12 }) }));
    expect(screen.getByText(/Finished: all 12 calls replayed/)).toBeTruthy();
  });

  it("phase and duration helpers", () => {
    expect(simPhase(null)).toBe("idle");
    expect(simPhase(status({ running: true }))).toBe("running");
    expect(simPhase(status({ calls_sent: 5 }))).toBe("stopped");
    expect(simPhase(status({ calls_sent: 12 }))).toBe("finished");
    expect(realDuration(45)).toBe("45 s");
    expect(realDuration(72)).toBe("1:12 min");
  });
});
