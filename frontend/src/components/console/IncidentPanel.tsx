import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import type { IncidentDetail, QueueItem } from "../../api/types";
import { Button, SpecLabel } from "../../ui";
import { isCritical, pct, sentence, tPlus } from "../../lib/format";
import { useConsole } from "../../store";
import { BandChip, CriticalBadge, NewInfoBadge, PriorityPill } from "./chips";
import { ConsensusBars, Contradictions, TransferBanner } from "./evidence";
import { WhyLinkedModal } from "./WhyLinkedModal";
import { TourHint } from "../../tour/FeatureTour";

export function IncidentHeader({ detail }: { detail: IncidentDetail }) {
  const { incident, location } = detail;
  return (
    <header className="grid gap-2">
      <SpecLabel k="Incident" rest={[incident.id, `${incident.call_count} calls`]} />
      <h1 className="font-serif text-[clamp(1.5rem,2.4vw,1.9rem)] font-medium leading-[1.1] tracking-[-0.02em]">
        {sentence(incident.type)}, {location.label}
      </h1>
      <div className="flex flex-wrap items-center gap-2">
        {isCritical(incident.severity) && <CriticalBadge />}
        <span className="cap">
          Location confidence {pct(location.confidence)}
          {location.ambiguous ? ` · ambiguous: ${location.candidates.join(", ")}` : ""}
        </span>
      </div>
      <p className="cap">
        First call T+00:00 · dispatch ready{" "}
        {incident.dispatch_ready_at ? tPlus(incident.dispatch_ready_at, incident.first_seen) : "not yet"}
      </p>
    </header>
  );
}

function CallRow({
  item,
  first = false,
  origin,
  canSplit,
  onWhy,
}: {
  item: QueueItem;
  first?: boolean;
  origin: string;
  canSplit: boolean;
  onWhy: () => void;
}) {
  const { selectedCallId, selectCall, refresh, pushToast } = useConsole();
  const [busy, setBusy] = useState<"confirm" | "split" | null>(null);
  const selected = selectedCallId === item.call_id;

  const act = async (kind: "confirm" | "split") => {
    setBusy(kind);
    try {
      await (kind === "confirm" ? api.confirm(item.call_id) : api.split(item.call_id));
      await refresh();
    } catch (error) {
      pushToast({ title: kind === "confirm" ? "Couldn't confirm" : "Couldn't split", body: errorMessage(error), tone: "error" });
    } finally {
      setBusy(null);
    }
  };

  return (
    <li
      className={`grid gap-2 border-t border-rule-soft py-3 ${isCritical(item.severity) ? "border-l-[3px] border-l-brand pl-3" : ""}`}
    >
      <button
        type="button"
        onClick={() => selectCall(item.call_id, item.incident_id)}
        aria-pressed={selected}
        className={`flex items-start gap-3 rounded text-left ${selected ? "text-ink" : "text-ink-soft hover:text-ink"}`}
      >
        <PriorityPill priority={item.priority} />
        <span className="min-w-0 flex-1">
          <span className="block text-[13.5px] text-ink">{item.summary || item.location_label}</span>
          <span className="cap">
            {item.call_id} · {tPlus(item.received_at, origin)} · {item.caller_role} · {item.language}
          </span>
        </span>
      </button>
      <div className="flex flex-wrap items-center gap-1.5" data-tour={first ? "call-actions" : undefined}>
        <BandChip band={item.band} />
        {item.new_info && <NewInfoBadge reasons={item.override_reasons} />}
        <span className="flex-1" />
        <Button size="sm" variant="quiet" onClick={onWhy}>
          Why linked?
        </Button>
        {(item.band === "suggest" || item.band === "auto") && (
          <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => act("confirm")}>
            {busy === "confirm" ? "Confirming…" : "Confirm"}
          </Button>
        )}
        {canSplit && item.band !== "new" && (
          <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => act("split")}>
            {busy === "split" ? "Splitting…" : "Split"}
          </Button>
        )}
      </div>
    </li>
  );
}

/** Incident panel: header, transfer banner, consensus, contradictions and calls with overrides. */
export function IncidentPanel({ detail }: { detail: IncidentDetail }) {
  const [why, setWhy] = useState<string | null>(null);
  return (
    <div className="grid gap-5">
      <div data-tour="incident">
        <IncidentHeader detail={detail} />
      </div>
      <TransferBanner transfers={detail.transfers} />
      <section aria-labelledby="consensus-h" className="grid gap-2" data-tour="consensus">
        <div className="flex items-center">
          <SpecLabel as="h2" id="consensus-h" k="What callers report" rest={["share · sources · first-hand"]} />
          <TourHint tour="operator" target="consensus" label="what callers report" />
        </div>
        <ConsensusBars consensus={detail.consensus} />
      </section>
      <Contradictions items={detail.contradictions} />
      <section aria-labelledby="calls-h" className="grid gap-1" data-tour="calls">
        <div className="flex items-center">
          <SpecLabel as="h2" id="calls-h" k="Calls" rest={[String(detail.calls.length)]} />
          <TourHint tour="operator" target="calls" label="link bands" />
        </div>
        <ul>
          {detail.calls.map((item, index) => (
            <CallRow
              key={item.call_id}
              first={index === 0}
              item={item}
              origin={detail.incident.first_seen}
              canSplit={detail.calls.length > 1}
              onWhy={() => setWhy(item.call_id)}
            />
          ))}
        </ul>
      </section>
      {why && <WhyLinkedModal callId={why} onClose={() => setWhy(null)} />}
    </div>
  );
}
