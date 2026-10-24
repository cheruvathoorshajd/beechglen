import type { QueueItem } from "../../api/types";
import { Badge } from "../../ui";
import { isCritical, tPlus } from "../../lib/format";
import { BandChip, CriticalBadge, NewInfoBadge, PriorityPill } from "./chips";

/** One call in the queue. Critical uses the call's own severity (0.9+), with a word and a stripe. */
export function QueueCard({
  item,
  origin,
  selected,
  flash,
  onSelect,
}: {
  item: QueueItem;
  origin: string | null;
  selected: boolean;
  flash?: boolean;
  onSelect: () => void;
}) {
  const critical = isCritical(item.severity);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      data-critical={critical || undefined}
      className={[
        "queue-card relative grid w-full gap-2 rounded border bg-card p-3 text-left transition-colors duration-200 ease-token",
        critical ? "border-l-[3px] border-l-brand" : "",
        selected ? "border-ink-soft bg-raised" : "border-rule-soft hover:border-rule",
        flash ? "flash" : "",
      ].join(" ")}
    >
      <div className="flex items-start gap-3">
        <PriorityPill priority={item.priority} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-medium text-ink">{item.location_label || "Unknown location"}</p>
          <p className="cap">
            {item.call_id} · {tPlus(item.received_at, origin)}
          </p>
        </div>
      </div>
      {item.summary && <p className="text-[13.5px] leading-snug text-ink-soft">{item.summary}</p>}
      <div className="flex flex-wrap gap-1.5">
        {critical && <CriticalBadge />}
        <BandChip band={item.band} />
        {item.new_info && <NewInfoBadge reasons={item.override_reasons} />}
        <Badge>{item.language}</Badge>
        <Badge>{item.channel}</Badge>
        <Badge>{item.caller_role}</Badge>
      </div>
    </button>
  );
}
