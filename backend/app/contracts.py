"""Nexus911 data contracts.

Single source of truth for every shape that crosses a module or process
boundary. Mirrors README.md -> "Data contracts". ``frontend/src/api/types.ts``
mirrors this file field for field.

Nothing in here may import from another ``app.*`` module: contracts sit at the
bottom of the dependency graph so every other package can depend on them
without risking an import cycle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums (Literal aliases so the JSON schema and the TypeScript unions match)
# ---------------------------------------------------------------------------

IncidentType = Literal[
    "shooting",
    "stabbing",
    "robbery",
    "assault",
    "medical",
    "fire",
    "vehicle_crash",
    "disturbance",
    "suspicious_activity",
    "other",
]
CallerRole = Literal["official", "victim", "witness", "bystander", "child", "unknown"]
Channel = Literal["voice", "text"]
Band = Literal["auto", "suggest", "new", "confirmed"]
ClaimStatus = Literal["verified", "pending_verification", "rejected"]
LocationKind = Literal["highway", "landmark", "intersection", "street", "device", "unknown"]
LeadStatus = Literal["suggested", "open", "assigned", "cleared"]
OverrideReason = Literal[
    "new_weapon",
    "new_injury",
    "injury_increase",
    "new_location",
    "new_hazard",
    "new_incident",
]
EventType = Literal[
    "call.processed",
    "incident.updated",
    "link.changed",
    "lead.updated",
    "settings.updated",
    "sim.status",
    "agent.escalated",
]
Actor = Literal["system", "operator", "officer"]
AgentAction = Literal["ask", "escalate", "complete"]

INCIDENT_TYPES: tuple[str, ...] = get_args(IncidentType)
CALLER_ROLES: tuple[str, ...] = get_args(CallerRole)
LOCATION_KINDS: tuple[str, ...] = get_args(LocationKind)
BANDS: tuple[str, ...] = get_args(Band)

# ---------------------------------------------------------------------------
# Closed claim vocabulary (README -> "1. Extract")
# ---------------------------------------------------------------------------

SUBJECTS: tuple[str, ...] = (
    "suspect",
    "suspect_2",
    "vehicle",
    "vehicle_2",
    "victim",
    "scene",
)

ATTRIBUTES: tuple[str, ...] = (
    "upper_clothing_color",
    "upper_clothing_type",
    "lower_clothing",
    "hair",
    "build",
    "height",
    "age_range",
    "sex",
    "weapon",
    "direction_of_travel",
    "suspect_location",
    "vehicle_make",
    "vehicle_model",
    "vehicle_color",
    "vehicle_plate",
    "vehicle_type",
    "injury_count",
    "victim_condition",
    "people_count",
    "hazard",
)

#: Attributes that change as an event unfolds. Excluded from entity matching
#: and subject to recency decay when weighed.
MUTABLE_ATTRIBUTES: frozenset[str] = frozenset({"suspect_location", "direction_of_travel"})

#: Attributes witnesses rarely get wrong. A mismatch here is strong evidence of
#: a different event, so it scores 0.0 instead of the perceptual 0.5.
IDENTIFYING_ATTRIBUTES: frozenset[str] = frozenset(
    {"sex", "weapon", "vehicle_make", "vehicle_model", "vehicle_type", "vehicle_plate"}
)


def is_identifying(attribute: str) -> bool:
    """True when a value mismatch on ``attribute`` should score 0.0."""
    return attribute in IDENTIFYING_ATTRIBUTES


def is_perceptual(attribute: str) -> bool:
    """True when witnesses plausibly disagree on ``attribute`` (scores 0.5)."""
    return attribute not in IDENTIFYING_ATTRIBUTES and attribute not in MUTABLE_ATTRIBUTES


#: Human-readable labels used by ask-next and briefing prompts.
ATTRIBUTE_LABELS: dict[str, str] = {
    "upper_clothing_color": "their jacket or top",
    "upper_clothing_type": "what they are wearing on top",
    "lower_clothing": "their pants",
    "hair": "their hair",
    "build": "their build",
    "height": "their height",
    "age_range": "their age",
    "sex": "whether they are male or female",
    "weapon": "anything they were carrying",
    "direction_of_travel": "which way they went",
    "suspect_location": "where they are now",
    "vehicle_make": "the vehicle's make",
    "vehicle_model": "the vehicle's model",
    "vehicle_color": "the vehicle's color",
    "vehicle_plate": "the licence plate",
    "vehicle_type": "the kind of vehicle",
    "injury_count": "how many people are hurt",
    "victim_condition": "how the injured person is doing",
    "people_count": "how many people are involved",
    "hazard": "any fire, smoke or other danger",
}


def attribute_label(attribute: str) -> str:
    """Plain-English label for ``attribute``, for operator-facing prompts."""
    return ATTRIBUTE_LABELS.get(attribute, attribute.replace("_", " "))


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

Probability = Annotated[float, Field(ge=0.0, le=1.0)]
Priority = Annotated[int, Field(ge=0, le=100)]


class Contract(BaseModel):
    """Base for every contract model.

    ``extra="forbid"`` makes a typo in a payload a loud 422 instead of a field
    that silently does nothing.
    """

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------


class Flags(Contract):
    """Boolean risk markers. Set true only when the caller stated them."""

    weapon_present: bool = False
    injuries_reported: bool = False
    not_breathing: bool = False
    fire_or_smoke: bool = False
    trapped: bool = False
    child_involved: bool = False

    def merged_with(self, other: Flags) -> Flags:
        """Logical OR of two flag sets (used to roll calls up to an incident)."""
        return Flags(
            weapon_present=self.weapon_present or other.weapon_present,
            injuries_reported=self.injuries_reported or other.injuries_reported,
            not_breathing=self.not_breathing or other.not_breathing,
            fire_or_smoke=self.fire_or_smoke or other.fire_or_smoke,
            trapped=self.trapped or other.trapped,
            child_involved=self.child_involved or other.child_involved,
        )

    def any_set(self) -> bool:
        return any(self.model_dump().values())


class CallIn(Contract):
    """One inbound 911 call. The only payload ``POST /api/calls`` accepts."""

    transcript: str = Field(min_length=1)
    channel: Channel = "voice"
    received_at: datetime
    caller_hash: str = Field(min_length=1, description="Hashed number; repeat-caller detection only.")
    caller_role_hint: CallerRole | None = None
    device_lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    device_lng: float | None = Field(default=None, ge=-180.0, le=180.0)
    psap_id: str = "boston-ecc"
    transferred_from: str | None = None
    scenario_id: str | None = None

    # Evaluation only. The pipeline never reads these.
    truth_incident: str | None = None
    truth_new_info: bool | None = None

    def device_coords(self) -> tuple[float, float] | None:
        """Device location as a pair, or None when either half is missing."""
        if self.device_lat is None or self.device_lng is None:
            return None
        return (self.device_lat, self.device_lng)


# ---------------------------------------------------------------------------
# Extraction (LLM output)
# ---------------------------------------------------------------------------


class LocationMention(Contract):
    """Location words as the caller said them, before resolution."""

    street: str | None = None
    cross_street: str | None = None
    town: str | None = None
    landmark: str | None = None
    highway_route: str | None = None
    highway_direction: str | None = None
    highway_exit: str | None = None
    exit_is_old: bool | None = None
    mile_marker: float | None = None
    raw: str = ""

    def is_empty(self) -> bool:
        """True when the caller gave nothing to resolve."""
        return not any(
            (
                self.street,
                self.cross_street,
                self.town,
                self.landmark,
                self.highway_route,
                self.highway_exit,
                self.mile_marker is not None,
            )
        )


class ExtractedClaim(Contract):
    """One fact a caller stated, with the verbatim span that supports it."""

    subject: str
    attribute: str
    value: str
    quote: str
    first_hand: bool = True
    confidence: Probability = 1.0

    @property
    def key(self) -> tuple[str, str]:
        """The ``(subject, attribute)`` pair this claim speaks to."""
        return (self.subject, self.attribute)

    def in_vocabulary(self) -> bool:
        return self.subject in SUBJECTS and self.attribute in ATTRIBUTES


class Extraction(Contract):
    """Everything the model read out of one transcript."""

    language: str = "en"
    incident_type: IncidentType = "other"
    caller_role: CallerRole = "unknown"
    flags: Flags = Field(default_factory=Flags)
    location: LocationMention = Field(default_factory=LocationMention)
    claims: list[ExtractedClaim] = Field(default_factory=list)
    summary: str = ""

    @field_validator("claims", mode="after")
    @classmethod
    def _drop_out_of_vocabulary(cls, claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
        """Discard claims outside the closed vocabulary.

        Fail-open: one off-vocabulary claim must not invalidate a whole call.
        """
        return [c for c in claims if c.in_vocabulary() and c.value.strip()]

    @field_validator("language", mode="after")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        code = value.strip().lower()[:5]
        return code or "en"


# ---------------------------------------------------------------------------
# Graph entities
# ---------------------------------------------------------------------------


class Claim(Contract):
    """A stored claim: an ``ExtractedClaim`` plus provenance and weight."""

    id: str
    call_id: str
    incident_id: str | None = None
    subject: str
    attribute: str
    value: str
    quote: str
    first_hand: bool = True
    confidence: Probability = 1.0
    status: ClaimStatus = "verified"
    weight: float = Field(default=0.0, ge=0.0)
    provisional: bool = False
    created_at: datetime

    @property
    def key(self) -> tuple[str, str]:
        return (self.subject, self.attribute)

    def counts_toward_consensus(self) -> bool:
        """Rejected and provisional claims are excluded from consensus."""
        return self.status != "rejected" and not self.provisional


class ResolvedLocation(Contract):
    """Output of the Massachusetts resolver."""

    lat: float | None = None
    lng: float | None = None
    h3: str | None = None
    kind: LocationKind = "unknown"
    label: str = "Unknown location"
    town: str | None = None
    confidence: Probability = 0.0
    ambiguous: bool = False
    candidates: list[str] = Field(default_factory=list)
    agency_hint: str | None = None

    def coords(self) -> tuple[float, float] | None:
        if self.lat is None or self.lng is None:
            return None
        return (self.lat, self.lng)

    def is_resolved(self) -> bool:
        return self.kind != "unknown" and self.coords() is not None


class Agency(Contract):
    """A responding agency."""

    id: str
    name: str
    kind: Literal["local_pd", "state_police", "mbta_police", "campus_police", "fire", "ems"]
    town: str | None = None


# ---------------------------------------------------------------------------
# Linking
# ---------------------------------------------------------------------------


class LinkComponents(Contract):
    """Per-component link scores. ``None`` means the component was unavailable
    for this call and was dropped from the weighted mean."""

    geo: float | None = None
    time: float | None = None
    type: float | None = None
    entity: float | None = None

    def available(self) -> dict[str, float]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class LinkDecision(Contract):
    """Why a call was attached to an incident, or why it was not."""

    call_id: str
    incident_id: str
    p_same: Probability = 0.0
    band: Band = "new"
    components: LinkComponents = Field(default_factory=LinkComponents)
    gates: list[str] = Field(default_factory=list)
    decided_by: Actor = "system"

    def is_attached(self) -> bool:
        """True when the call's claims belong to an existing incident."""
        return self.band in ("auto", "suggest", "confirmed")

    def is_provisional(self) -> bool:
        """Suggested links are attached but kept out of consensus."""
        return self.band == "suggest"


