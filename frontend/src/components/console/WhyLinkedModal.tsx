import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../api/client";
import type { LinkDecision, RuntimeSettings } from "../../api/types";
import { Badge, Button, SpecLabel } from "../../ui";
import { BAND_LABEL, GATE_WORDS, LINK_WEIGHTS, pct, words } from "../../lib/format";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import { useConsole } from "../../store";

type Component = keyof typeof LINK_WEIGHTS;
const COMPONENTS: { key: Component; label: string; meaning: string }[] = [
  { key: "geo", label: "Place", meaning: "distance to the incident" },
  { key: "time", label: "Time", meaning: "minutes since its last call" },
  { key: "type", label: "Type", meaning: "same or compatible emergency" },
  { key: "entity", label: "Details", meaning: "shared suspect and vehicle details" },
];

function thresholds(settings: RuntimeSettings | null) {
  const auto = settings?.auto_link_threshold ?? 0.85;
  const mass = settings?.mass_event_mode ?? false;
  return { auto: mass ? Math.max(auto, 0.9) : auto, suggest: settings?.suggest_threshold ?? 0.5, mass };
}

/** One sentence that says why the call landed in its band. */
export function explainOutcome(decision: LinkDecision, settings: RuntimeSettings | null) {
  const { auto, suggest, mass } = thresholds(settings);
  const p = decision.p_same.toFixed(2);
  const scored = Object.values(decision.components).some((value) => value !== null);
  const autoText = `${auto.toFixed(2)}${mass ? " (mass-event mode)" : ""}`;
  if (decision.gates.includes("operator_split")) {
    return `An operator split this call into its own incident, ${decision.incident_id}. The scores below are from its original link.`;
  }
  if (decision.band === "new") {
    if (!scored) {
      return `No open incident was within range and inside the time window, so there was nothing to compare. This call started ${decision.incident_id}.`;
    }
    return `The closest open incident scored ${p}, below the ${suggest.toFixed(2)} needed to suggest a link, so this call started ${decision.incident_id}.`;
  }
  if (decision.band === "confirmed") {
    return `An operator confirmed this link to ${decision.incident_id}. The system had scored it ${p}.`;
  }
  if (decision.band === "suggest") {
    return decision.gates.includes("low_location_confidence")
      ? `Scored ${p}, high enough to link, but the location is unresolved, so it waits for an operator to confirm ${decision.incident_id}.`
      : `Scored ${p}: at least ${suggest.toFixed(2)} but under ${autoText}, so it waits for an operator to confirm ${decision.incident_id}.`;
  }
  return `Scored ${p}, at or above ${autoText}, so it linked to ${decision.incident_id} on its own.`;
}

