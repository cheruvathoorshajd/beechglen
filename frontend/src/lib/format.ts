import type { Band, OverrideReason } from "../api/types";

/** NEW INFO reasons in words (style guide: never color alone). */
export const REASON_WORDS: Record<OverrideReason, string> = {
  new_weapon: "new weapon",
  new_injury: "new injury",
  injury_increase: "more injured",
  new_location: "new location",
  new_hazard: "new hazard",
  new_incident: "new incident",
};

/** Link gates in plain words for the Why linked? modal. */
export const GATE_WORDS: Record<string, string> = {
  incompatible_type_cap: "Different emergency types are never merged",
  low_location_confidence: "An unresolved location is never auto-linked; an operator confirms it",
  operator_split: "Split into its own incident by an operator",
};

export const BAND_LABEL: Record<Band, string> = {
  auto: "Auto",
  suggest: "Suggest",
  new: "New",
  confirmed: "Confirmed",
};

export const BAND_MEANING: Record<Band, string> = {
  auto: "Linked on its own",
  suggest: "Waits for you",
  new: "Started an incident",
  confirmed: "Approved by an operator",
};

/** Link score weights (README "4. Link"). */
export const LINK_WEIGHTS = { geo: 0.35, time: 0.25, type: 0.2, entity: 0.2 } as const;

/** Critical: severity 0.9 or above (shooting, stabbing, fire, weapon, trapped, not breathing). */
export const CRITICAL_SEVERITY = 0.9;
export const isCritical = (severity: number) => severity >= CRITICAL_SEVERITY;

export type PriorityTone = "high" | "mid" | "low";
export function priorityTone(priority: number): PriorityTone {
  if (priority >= 80) return "high";
  if (priority >= 50) return "mid";
  return "low";
}

export const words = (value: string) => value.replace(/[_.]+/g, " ");

export function sentence(value: string) {
  const text = words(value);
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Dispatch field names: "suspect.upper_clothing_color" -> "Suspect · upper clothing color". */
export function fieldLabel(name: string) {
  const [head, ...rest] = name.split(".");
  return rest.length ? `${sentence(head)} · ${words(rest.join(" "))}` : sentence(head);
}

export function attributeLabel(subject: string, attribute: string) {
  return `${sentence(subject)} · ${words(attribute)}`;
}

/** "T+mm:ss" from an ISO time relative to an origin (the first call). */
export function tPlus(at: string | null | undefined, origin: string | null | undefined) {
  if (!at || !origin) return "T+--:--";
  return tPlusSeconds((Date.parse(at) - Date.parse(origin)) / 1000);
}

export function tPlusSeconds(seconds: number) {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `T+${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export const pct = (value: number) => `${Math.round(value * 100)}%`;
