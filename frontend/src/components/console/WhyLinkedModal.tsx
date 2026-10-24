import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../api/client";
import type { LinkDecision } from "../../api/types";
import { Badge, Button, SpecLabel } from "../../ui";
import { BAND_LABEL, BAND_MEANING, GATE_WORDS, LINK_WEIGHTS, pct, words } from "../../lib/format";
import { useFocusTrap } from "../../hooks/useFocusTrap";

/** "Why linked?": the score components, their weights, the gates in words, and who decided. */
export function WhyLinkedModal({ callId, onClose }: { callId: string; onClose: () => void }) {
  const [decision, setDecision] = useState<LinkDecision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useFocusTrap(dialog, onClose);

  useEffect(() => {
    heading.current?.focus();
    api.explain(callId).then(setDecision).catch((e) => setError(errorMessage(e)));
  }, [callId]);

  const components = decision ? (Object.keys(LINK_WEIGHTS) as (keyof typeof LINK_WEIGHTS)[]) : [];

  return (
    <div className="fixed inset-0 z-[1000] grid place-items-center bg-[var(--ground-veil)] p-4" onMouseDown={onClose}>
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="why-h"
        className="grid max-h-[90vh] w-full max-w-lg gap-4 overflow-auto rounded border border-rule bg-card p-5"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="grid gap-2">
            <SpecLabel k="Why linked?" rest={[callId]} />
            <h2 ref={heading} tabIndex={-1} id="why-h" className="font-serif text-[22px] font-medium leading-tight tracking-[-0.01em] outline-none">
              {decision ? `${BAND_LABEL[decision.band]} · p = ${decision.p_same.toFixed(2)}` : "Loading the decision"}
            </h2>
            {decision && <p className="text-[13.5px] text-ink-soft">{BAND_MEANING[decision.band]} ({decision.incident_id}).</p>}
          </div>
          <Button variant="quiet" size="sm" icon="close" onClick={onClose} aria-label="Close">
            Close
          </Button>
        </div>

        {error && <p className="ferr" role="alert">{error}</p>}

        {decision && (
          <>
            <table className="w-full border-collapse font-mono text-[12px]">
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
                </tr>
              </thead>
              <tbody>
                {components.map((name) => {
                  const value = decision.components[name];
                  return (
                    <tr key={name} className="border-t border-rule-soft">
                      <th scope="row" className="py-2 text-left font-normal text-ink">
                        {name}
                      </th>
                      <td className="num py-2 text-right text-ink">{value === null ? "not available" : value.toFixed(2)}</td>
                      <td className="num py-2 text-right text-ink-soft">{value === null ? "dropped" : pct(LINK_WEIGHTS[name])}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="cap">Unavailable components are dropped and the remaining weights renormalized.</p>

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
            <p className="flex items-center gap-2 text-[13.5px] text-ink-soft">
              Decided by <Badge>{decision.decided_by}</Badge>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