# ---------------------------------------------------------------------------
# Consensus and queue
# ---------------------------------------------------------------------------


class ValueShare(Contract):
    """One candidate value for an attribute, with its weighted share."""

    value: str
    share: Probability
    sources: int = Field(ge=0)
    first_hand_sources: int = Field(ge=0)


class AttributeConsensus(Contract):
    """Every value reported for one ``(subject, attribute)``, never just the winner."""

    subject: str
    attribute: str
    contested: bool = False
    values: list[ValueShare] = Field(default_factory=list)

    def top(self) -> ValueShare | None:
        return self.values[0] if self.values else None


class QueueItem(Contract):
    """One row in the operator queue."""

    call_id: str
    incident_id: str
    received_at: datetime
    priority: Priority = 0
    band: Band = "new"
    p_same: Probability = 0.0
    novelty: Probability = 1.0
    severity: Probability = 0.0
    new_info: bool = False
    override_reasons: list[OverrideReason] = Field(default_factory=list)
    summary: str = ""
    language: str = "en"
    channel: Channel = "voice"
    caller_role: CallerRole = "unknown"
    location_label: str = ""


# ---------------------------------------------------------------------------
# Incidents and dispatch
# ---------------------------------------------------------------------------


class IncidentSummary(Contract):
    """Incident header, as shown in lists and on the map."""

    id: str
    type: IncidentType = "other"
    severity: Probability = 0.0
    status: Literal["open", "closed"] = "open"
    location_label: str = ""
    lat: float | None = None
    lng: float | None = None
    call_count: int = Field(default=0, ge=0)
    first_seen: datetime
    last_seen: datetime
    top_priority: Priority = 0
    dispatch_ready_at: datetime | None = None


