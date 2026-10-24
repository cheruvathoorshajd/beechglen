import type { AttributeConsensus, Contradiction, DispatchPackage, TransferRecord } from "../../api/types";
import { Badge, ConfidenceBar, Contested, SpecLabel } from "../../ui";
import { attributeLabel, fieldLabel, pct, words } from "../../lib/format";

/** Every value with its share, never just the winner. Top value ok/warn, others soft. */
export function ConsensusBars({ consensus }: { consensus: AttributeConsensus[] }) {
  if (!consensus.length) return <p className="text-[13.5px] text-ink-soft">No details reported yet.</p>;
  return (
    <ul className="grid gap-4">
      {consensus.map((entry) => (
        <li key={`${entry.subject}.${entry.attribute}`} className="grid gap-2 border-t border-rule-soft pt-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-soft">
              {attributeLabel(entry.subject, entry.attribute)}
            </span>
            {entry.contested && <Contested reason="No value has 70%; callers disagree." />}
          </div>
          {entry.values.map((value, index) => (
            <ConfidenceBar
              key={value.value}
              label={words(value.value)}
              value={value.share}
              sources={value.sources}
              firstHand={value.first_hand_sources}
              tone={index === 0 ? (entry.contested ? "warn" : "ok") : "soft"}
            />
          ))}
        </li>
      ))}
    </ul>
  );
}

export function Contradictions({ items }: { items: Contradiction[] }) {
  if (!items.length) return null;
  return (
    <section aria-labelledby="contradictions-h" className="grid gap-2">
      <SpecLabel as="h2" id="contradictions-h" k="Contradictions" rest={[String(items.length)]} />
      <ul className="grid gap-1.5">
        {items.map((item) => (
          <li key={`${item.subject}.${item.attribute}`} className="flex flex-wrap gap-2 text-[13.5px]">
            <span className="text-warn" aria-hidden="true">
              △
            </span>
            <span className="text-ink">{attributeLabel(item.subject, item.attribute)}:</span>
            <span className="text-ink-soft">{item.values.map(words).join(" vs ")}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function TransferBanner({ transfers }: { transfers: TransferRecord[] }) {
  if (!transfers.length) return null;
  return (
    <div className="grid gap-1">
      {transfers.map((transfer) => (
        <p key={transfer.call_id} className="border-l-2 border-rule py-1 pl-3 font-mono text-[11.5px] text-ink-soft">
          Transferred from <span className="text-ink">{transfer.from_psap}</span> to {transfer.to_psap} · context
          preserved ({transfer.call_id})
        </p>
      ))}
    </div>
  );
}

/** Dispatch package: mono labels, value, share and sources; contested marked; neutral Illustrative badge. */
export function DispatchPackageCard({ dispatch }: { dispatch: DispatchPackage }) {
  return (
    <section aria-labelledby="dispatch-h" className="grid gap-3 rounded border border-rule-soft bg-card p-4" data-tour="dispatch">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SpecLabel as="h2" id="dispatch-h" k="Dispatch package" rest={[dispatch.rule_id]} />
        {dispatch.illustrative && <Badge>Illustrative</Badge>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] border-collapse text-[13.5px]">
          <thead>
            <tr className="text-left font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-soft">
              <th scope="col" className="py-1.5 pr-3 font-medium">
                Field
              </th>
              <th scope="col" className="py-1.5 pr-3 font-medium">
                Value
              </th>
              <th scope="col" className="py-1.5 pr-3 text-right font-medium">
                Share
              </th>
              <th scope="col" className="py-1.5 text-right font-medium">
                Sources
              </th>
            </tr>
          </thead>
          <tbody>
            {dispatch.fields.map((field) => (
              <tr key={field.name} className="border-t border-rule-soft align-top">
                <th scope="row" className="py-2 pr-3 text-left font-mono text-[10.5px] font-normal uppercase tracking-[0.1em] text-ink-soft">
                  {fieldLabel(field.name)}
                </th>
                <td className="py-2 pr-3 text-ink">
                  {words(field.value)}
                  {field.contested && <span className="contested ml-2">△ Contested</span>}
                </td>
                <td className="num py-2 pr-3 text-right text-ink-soft">{pct(field.confidence)}</td>
                <td className="num py-2 text-right text-ink-soft">{field.sources}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-1.5 text-[13.5px]">
        <p>
          <span className="field-label inline">Recommended units</span>{" "}
          <span className="text-ink">{dispatch.recommended_units.join(" · ") || "None yet"}</span>
        </p>
        <p>
          <span className="field-label inline">Agencies</span>{" "}
          <span className="text-ink">{dispatch.agencies.join(" · ") || "None yet"}</span>
        </p>
        <p className="cap">Illustrative units, not a real dispatch protocol.</p>
      </div>
    </section>
  );
}