/** "Why linked?": the outcome in words, each component's score and share of p, the gates, who decided. */
export function WhyLinkedModal({ callId, onClose }: { callId: string; onClose: () => void }) {
  const settings = useConsole((s) => s.settings);
  const [decision, setDecision] = useState<LinkDecision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useFocusTrap(dialog, onClose);

  useEffect(() => {
    heading.current?.focus();
    let live = true;
    setDecision(null);
    setError(null);
    api
      .explain(callId)
      .then((value) => live && setDecision(value))
      .catch((e) => live && setError(`Couldn't load the link decision: ${errorMessage(e)}`));
    return () => {
      live = false;
    };
  }, [callId]);

  const available = decision ? COMPONENTS.filter((c) => decision.components[c.key] !== null) : [];
  const totalWeight = available.reduce((sum, c) => sum + LINK_WEIGHTS[c.key], 0);
  const rawScore = decision
    ? available.reduce((sum, c) => sum + (decision.components[c.key] ?? 0) * LINK_WEIGHTS[c.key], 0) / (totalWeight || 1)
    : 0;
  const capped = decision !== null && available.length > 0 && decision.p_same < rawScore - 0.005;

  return (
    <div className="fixed inset-0 z-[1000] grid place-items-center bg-[var(--ground-veil)] p-4" onMouseDown={onClose}>
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="why-h"
        className="grid max-h-[90vh] w-full max-w-xl gap-4 overflow-auto rounded border border-rule bg-card p-5"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="grid gap-2">
            <SpecLabel k="Why linked?" rest={[callId]} />
            <h2 ref={heading} tabIndex={-1} id="why-h" className="font-serif text-[22px] font-medium leading-tight tracking-[-0.01em] outline-none">
              {decision ? `${BAND_LABEL[decision.band]} · p = ${decision.p_same.toFixed(2)}` : error ? "Decision unavailable" : "Loading the decision…"}
            </h2>
          </div>
          <Button variant="quiet" size="sm" icon="close" onClick={onClose} aria-label="Close">
            Close
          </Button>
        </div>

        {error && (
          <p className="ferr" role="alert">
            {error}
          </p>
        )}

        {decision && (
          <>
            <p className="text-[15px] text-ink" data-testid="why-outcome">
              {explainOutcome(decision, settings)}
            </p>

            {available.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[460px] border-collapse font-mono text-[12px]">
                  <caption className="sr-only">Link score components</caption>
                  <thead>
                    <tr className="text-left text-[10.5px] uppercase tracking-[0.12em] text-ink-soft">
                      <th scope="col" className="py-1.5 font-medium">
                        Component
                      </th>
                      <th scope="col" className="py-1.5 text-right font-medium">
                        Score
                      </th>
                      <th scope="col" className="py-1.5 text-right font-medium">
                        Weight
                      </th>
                      <th scope="col" className="py-1.5 text-right font-medium">
                        Adds to p
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {COMPONENTS.map(({ key, label, meaning }) => {
                      const value = decision.components[key];
                      const share = value === null || !totalWeight ? null : (value * LINK_WEIGHTS[key]) / totalWeight;
                      return (
                        <tr key={key} className="border-t border-rule-soft align-top">
                          <th scope="row" className="py-2 pr-3 text-left font-normal">
                            <span className="block text-ink">{label}</span>
                            <span className="block font-sans text-[12px] text-ink-soft">{meaning}</span>
                          </th>
                          <td className="num py-2 text-right text-ink">{value === null ? "n/a" : value.toFixed(2)}</td>
                          <td className="num py-2 text-right text-ink-soft">
                            {value === null ? "dropped" : `${pct(LINK_WEIGHTS[key])} → ${pct(LINK_WEIGHTS[key] / totalWeight)}`}
                          </td>
                          <td className="num py-2 text-right text-ink">{share === null ? "—" : share.toFixed(2)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-rule">
                      <th scope="row" className="py-2 text-left font-medium text-ink">
                        p_same
                      </th>
                      <td colSpan={3} className="num py-2 text-right text-ink">
                        {capped ? `${rawScore.toFixed(2)} → capped at ${decision.p_same.toFixed(2)}` : decision.p_same.toFixed(2)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
            {available.length > 0 && available.length < COMPONENTS.length && (
              <p className="cap">Unavailable components are dropped and the remaining weights renormalized to 100%.</p>
            )}

            <div className="grid gap-2">
              <span className="field-label">Gates</span>
              {decision.gates.length ? (
                <ul className="grid gap-1.5">
                  {decision.gates.map((gate) => (
                    <li key={gate} className="flex gap-2 text-[13.5px] text-ink">
                      <span className="text-warn" aria-hidden="true">
                        △
                      </span>
                      {GATE_WORDS[gate] ?? words(gate)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[13.5px] text-ink-soft">No gate applied.</p>
              )}
            </div>
            <p className="flex flex-wrap items-center gap-2 text-[13.5px] text-ink-soft">
              Decided by <Badge>{decision.decided_by}</Badge>
              <span className="cap">
                Bands: auto ≥ {thresholds(settings).auto.toFixed(2)} · suggest ≥ {thresholds(settings).suggest.toFixed(2)} · below that, a new
                incident
              </span>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
