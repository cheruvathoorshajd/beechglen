import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { RuntimeSettings, SimStatus } from "../api/types";
import { Button, ChoiceCard, Segmented, SpecLabel, nextIndex } from "../ui";
import { useConsole } from "../store";
import { MetricsPanel } from "../components/console/shell";
import { tPlusSeconds } from "../lib/format";
import { FeatureTour, TourHint } from "../tour/FeatureTour";

/** `lastCallS` is the offset of the scenario's last call (data/scenarios/*.json). */
export const SCENARIOS = [
  {
    id: "mass_ave_robbery",
    title: "Mass Ave robbery",
    body: "Eleven calls about one robbery near Boylston St, then a fire with people trapped a block away.",
    calls: 12,
    lastCallS: 720,
  },
  {
    id: "pike_crash",
    title: "Pike crash",
    body: "Twelve calls on I-90 near Exit 63 (old Exit 8): mile markers, Portuguese, text-to-911 and a transfer.",
    calls: 12,
    lastCallS: 380,
  },
  {
    id: "washington_st",
    title: "Washington St",
    body: "Fights on Washington Street in Boston and Brookline; one caller gives no town.",
    calls: 4,
    lastCallS: 150,
  },
] as const;

type ScenarioId = (typeof SCENARIOS)[number]["id"];
type Speed = "1" | "5" | "10" | "20";

/** "1:12" or "45 s" for a real-time duration in seconds. */
export function realDuration(seconds: number) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")} min`;
}

type Phase = "idle" | "running" | "stopped" | "finished";

export function simPhase(status: SimStatus | null): Phase {
  if (!status?.scenario_id) return "idle";
  if (status.running) return "running";
  return status.calls_total > 0 && status.calls_sent >= status.calls_total ? "finished" : "stopped";
}

const PHASE_WORD: Record<Phase, string> = {
  idle: "Not started",
  running: "Running",
  stopped: "Stopped",
  finished: "Finished",
};