class DispatchField(Contract):
    """One line of the dispatch package."""

    name: str
    value: str
    confidence: Probability = 0.0
    sources: int = Field(default=0, ge=0)
    contested: bool = False


class DispatchPackage(Contract):
    """What responders receive. Unit recommendations are illustrative."""

    fields: list[DispatchField] = Field(default_factory=list)
    recommended_units: list[str] = Field(default_factory=list)
    agencies: list[str] = Field(default_factory=list)
    rule_id: str = "default"
    illustrative: bool = True


class Lead(Contract):
    """A trackable follow-up derived from claims."""

    id: str
    incident_id: str
    description: str
    status: LeadStatus = "suggested"
    assigned_unit: str | None = None
    source_claim_ids: list[str] = Field(default_factory=list)


class Contradiction(Contract):
    """Same key, different values, from different callers."""

    subject: str
    attribute: str
    values: list[str] = Field(default_factory=list)


class TransferRecord(Contract):
    """Cross-PSAP handoff context for one call."""

    call_id: str
    from_psap: str
    to_psap: str


class TimelineEntry(Contract):
    """One dot on the incident timeline."""

    t: datetime
    event: str
    call_id: str | None = None


class IncidentDetail(Contract):
    """Full incident read model backing the operator and officer panels."""

    incident: IncidentSummary
    location: ResolvedLocation
    calls: list[QueueItem] = Field(default_factory=list)
    consensus: list[AttributeConsensus] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    dispatch: DispatchPackage = Field(default_factory=DispatchPackage)
    leads: list[Lead] = Field(default_factory=list)
    transfers: list[TransferRecord] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)


