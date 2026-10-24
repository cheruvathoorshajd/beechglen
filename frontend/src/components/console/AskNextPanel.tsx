import { useEffect, useState } from "react";
import { api, errorMessage } from "../../api/client";
import type { AskNext } from "../../api/types";
import { SpecLabel } from "../../ui";

/** Ask-next for the selected call: a confirm line plus 2-3 open questions.
 *  The town question is highlighted when the caller's location is ambiguous. */
export function AskNextPanel({ callId, refreshKey }: { callId: string | null; refreshKey: string }) {
  const [ask, setAsk] = useState<AskNext | null>(null);
  const [ambiguous, setAmbiguous] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!callId) return;
    let live = true;
    setError(null);
    Promise.all([api.askNext(callId), api.call(callId)])
      .then(([next, detail]) => {
        if (!live) return;
        setAsk(next);
        setAmbiguous(detail.location.ambiguous);
      })
      .catch((e) => live && setError(errorMessage(e)));
    return () => {
      live = false;
    };
  }, [callId, refreshKey]);

  return (
    <section aria-labelledby="ask-h" className="grid gap-3 rounded border border-rule-soft bg-card p-4">
      <SpecLabel as="h2" id="ask-h" k="Ask next" rest={callId ? [callId] : ["select a call"]} />
      {!callId && <p className="text-[13.5px] text-ink-soft">Select a call to see what to ask the caller.</p>}
      {error && <p className="ferr" role="alert">{error}</p>}
      {callId && ask && (
        <>
          {ask.confirm_line && <p className="text-[15px] text-ink">{ask.confirm_line}</p>}
          <ol className="grid gap-2">
            {ask.questions.map((question, index) => {
              const town = ambiguous && /town/i.test(question);
              return (
                <li
                  key={question}
                  className={`flex gap-3 rounded border p-2.5 text-[14px] ${town ? "border-brand text-ink" : "border-rule-soft text-ink"}`}
                >
                  <span className="num text-ink-soft">{String(index + 1).padStart(2, "0")}</span>
                  <span className="flex-1">{question}</span>
                  {town && <span className="badge highlight self-start">Ask first</span>}
                </li>
              );
            })}
          </ol>
          <p className="cap">Open questions only; never suggest an answer.</p>
        </>
      )}
    </section>
  );
}