/** Simulated clock between events: the last reported offset plus the real time since, times speed. */
function useSimClock(status: SimStatus | null) {
  const [now, setNow] = useState(() => Date.now());
  const anchor = useRef({ at: Date.now(), offset: 0 });
  useEffect(() => {
    anchor.current = { at: Date.now(), offset: status?.t_offset_s ?? 0 };
    setNow(Date.now());
  }, [status]);
  useEffect(() => {
    if (!status?.running) return;
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, [status?.running]);
  if (!status?.running) return status?.t_offset_s ?? 0;
  return anchor.current.offset + ((now - anchor.current.at) / 1000) * status.speed;
}

function ReplayProgress({ status }: { status: SimStatus | null }) {
  const phase = simPhase(status);
  const scenario = SCENARIOS.find((s) => s.id === status?.scenario_id);
  const lastCall = scenario?.lastCallS ?? status?.t_offset_s ?? 0;
  const clock = Math.min(useSimClock(status), lastCall);
  const sent = status?.calls_sent ?? 0;
  const total = status?.calls_total ?? 0;
  const share = total ? sent / total : 0;
  const left = status && phase === "running" ? (lastCall - clock) / status.speed : 0;

  return (
    <section aria-labelledby="progress-h" className="grid gap-3 rounded border border-rule-soft bg-card p-5" data-tour="sim-progress">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center">
          <SpecLabel as="h2" id="progress-h" k="Replay" rest={[scenario?.title ?? "no scenario", PHASE_WORD[phase]]} />
          <TourHint tour="sim" target="sim-progress" label="replay progress" />
        </div>
        <span className="font-mono text-[12px] tracking-[0.08em] text-ink-soft">
          Sim clock <span className="num text-ink">{tPlusSeconds(clock)}</span>
        </span>
      </div>
      <div
        role="progressbar"
        aria-label="Calls replayed"
        aria-valuemin={0}
        aria-valuemax={total || 1}
        aria-valuenow={sent}
        aria-valuetext={`${sent} of ${total} calls`}
        className="h-1.5 overflow-hidden rounded bg-raised"
      >
        <div className="h-full bg-ink transition-[width] duration-500" style={{ width: `${Math.round(share * 100)}%` }} />
      </div>
      <p className="text-[14px] text-ink" aria-live="polite">
        {phase === "idle" && "No replay yet. Pick a scenario and press Start."}
        {phase === "running" &&
          `${sent} of ${total} calls in. Waiting for the next call · about ${realDuration(left)} left at ${status?.speed}×.`}
        {phase === "stopped" && `Stopped after ${sent} of ${total} calls. Start replays from the first call.`}
        {phase === "finished" && `Finished: all ${total} calls replayed. Start to watch it again.`}
      </p>
      {phase !== "idle" && (
        <p className="cap">
          Watch the calls merge into incidents on the{" "}
          <Link to="/operator" className="text-ink">
            Operator page
          </Link>
          .
        </p>
      )}
    </section>
  );
}

const DEFAULTS: RuntimeSettings = {
  auto_link_threshold: 0.85,
  suggest_threshold: 0.5,
  time_window_min: 30,
  mass_event_mode: false,
  radius_m: {},
};

function Slider({
  id,
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="grid gap-1.5">
      <label htmlFor={id} className="field-label flex justify-between">
        {label} <span className="num text-ink">{format(value)}</span>
      </label>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full accent-brand"
      />
    </div>
  );
}

/** /sim: scenario, speed, Start/Stop/Reset, mass-event mode, thresholds with Apply & Replay, metrics. */
export default function Sim() {
  const { metrics, settings, simStatus, refresh, setSettings, setSimStatus, pushToast } = useConsole();
  const [scenario, setScenario] = useState<ScenarioId>("mass_ave_robbery");
  const [speed, setSpeed] = useState<Speed>("10");
  const [draft, setDraft] = useState<RuntimeSettings>(settings ?? DEFAULTS);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (settings) setDraft(settings);
  }, [settings]);

  const run = async (label: string, action: () => Promise<void>) => {
    setBusy(label);
    try {
      await action();
      await refresh();
    } catch (error) {
      pushToast({ title: `${label} failed`, body: errorMessage(error), tone: "error" });
    } finally {
      setBusy(null);
    }
  };

  // Start always begins on a clean console, so a second run doesn't pile its calls
  // onto the incidents of the first one.
  const start = () =>
    run("Start", async () => {
      await api.reset();
      setSimStatus(await api.startSim({ scenario_id: scenario, speed: Number(speed) }));
    });
  const stop = () => run("Stop", async () => setSimStatus(await api.stopSim()));
  const reset = () => run("Reset", async () => setSimStatus(await api.reset()));
  const applyAndReplay = () =>
    run("Apply & Replay", async () => {
      const saved = await api.putSettings({
        auto_link_threshold: draft.auto_link_threshold,
        suggest_threshold: Math.min(draft.suggest_threshold, draft.auto_link_threshold),
        time_window_min: draft.time_window_min,
        mass_event_mode: draft.mass_event_mode,
      });
      setSettings(saved);
      await api.reset();
      setSimStatus(await api.startSim({ scenario_id: scenario, speed: Number(speed) }));
    });

  const index = SCENARIOS.findIndex((s) => s.id === scenario);
  const selected = SCENARIOS[index];
  const running = simStatus?.running ?? false;

  return (
    <div className="h-full overflow-y-auto">
      <FeatureTour id="sim" />
      <div className="mx-auto grid max-w-6xl gap-8 p-4 md:p-8">
        <header className="grid gap-2">
          <SpecLabel k="Simulation" rest={["synthetic calls", "simulated clock"]} />
          <h1 className="font-serif text-[clamp(1.7rem,3.2vw,2.4rem)] font-medium leading-[1.08] tracking-[-0.02em]">
            Replay a scenario.
          </h1>
        </header>

        <section aria-labelledby="scenario-h" className="grid gap-3" data-tour="sim-scenario">
          <div className="flex items-center">
            <h2 id="scenario-h" className="field-label">
              Scenario
            </h2>
            <TourHint tour="sim" target="sim-scenario" label="scenarios" />
          </div>
          <div
            role="radiogroup"
            aria-labelledby="scenario-h"
            className="grid gap-3 md:grid-cols-3"
            onKeyDown={(event) => {
              const next = nextIndex(event.key, index, SCENARIOS.length);
              if (next === null) return;
              event.preventDefault();
              setScenario(SCENARIOS[next].id);
              (event.currentTarget.querySelectorAll<HTMLElement>('[role="radio"]')[next] ?? null)?.focus();
            }}
          >
            {SCENARIOS.map((item) => (
              <ChoiceCard
                key={item.id}
                radio
                selected={scenario === item.id}
                title={item.title}
                body={item.body}
                onSelect={() => setScenario(item.id)}
              />
            ))}
          </div>
          <p className="cap">
            {selected.calls} calls over {realDuration(selected.lastCallS)} of call time · about{" "}
            {realDuration(selected.lastCallS / Number(speed))} at {speed}×.
          </p>
        </section>

        <section aria-label="Replay controls" className="flex flex-wrap items-end gap-6">
          <div className="grid gap-2" data-tour="sim-speed">
            <span className="field-label flex items-center" id="speed-l">
              Speed
              <TourHint tour="sim" target="sim-speed" label="speed" />
            </span>
            <Segmented
              label="Speed"
              value={speed}
              onChange={setSpeed}
              options={[
                { value: "1", label: "1×" },
                { value: "5", label: "5×" },
                { value: "10", label: "10×" },
                { value: "20", label: "20×" },
              ]}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2" data-tour="sim-controls">
            <Button variant="primary" icon="arrow" onClick={start} disabled={busy !== null}>
              {busy === "Start" ? "Starting…" : "Start"}
            </Button>
            <Button variant="ghost" onClick={stop} disabled={busy !== null || !running}>
              Stop
            </Button>
            <Button variant="quiet" onClick={reset} disabled={busy !== null}>
              Reset
            </Button>
            <TourHint tour="sim" target="sim-controls" label="the replay controls" />
          </div>
          <p className="cap basis-full">
            {speed === "1"
              ? "1× is real time: calls can be up to a minute apart, and the first gap is 30–60 s."
              : "Start clears the console, then replays from the first call."}
          </p>
        </section>

        <ReplayProgress status={simStatus} />

        <section aria-labelledby="tune-h" className="grid gap-4 rounded border border-rule-soft bg-card p-5" data-tour="sim-thresholds">
          <div className="flex items-center">
            <h2 id="tune-h" className="font-serif text-[22px] font-medium tracking-[-0.01em]">
              Thresholds
            </h2>
            <TourHint tour="sim" target="sim-thresholds" label="thresholds" />
          </div>
          <div className="grid gap-2" data-tour="sim-mass">
            <span className="field-label flex items-center">
              Mass-event mode
              <TourHint tour="sim" target="sim-mass" label="mass-event mode" />
            </span>
            <Segmented
              label="Mass-event mode"
              value={draft.mass_event_mode ? "on" : "off"}
              onChange={(value) => setDraft({ ...draft, mass_event_mode: value === "on" })}
              options={[
                { value: "off", label: "Off" },
                { value: "on", label: "On" },
              ]}
            />
            <p className="cap">On: auto-link needs 0.90 and the time window doubles.</p>
          </div>
          <div className="grid gap-5 md:grid-cols-3">
            <Slider
              id="auto"
              label="Auto-link at"
              value={draft.auto_link_threshold}
              min={0.5}
              max={1}
              step={0.01}
              format={(v) => v.toFixed(2)}
              onChange={(v) => setDraft({ ...draft, auto_link_threshold: v })}
            />
            <Slider
              id="suggest"
              label="Suggest at"
              value={draft.suggest_threshold}
              min={0.2}
              max={0.85}
              step={0.01}
              format={(v) => v.toFixed(2)}
              onChange={(v) => setDraft({ ...draft, suggest_threshold: v })}
            />
            <Slider
              id="window"
              label="Time window"
              value={draft.time_window_min}
              min={5}
              max={120}
              step={5}
              format={(v) => `${v} min`}
              onChange={(v) => setDraft({ ...draft, time_window_min: v })}
            />
          </div>
          <div className="flex flex-wrap items-center gap-3" data-tour="sim-apply">
            <Button variant="ghost" onClick={applyAndReplay} disabled={busy !== null}>
              {busy === "Apply & Replay" ? "Replaying…" : "Apply & Replay"}
            </Button>
            <p className="cap">Saves the settings, clears the console, then replays the selected scenario.</p>
          </div>
        </section>

        <MetricsPanel metrics={metrics} />
      </div>
    </div>
  );
}
