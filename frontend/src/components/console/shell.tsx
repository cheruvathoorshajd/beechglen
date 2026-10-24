import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import type { Metrics } from "../../api/types";
import { USE_MOCKS } from "../../api/client";
import { LiveDot, Wordmark } from "../../ui";
import { pct, tPlusSeconds } from "../../lib/format";
import { useConsole } from "../../store";
import { useDashboardSocket } from "../../hooks/useDashboardSocket";
import { SessionControls } from "../../auth/SessionControls";

const NAV = [
  { to: "/operator", label: "Operator" },
  { to: "/officer", label: "Officer" },
  { to: "/sim", label: "Sim" },
];

/** Top bar: Wordmark, nav, connection dot and the sim T+ clock. `extra` holds header controls. */
export function TopBar({ extra }: { extra?: ReactNode }) {
  const connected = useConsole((s) => s.connected);
  const sim = useConsole((s) => s.simStatus);
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-rule-soft bg-card px-4 py-3 md:px-6">
      <div className="flex flex-wrap items-center gap-5">
        <Wordmark to="/" />
        <nav aria-label="Console" className="flex gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `rounded border px-3 py-1.5 font-mono text-[11.5px] uppercase tracking-[0.12em] no-underline transition-colors duration-200 ${
                  isActive ? "border-rule bg-raised text-ink" : "border-transparent text-ink-soft hover:text-ink"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <LiveDot live={connected} label={USE_MOCKS ? "Mock data" : connected ? "Live" : "Offline"} />
        <span className="font-mono text-[11.5px] tracking-[0.08em] text-ink-soft" aria-label="Simulation clock">
          {sim?.scenario_id ? `${sim.scenario_id} · ` : ""}
          <span className="num text-ink">{tPlusSeconds(sim?.t_offset_s ?? 0)}</span>
          {sim?.running ? " · running" : ""}
        </span>
        {extra}
      </div>
    </header>
  );
}

export function Toasts() {
  const toasts = useConsole((s) => s.toasts);
  const dismiss = useConsole((s) => s.dismissToast);
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[1100] grid w-[min(360px,calc(100vw-2rem))] gap-2" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="status"
          className={`pointer-events-auto grid gap-1 rounded border border-rule-soft bg-card p-3 ${
            toast.tone === "new-info" ? "border-l-[3px] border-l-brand" : toast.tone === "error" ? "border-l-[3px] border-l-warn" : ""
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink">{toast.title}</p>
            <button type="button" className="btn quiet sm" onClick={() => dismiss(toast.id)} aria-label="Dismiss">
              ✕
            </button>
          </div>
          {toast.body && <p className="text-[13.5px] text-ink-soft">{toast.body}</p>}
        </div>
      ))}
    </div>
  );
}

/** Live load: serif figures, mono labels. */
export function MetricsPanel({ metrics }: { metrics: Metrics | null }) {
  const items: [string, string][] = metrics
    ? [
        ["Calls", String(metrics.calls)],
        ["Incidents", String(metrics.incidents)],
        ["Collapse rate", pct(metrics.collapse_rate)],
        ["NEW INFO calls", String(metrics.new_info_calls)],
        ["Auto · suggest", `${metrics.bands.auto ?? 0} · ${metrics.bands.suggest ?? 0}`],
        ["New · confirmed", `${metrics.bands.new ?? 0} · ${metrics.bands.confirmed ?? 0}`],
        [
          "Claims verified · pending · rejected",
          `${metrics.guard.verified} · ${metrics.guard.pending_verification} · ${metrics.guard.rejected}`,
        ],
      ]
    : [];
  return (
    <section aria-labelledby="metrics-h" className="grid gap-3">
      <h2 id="metrics-h" className="font-serif text-[22px] font-medium tracking-[-0.01em]">
        Metrics
      </h2>
      {!metrics && <p className="text-[13.5px] text-ink-soft">Waiting for the server.</p>}
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {items.map(([label, value]) => (
          <div key={label} className="grid gap-1 rounded border border-rule-soft bg-card p-4">
            <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-soft">{label}</dt>
            <dd className="num font-serif text-[clamp(1.6rem,3vw,2.2rem)] font-medium leading-none tracking-[-0.02em] text-ink">
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Console frame: one socket for every console page, top bar, toasts. */
export function ConsoleLayout({ children }: { children: ReactNode }) {
  useDashboardSocket();
  return (
    <div className="enter flex h-screen min-h-0 flex-col bg-ground">
      <TopBar extra={<SessionControls />} />
      <div className="min-h-0 flex-1">{children}</div>
      <Toasts />
    </div>
  );
}
