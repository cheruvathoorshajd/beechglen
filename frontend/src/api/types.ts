// Mirrors backend/app/contracts.py field for field. contracts.py is the authority.
// Datetimes arrive as ISO 8601 strings.

export type IncidentType =
  | "shooting"
  | "stabbing"
  | "robbery"
  | "assault"
  | "medical"
  | "fire"
  | "vehicle_crash"
  | "disturbance"
  | "suspicious_activity"
  | "other";
export type CallerRole = "official" | "victim" | "witness" | "bystander" | "child" | "unknown";
export type Channel = "voice" | "text";
export type Band = "auto" | "suggest" | "new" | "confirmed";
export type ClaimStatus = "verified" | "pending_verification" | "rejected";
export type LocationKind = "highway" | "landmark" | "intersection" | "street" | "device" | "unknown";
export type LeadStatus = "suggested" | "open" | "assigned" | "cleared";
export type OverrideReason =
  | "new_weapon"
  | "new_injury"
  | "injury_increase"
  | "new_location"
  | "new_hazard"
  | "new_incident";
export type EventType =
  | "call.processed"
  | "incident.updated"
  | "link.changed"
  | "lead.updated"
  | "settings.updated"
  | "sim.status"
  | "agent.escalated";
export type Actor = "system" | "operator" | "officer";
export type AgentAction = "ask" | "escalate" | "complete";

export interface Flags {
  weapon_present: boolean;
  injuries_reported: boolean;
  not_breathing: boolean;
  fire_or_smoke: boolean;
  trapped: boolean;
  child_involved: boolean;
}

export interface CallIn {
  transcript: string;
  channel: Channel;
  received_at: string;
  caller_hash: string;
  caller_role_hint: CallerRole | null;
  device_lat: number | null;
  device_lng: number | null;
  psap_id: string;
  transferred_from: string | null;
  scenario_id: string | null;
  truth_incident: string | null;
  truth_new_info: boolean | null;
}

export interface LocationMention {
  street: string | null;
  cross_street: string | null;
  town: string | null;
  landmark: string | null;
  highway_route: string | null;
  highway_direction: string | null;
  highway_exit: string | null;
  exit_is_old: boolean | null;
  mile_marker: number | null;
  raw: string;
}

export interface ExtractedClaim {
  subject: string;
  attribute: string;
  value: string;
  quote: string;
  first_hand: boolean;
  confidence: number;
}

export interface Extraction {
  language: string;
  incident_type: IncidentType;
  caller_role: CallerRole;
  flags: Flags;
  location: LocationMention;
  claims: ExtractedClaim[];
  summary: string;
}

export interface Claim extends ExtractedClaim {
  id: string;
  call_id: string;
  incident_id: string | null;
  status: ClaimStatus;
  weight: number;
  provisional: boolean;
  created_at: string;
}

export interface ResolvedLocation {
  lat: number | null;
  lng: number | null;
  h3: string | null;
  kind: LocationKind;
  label: string;
  town: string | null;
  confidence: number;
  ambiguous: boolean;
  candidates: string[];
  agency_hint: string | null;
}

export interface LinkComponents {
  geo: number | null;
  time: number | null;
  type: number | null;
  entity: number | null;
}

export interface LinkDecision {
  call_id: string;
  incident_id: string;
  p_same: number;
  band: Band;
  components: LinkComponents;
  gates: string[];
  decided_by: Actor;
}

export interface QueueItem {
  call_id: string;
  incident_id: string;
  received_at: string;
  priority: number;
  band: Band;
  p_same: number;
  novelty: number;
  severity: number;
  new_info: boolean;
  override_reasons: OverrideReason[];
  summary: string;
  language: string;
  channel: Channel;
  caller_role: CallerRole;
  location_label: string;
}

export interface ValueShare {
  value: string;
  share: number;
  sources: number;
  first_hand_sources: number;
}

export interface AttributeConsensus {
  subject: string;
  attribute: string;
  contested: boolean;
  values: ValueShare[];
}

export interface IncidentSummary {
  id: string;
  type: IncidentType;
  severity: number;
  status: "open" | "closed";
  location_label: string;
  lat: number | null;
  lng: number | null;
  call_count: number;
  first_seen: string;
  last_seen: string;
  top_priority: number;
  dispatch_ready_at: string | null;
}

export interface DispatchField {
  name: string;
  value: string;
  confidence: number;
  sources: number;
  contested: boolean;
}

export interface DispatchPackage {
  fields: DispatchField[];
  recommended_units: string[];
  agencies: string[];
  rule_id: string;
  illustrative: boolean;
}

export interface Lead {
  id: string;
  incident_id: string;
  description: string;
  status: LeadStatus;
  assigned_unit: string | null;
  source_claim_ids: string[];
}

export interface Contradiction {
  subject: string;
  attribute: string;
  values: string[];
}

export interface TransferRecord {
  call_id: string;
  from_psap: string;
  to_psap: string;
}

export interface TimelineEntry {
  t: string;
  event: string;
  call_id: string | null;
}

export interface IncidentDetail {
  incident: IncidentSummary;
  location: ResolvedLocation;
  calls: QueueItem[];
  consensus: AttributeConsensus[];
  contradictions: Contradiction[];
  dispatch: DispatchPackage;
  leads: Lead[];
  transfers: TransferRecord[];
  timeline: TimelineEntry[];
}

export interface CallDetail {
  call: CallIn;
  extraction: Extraction;
  claims: Claim[];
  location: ResolvedLocation;
  link: LinkDecision;
  queue_item: QueueItem;
}

export interface ProcessResult {
  incident_id: string;
  queue_item: QueueItem;
  link: LinkDecision;
  claims: Claim[];
}

export interface AskNext {
  confirm_line: string;
  questions: string[];
}

export interface Briefing {
  known: string;
  disputed: string;
  open: string;
}

export interface GuardStats {
  verified: number;
  pending_verification: number;
  rejected: number;
}

export interface Metrics {
  calls: number;
  incidents: number;
  collapse_rate: number;
  bands: Record<string, number>;
  new_info_calls: number;
  guard: GuardStats;
}

export interface RuntimeSettings {
  auto_link_threshold: number;
  suggest_threshold: number;
  time_window_min: number;
  mass_event_mode: boolean;
  radius_m: Record<string, number>;
}

export type RuntimeSettingsPatch = Partial<RuntimeSettings>;

export interface SimStatus {
  scenario_id: string | null;
  running: boolean;
  speed: number;
  t_offset_s: number;
  sim_time: string | null;
  calls_sent: number;
  calls_total: number;
}

export interface AuditEvent {
  id: string;
  ts: string;
  actor: Actor;
  action: string;
  call_id: string | null;
  incident_id: string | null;
  details: Record<string, unknown>;
}

export interface DashboardEvent {
  type: EventType;
  payload: Record<string, unknown>;
  ts: string;
}

export interface LeadCreate {
  incident_id: string;
  description: string;
  source_claim_ids: string[];
}

export interface LeadUpdate {
  status?: LeadStatus | null;
  assigned_unit?: string | null;
}

export interface SimStartRequest {
  scenario_id: string;
  speed: number;
}

export interface AgentTurnRequest {
  session_id: string;
  incident_id: string;
  caller_text: string;
}

export interface AgentTurnResponse {
  action: AgentAction;
  message: string;
  reasons: string[];
}
