import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Briefing } from "../api/types";
import { Badge, SpecLabel } from "../ui";
import { isCritical, sentence } from "../lib/format";
import { useConsole } from "../store";
import { CriticalBadge, PriorityPill } from "../components/console/chips";
import { DispatchPackageCard } from "../components/console/evidence";
import { BriefingCard, LeadsBoard } from "../components/console/officer";
import { IncidentHeader } from "../components/console/IncidentPanel";

/** /officer: incident list, three-line briefing, dispatch package and leads board. */
export default function Officer() {
  const { incidents, incident, selectedIncidentId, selectIncident, loaded } = useConsole();
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const version = incident ? `${incident.incident.id}-${incident.incident.last_seen}-${incident.timeline.length}` : "";

  useEffect(() => {
    if (!incident) return;
    let live = true;
    setBriefing(null);
    api
      .briefing(incident.incident.id)
      .then((value) => live && setBriefing(value))
      .catch(() => live && setBriefing({ known: "Briefing unavailable.", disputed: "None", open: "Try again shortly." }));
    return () => {
      live = false;
    };
  }, [version]); // re-fetch only when the incident changes, not on every refresh

  return (
    <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[minmax(280px,340px)_minmax(0,1fr)]">
      <section aria-labelledby="inc-h" className="flex min-h-0 flex-col border-r border-rule-soft">
        <div className="border-b border-rule-soft px-4 py-3">
          <SpecLabel as="h2" id="inc-h" k="Incidents" rest={[`${incidents.length} open`]} />
        </div>
        <ul className="grid min-h-0 flex-1 content-start gap-2 overflow-y-auto p-3">
          {loaded && !incidents.length && (
            <li className="rounded border border-dashed border-rule p-4 text-[13.5px] text-ink-soft">
              New incidents appear here as calls come in.
            </li>
          )}
          {incidents.map((item) => {
            const critical = isCritical(item.severity);
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => selectIncident(item.id)}
                  aria-pressed={item.id === selectedIncidentId}
                  className={`grid w-full gap-1.5 rounded border p-3 text-left ${critical ? "border-l-[3px] border-l-brand" : ""} ${
                    item.id === selectedIncidentId ? "border-ink-soft bg-raised" : "border-rule-soft bg-card hover:border-rule"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <PriorityPill priority={item.top_priority} />
                    <span className="font-serif text-[19px] font-medium leading-tight tracking-[-0.01em] text-ink">
                      {sentence(item.type)}
                    </span>
                  </div>
                  <span className="text-[13.5px] text-ink-soft">{item.location_label}</span>
                  <div className="flex flex-wrap gap-1.5">
                    {critical && <CriticalBadge />}
                    <Badge>{item.call_count} calls</Badge>
                    {item.dispatch_ready_at && <Badge tone="ok">Dispatch ready</Badge>}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-label="Officer view" className="min-h-0 overflow-y-auto p-4 md:p-6">
        {incident ? (
          <div className="grid gap-5">
            <IncidentHeader detail={incident} />
            <div className="grid gap-5 xl:grid-cols-2">
              <BriefingCard briefing={briefing} />
              <DispatchPackageCard dispatch={incident.dispatch} />
            </div>
            <LeadsBoard incidentId={incident.incident.id} leads={incident.leads} />
          </div>
        ) : (
          <p className="text-[13.5px] text-ink-soft">Select an incident to see its briefing and leads.</p>
        )}
      </section>
    </div>
  );
}
