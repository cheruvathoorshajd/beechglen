import type { Band, OverrideReason } from "../../api/types";
import { Badge } from "../../ui";
import { BAND_LABEL, BAND_MEANING, REASON_WORDS, priorityTone } from "../../lib/format";

const PILL: Record<ReturnType<typeof priorityTone>, string> = {
  high: "bg-brand border-brand text-ink",
  mid: "border-warn text-warn",
  low: "border-rule text-ink-soft",
};

/** Priority pill: always shows the number; 80+ crimson fill, 50-79 warn outline, below 50 grey. */
export function PriorityPill({ priority }: { priority: number }) {
  const tone = priorityTone(priority);
  return (
    <span
      data-tone={tone}
      title={`Priority ${priority} of 100`}
      className={`num inline-flex h-7 min-w-[2.6rem] items-center justify-center rounded border px-2 text-[13px] font-medium ${PILL[tone]}`}
    >
      <span className="sr-only">Priority </span>
      {priority}
    </span>
  );
}

export function BandChip({ band }: { band: Band }) {
  const label = BAND_LABEL[band];
  const title = BAND_MEANING[band];
  if (band === "suggest") return <Badge tone="warn">{label} · needs you</Badge>;
  if (band === "new") return <Badge tone="highlight">{label}</Badge>;
  if (band === "confirmed") return <Badge tone="ok">✓ {label}</Badge>;
  return (
    <span title={title}>
      <Badge>{label}</Badge>
    </span>
  );
}

export function CriticalBadge() {
  return <Badge tone="critical">● Critical</Badge>;
}

export function NewInfoBadge({ reasons }: { reasons: OverrideReason[] }) {
  const words = reasons.map((reason) => REASON_WORDS[reason] ?? reason).join(", ");
  return <Badge tone="highlight">New info{words ? ` · ${words}` : ""}</Badge>;
}
