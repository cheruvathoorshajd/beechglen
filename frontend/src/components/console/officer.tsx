import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import type { Briefing, Lead, LeadStatus } from "../../api/types";
import { Badge, Button, SpecLabel } from "../../ui";
import { useConsole } from "../../store";
import { TourHint } from "../../tour/FeatureTour";

/** Three-line officer briefing: KNOWN · DISPUTED · OPEN. */
export function BriefingCard({ briefing }: { briefing: Briefing | null }) {
  const rows: [string, string | undefined][] = [
    ["Known", briefing?.known],
    ["Disputed", briefing?.disputed],
    ["Open", briefing?.open],
  ];
  return (
    <section aria-labelledby="brief-h" className="grid gap-3 rounded border border-rule-soft bg-card p-4" data-tour="briefing">
      <div className="flex items-center">
        <h2 id="brief-h" className="font-serif text-[22px] font-medium tracking-[-0.01em]">
          Briefing
        </h2>
        <TourHint tour="officer" target="briefing" label="the briefing" />
      </div>
      <dl className="grid gap-3">
        {rows.map(([label, text]) => (
          <div key={label} className="grid gap-1 border-t border-rule-soft pt-3">
            <dt>
              <SpecLabel as="div" k={label} />
            </dt>
            <dd className="text-[15px] text-ink">{text ?? "Loading…"}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

const COLUMNS: { status: LeadStatus; title: string }[] = [
  { status: "suggested", title: "Suggested" },
  { status: "open", title: "Open" },
  { status: "assigned", title: "Assigned" },
  { status: "cleared", title: "Cleared" },
];

function LeadCard({ lead }: { lead: Lead }) {
  const { refresh, pushToast } = useConsole();
  const [unit, setUnit] = useState(lead.assigned_unit ?? "");
  const [busy, setBusy] = useState(false);

  const update = async (status: LeadStatus, assigned_unit?: string) => {
    setBusy(true);
    try {
      await api.updateLead(lead.id, { status, assigned_unit });
      await refresh();
    } catch (error) {
      pushToast({ title: "Couldn't update the lead", body: errorMessage(error), tone: "error" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="grid gap-2 rounded border border-rule-soft bg-raised p-3">
      <p className="text-[13.5px] text-ink">{lead.description}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={lead.status === "suggested" ? "warn" : lead.status === "cleared" ? "ok" : "neutral"}>{lead.status}</Badge>
        {lead.assigned_unit && <span className="cap">Unit {lead.assigned_unit}</span>}
      </div>
      {lead.status === "suggested" && (
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => update("open")}>
          Accept lead
        </Button>
      )}
      {lead.status === "open" && (
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (unit.trim()) void update("assigned", unit.trim());
          }}
        >
          <label className="sr-only" htmlFor={`unit-${lead.id}`}>
            Unit for {lead.description}
          </label>
          <input
            id={`unit-${lead.id}`}
            className="inp py-1.5 text-[13px]"
            placeholder="Unit, e.g. B-101"
            value={unit}
            onChange={(event) => setUnit(event.target.value)}
          />
          <Button size="sm" variant="ghost" type="submit" disabled={busy || !unit.trim()}>
            Assign
          </Button>
        </form>
      )}
      {lead.status === "assigned" && (
        <Button size="sm" variant="quiet" disabled={busy} onClick={() => update("cleared")}>
          Clear lead
        </Button>
      )}
    </li>
  );
}

/** Leads board: suggested → open → assigned → cleared, mono headers with counts. */
export function LeadsBoard({ incidentId, leads }: { incidentId: string; leads: Lead[] }) {
  const { refresh, pushToast } = useConsole();
  const [draft, setDraft] = useState("");

  const add = async () => {
    const description = draft.trim();
    if (!description) return;
    try {
      await api.createLead({ incident_id: incidentId, description, source_claim_ids: [] });
      setDraft("");
      await refresh();
    } catch (error) {
      pushToast({ title: "Couldn't add the lead", body: errorMessage(error), tone: "error" });
    }
  };

  return (
    <section aria-labelledby="leads-h" className="grid gap-3" data-tour="leads">
      <div className="flex items-center">
        <h2 id="leads-h" className="font-serif text-[22px] font-medium tracking-[-0.01em]">
          Leads
        </h2>
        <TourHint tour="officer" target="leads" label="the leads board" />
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        {COLUMNS.map((column) => {
          const items = leads.filter((lead) => lead.status === column.status);
          return (
            <div key={column.status} className="grid content-start gap-2">
              <h3 className="flex justify-between font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-soft">
                {column.title} <span className="num">{items.length}</span>
              </h3>
              <ul className="grid gap-2">
                {items.map((lead) => (
                  <LeadCard key={lead.id} lead={lead} />
                ))}
              </ul>
            </div>
          );
        })}
      </div>
      <form
        className="flex max-w-xl gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void add();
        }}
      >
        <label className="sr-only" htmlFor="new-lead">
          New lead
        </label>
        <input
          id="new-lead"
          className="inp"
          placeholder="Add a lead, e.g. Canvass Newbury St"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Button type="submit" variant="ghost" disabled={!draft.trim()}>
          Add lead
        </Button>
      </form>
    </section>
  );
}
