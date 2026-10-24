import { useEffect, useRef, useState } from "react";
import { SpecLabel } from "../ui";
import { useConsole, queueOrigin } from "../store";
import { QueueCard } from "../components/console/QueueCard";
import { IncidentMap } from "../components/console/IncidentMap";
import { IncidentPanel } from "../components/console/IncidentPanel";
import { AskNextPanel } from "../components/console/AskNextPanel";
import { DispatchPackageCard } from "../components/console/evidence";

/** /operator: queue · map · incident panel. Fits 1440×900 without page scroll; panels scroll. */
export default function Operator() {
  const { queue, incidents, incident, selectedIncidentId, selectedCallId, selectIncident, selectCall, loaded } = useConsole();
  const origin = queueOrigin(queue);
  const first = queue[0]?.call_id;
  const previousFirst = useRef<string | undefined>(undefined);
  const [flashId, setFlashId] = useState<string | null>(null);

  useEffect(() => {
    if (first && previousFirst.current && first !== previousFirst.current) {
      setFlashId(first);
      const timer = setTimeout(() => setFlashId(null), 1500);
      previousFirst.current = first;
      return () => clearTimeout(timer);
    }
    previousFirst.current = first;
  }, [first]);

  const activeCall = selectedCallId ?? incident?.calls[incident.calls.length - 1]?.call_id ?? null;

  return (
    <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[minmax(300px,360px)_minmax(0,1fr)_minmax(360px,460px)]">
      <section aria-labelledby="queue-h" className="flex min-h-0 flex-col border-r border-rule-soft">
        <div className="border-b border-rule-soft px-4 py-3">
          <SpecLabel as="h2" id="queue-h" k="Queue" rest={[`${queue.length} calls`, "priority, then oldest"]} />
        </div>
        <ol className="grid min-h-0 flex-1 content-start gap-2 overflow-y-auto p-3">
          {loaded && !queue.length && (
            <li className="rounded border border-dashed border-rule p-4 text-[13.5px] text-ink-soft">
              No calls yet. Start a scenario from Sim; calls appear here as they come in.
            </li>
          )}
          {queue.map((item) => (
            <li key={item.call_id}>
              <QueueCard
                item={item}
                origin={origin}
                selected={item.call_id === selectedCallId}
                flash={item.call_id === flashId}
                onSelect={() => selectCall(item.call_id, item.incident_id)}
              />
            </li>
          ))}
        </ol>
      </section>

      <section aria-label="Map" className="min-h-[320px] border-r border-rule-soft">
        <IncidentMap incidents={incidents} selectedId={selectedIncidentId} onSelect={selectIncident} />
      </section>

      <section aria-label="Selected incident" className="min-h-0 overflow-y-auto p-4">
        {incident ? (
          <div className="grid gap-5">
            <IncidentPanel detail={incident} />
            <AskNextPanel callId={activeCall} refreshKey={`${incident.incident.last_seen}-${incident.timeline.length}`} />
            <DispatchPackageCard dispatch={incident.dispatch} />
          </div>
        ) : (
          <p className="text-[13.5px] text-ink-soft">Select an incident on the map or a call in the queue.</p>
        )}
      </section>
    </div>
  );
}
