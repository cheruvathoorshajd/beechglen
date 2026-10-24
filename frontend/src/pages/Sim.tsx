import { useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { RuntimeSettings } from "../api/types";
import { Button, ChoiceCard, Segmented, SpecLabel, nextIndex } from "../ui";
import { useConsole } from "../store";
import { MetricsPanel } from "../components/console/shell";

export const SCENARIOS = [
  {
    id: "mass_ave_robbery",
    title: "Mass Ave robbery",
    body: "Eleven calls about one robbery near Boylston St, then a fire with people trapped a block away.",
  },
  {
    id: "pike_crash",
    title: "Pike crash",
    body: "Twelve calls on I-90 near Exit 63 (old Exit 8): mile markers, Portuguese, text-to-911 and a transfer.",
  },
  {
    id: "washington_st",
    title: "Washington St",
    body: "Fights on Washington Street in Boston and Brookline; one caller gives no town.",
  },
] as const;

type ScenarioId = (typeof SCENARIOS)[number]["id"];
type Speed = "1" | "5" | "10" | "20";

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

  const start = () => run("Start", async () => setSimStatus(await api.startSim({ scenario_id: scenario, speed: Number(speed) })));
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
  const running = simStatus?.running ?? false;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto grid max-w-6xl gap-8 p-4 md:p-8">
        <header className="grid gap-2">
          <SpecLabel k="Simulation" rest={["synthetic calls", "simulated clock"]} />
          <h1 className="font-serif text-[clamp(1.7rem,3.2vw,2.4rem)] font-medium leading-[1.08] tracking-[-0.02em]">
            Replay a scenario.
          </h1>
        </header>

        <section aria-labelledby="scenario-h" className="grid gap-3">
          <h2 id="scenario-h" className="field-label">
            Scenario
          </h2>
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
        </section>

        <section aria-label="Replay controls" className="flex flex-wrap items-end gap-6">
          <div className="grid gap-2">
            <span className="field-label" id="speed-l">
              Speed
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
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" icon="arrow" onClick={start} disabled={busy !== null}>
              {busy === "Start" ? "Starting…" : "Start"}
            </Button>
            <Button variant="ghost" onClick={stop} disabled={busy !== null || !running}>
              Stop
            </Button>
            <Button variant="quiet" onClick={reset} disabled={busy !== null}>
              Reset
            </Button>
          </div>
          <p className="cap">
            {simStatus?.scenario_id
              ? `${simStatus.scenario_id}: ${simStatus.calls_sent} of ${simStatus.calls_total} calls${running ? " · running" : ""}`
              : "No replay yet."}
          </p>
        </section>

        <section aria-labelledby="tune-h" className="grid gap-4 rounded border border-rule-soft bg-card p-5">
          <h2 id="tune-h" className="font-serif text-[22px] font-medium tracking-[-0.01em]">
            Thresholds
          </h2>
          <div className="grid gap-2">
            <span className="field-label">Mass-event mode</span>
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
          <div className="flex flex-wrap items-center gap-3">
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