class CallDetail(Contract):
    """Everything known about one call."""

    call: CallIn
    extraction: Extraction
    claims: list[Claim] = Field(default_factory=list)
    location: ResolvedLocation
    link: LinkDecision
    queue_item: QueueItem


class ProcessResult(Contract):
    """Return value of the call pipeline."""

    incident_id: str
    queue_item: QueueItem
    link: LinkDecision
    claims: list[Claim] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM-backed read models
# ---------------------------------------------------------------------------


class AskNext(Contract):
    """Prompts a call-taker can read aloud."""

    confirm_line: str = ""
    questions: list[str] = Field(default_factory=list)


class Briefing(Contract):
    """Three-line officer briefing."""

    known: str = ""
    disputed: str = ""
    open: str = ""


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


class GuardStats(Contract):
    """Quote-grounding outcomes across every claim."""

    verified: int = 0
    pending_verification: int = 0
    rejected: int = 0


class Metrics(Contract):
    """Live load, as shown on the sim page."""

    calls: int = 0
    incidents: int = 0
    collapse_rate: float = 0.0
    bands: dict[str, int] = Field(default_factory=dict)
    new_info_calls: int = 0
    guard: GuardStats = Field(default_factory=GuardStats)


DEFAULT_RADIUS_M: dict[str, int] = {
    "highway": 2000,
    "landmark": 400,
    "intersection": 400,
    "street": 600,
    "device": 600,
}


class RuntimeSettings(Contract):
    """Operator-tunable knobs. Changes apply to calls processed afterwards."""

    auto_link_threshold: Probability = 0.85
    suggest_threshold: Probability = 0.50
    time_window_min: int = Field(default=30, gt=0)
    mass_event_mode: bool = False
    radius_m: dict[str, int] = Field(default_factory=lambda: dict(DEFAULT_RADIUS_M))

    def effective_auto_threshold(self) -> float:
        """Mass-event mode raises the auto-link bar to 0.90."""
        return max(self.auto_link_threshold, 0.90) if self.mass_event_mode else self.auto_link_threshold

    def effective_window_min(self) -> int:
        """Mass-event mode doubles the time window."""
        return self.time_window_min * 2 if self.mass_event_mode else self.time_window_min

    def radius_for(self, kind: str) -> int:
        """Search radius in metres for a resolved location kind."""
        return self.radius_m.get(kind, DEFAULT_RADIUS_M.get(kind, 600))


class RuntimeSettingsPatch(Contract):
    """Partial update for ``PUT /api/settings``."""

    auto_link_threshold: Probability | None = None
    suggest_threshold: Probability | None = None
    time_window_min: int | None = Field(default=None, gt=0)
    mass_event_mode: bool | None = None
    radius_m: dict[str, int] | None = None

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class SimStatus(Contract):
    """Replay clock and progress."""

    scenario_id: str | None = None
    running: bool = False
    speed: float = 1.0
    t_offset_s: float = 0.0
    sim_time: datetime | None = None
    calls_sent: int = 0
    calls_total: int = 0


class AuditEvent(Contract):
    """One immutable record of a decision."""

    id: str
    ts: datetime
    actor: Actor
    action: str
    call_id: str | None = None
    incident_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class DashboardEvent(Contract):
    """One message on ``/ws/dashboard``."""

    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: datetime


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class LeadCreate(Contract):
    incident_id: str
    description: str = Field(min_length=1)
    source_claim_ids: list[str] = Field(default_factory=list)


class LeadUpdate(Contract):
    status: LeadStatus | None = None
    assigned_unit: str | None = None


class SimStartRequest(Contract):
    scenario_id: str
    speed: float = Field(default=1.0, gt=0, le=100)


class AgentTurnRequest(Contract):
    session_id: str
    incident_id: str
    caller_text: str


class AgentTurnResponse(Contract):
    action: AgentAction
    message: str = ""
    reasons: list[str] = Field(default_factory=list)
