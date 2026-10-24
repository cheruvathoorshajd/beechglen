"""Claim weighting, per-attribute consensus and contradictions.

Implements README -> "5. Weigh". Pure: the caller passes plain
:class:`ClaimEvidence` snapshots and a reference time, so every number here is
testable without a graph.

    w = role x source x recency x independence x verification

Consensus keeps every value with its share, never just the winner, so a
minority account stays visible. Role priors change claim weight only; they
never touch call priority.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.contracts import (
    ATTRIBUTES,
    MUTABLE_ATTRIBUTES,
    SUBJECTS,
    AttributeConsensus,
    CallerRole,
    ClaimStatus,
    Contradiction,
    ValueShare,
)

ROLE_WEIGHTS: dict[str, float] = {
    "official": 0.95,
    "victim": 0.75,
    "witness": 0.65,
    "bystander": 0.50,
    "child": 0.35,
    "unknown": 0.50,
}
FIRST_HAND_WEIGHT = 1.0
HEARSAY_WEIGHT = 0.5
RECENCY_TAU_MIN = 15.0
REPEAT_CALLER_WEIGHT = 0.3
VERIFICATION_WEIGHTS: dict[str, float] = {
    "verified": 1.0,
    "pending_verification": 0.6,
    "rejected": 0.0,
}

#: Contested when the top share is below this...
CONTESTED_TOP_BELOW = 0.70
#: ...and the runner-up holds at least this much.
CONTESTED_RUNNER_UP_MIN = 0.20

ClaimKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    """One claim plus the call metadata its weight depends on."""

    claim_id: str
    call_id: str
    subject: str
    attribute: str
    value: str
    first_hand: bool
    status: ClaimStatus
    provisional: bool
    caller_role: CallerRole
    received_at: datetime
    repeat_caller: bool

    @property
    def key(self) -> ClaimKey:
        return (self.subject, self.attribute)

    def counts_toward_consensus(self) -> bool:
        """Rejected claims and provisional (suggested-link) claims are excluded."""
        return self.status != "rejected" and not self.provisional


# ---------------------------------------------------------------------------
# Weight factors
# ---------------------------------------------------------------------------


def role_factor(role: str) -> float:
    return ROLE_WEIGHTS.get(role, ROLE_WEIGHTS["unknown"])


def source_factor(first_hand: bool) -> float:
    return FIRST_HAND_WEIGHT if first_hand else HEARSAY_WEIGHT


def recency_factor(attribute: str, received_at: datetime, now: datetime) -> float:
    """Exponential decay for facts that go stale as a suspect moves."""
    if attribute not in MUTABLE_ATTRIBUTES:
        return 1.0
    age_min = max(0.0, (now - received_at).total_seconds() / 60.0)
    return math.exp(-age_min / RECENCY_TAU_MIN)


def independence_factor(repeat_caller: bool) -> float:
    return REPEAT_CALLER_WEIGHT if repeat_caller else 1.0


def verification_factor(status: str) -> float:
    return VERIFICATION_WEIGHTS.get(status, 0.0)


def claim_weight(evidence: ClaimEvidence, now: datetime) -> float:
    """Weight of one claim. Rejected claims weigh 0 and never enter consensus."""
    if evidence.status == "rejected":
        return 0.0
    weight = (
        role_factor(evidence.caller_role)
        * source_factor(evidence.first_hand)
        * recency_factor(evidence.attribute, evidence.received_at, now)
        * independence_factor(evidence.repeat_caller)
        * verification_factor(evidence.status)
    )
    return round(weight, 6)


def repeat_callers(calls: Sequence[tuple[str, str, datetime]]) -> set[str]:
    """Call ids whose caller already called earlier about the same incident.

    ``calls`` holds ``(call_id, caller_hash, received_at)`` in arrival order;
    ties on ``received_at`` keep that order. The first call from a caller
    counts fully; every later one is a repeat.
    """
    ordered = sorted(enumerate(calls), key=lambda item: (item[1][2], item[0]))
    seen: set[str] = set()
    repeats: set[str] = set()
    for _, (call_id, caller_hash, _) in ordered:
        if caller_hash in seen:
            repeats.add(call_id)
        seen.add(caller_hash)
    return repeats


# ---------------------------------------------------------------------------
# Consensus
# ---------------------------------------------------------------------------


def _key_order(key: ClaimKey) -> tuple[int, int, str, str]:
    subject, attribute = key
    s = SUBJECTS.index(subject) if subject in SUBJECTS else len(SUBJECTS)
    a = ATTRIBUTES.index(attribute) if attribute in ATTRIBUTES else len(ATTRIBUTES)
    return (s, a, subject, attribute)


def is_contested(values: Sequence[ValueShare]) -> bool:
    if len(values) < 2:
        return False
    return values[0].share < CONTESTED_TOP_BELOW and values[1].share >= CONTESTED_RUNNER_UP_MIN


def consensus(evidence: Iterable[ClaimEvidence], now: datetime) -> list[AttributeConsensus]:
    """Weighted share of every value for every ``(subject, attribute)``."""
    weights: dict[ClaimKey, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    sources: dict[ClaimKey, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    first_hand: dict[ClaimKey, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for item in evidence:
        if not item.counts_toward_consensus():
            continue
        weight = claim_weight(item, now)
        if weight <= 0.0:
            continue
        weights[item.key][item.value] += weight
        sources[item.key][item.value].add(item.call_id)
        if item.first_hand:
            first_hand[item.key][item.value].add(item.call_id)

    result: list[AttributeConsensus] = []
    for key in sorted(weights, key=_key_order):
        total = sum(weights[key].values())
        shares = [
            ValueShare(
                value=value,
                share=round(weight / total, 4),
                sources=len(sources[key][value]),
                first_hand_sources=len(first_hand[key][value]),
            )
            for value, weight in weights[key].items()
        ]
        shares.sort(key=lambda share: (-share.share, -share.sources, share.value))
        result.append(
            AttributeConsensus(
                subject=key[0],
                attribute=key[1],
                contested=is_contested(shares),
                values=shares,
            )
        )
    return result


def contradictions(
    evidence: Iterable[ClaimEvidence],
    now: datetime,
) -> tuple[list[Contradiction], list[tuple[str, str]]]:
    """Same key, different values, from different calls.

    Returns the contradiction list for the incident view (values ordered by
    total weight) and the claim-id pairs for ``CONTRADICTS`` edges, each pair
    ordered oldest claim first so it is recorded once.
    """
    by_key: dict[ClaimKey, list[ClaimEvidence]] = defaultdict(list)
    for item in evidence:
        if item.counts_toward_consensus():
            by_key[item.key].append(item)

    found: list[Contradiction] = []
    pairs: list[tuple[str, str]] = []
    for key in sorted(by_key, key=_key_order):
        items = sorted(by_key[key], key=lambda e: (e.received_at, e.claim_id))
        key_pairs = [
            (a.claim_id, b.claim_id)
            for index, a in enumerate(items)
            for b in items[index + 1 :]
            if a.value != b.value and a.call_id != b.call_id
        ]
        if not key_pairs:
            continue
        totals: dict[str, float] = defaultdict(float)
        for item in items:
            totals[item.value] += claim_weight(item, now)
        values = sorted(totals, key=lambda value: (-totals[value], value))
        found.append(Contradiction(subject=key[0], attribute=key[1], values=values))
        pairs.extend(key_pairs)
    return found, pairs


def consensus_lookup(entries: Iterable[AttributeConsensus]) -> dict[ClaimKey, AttributeConsensus]:
    """Index consensus entries by ``(subject, attribute)``."""
    return {(entry.subject, entry.attribute): entry for entry in entries}
