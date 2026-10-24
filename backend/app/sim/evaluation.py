"""Batch replay and the README "Evaluation" metrics.

Used by ``scripts/evaluate.py`` and the scenario acceptance tests. Calls are
processed in order without sleeping; extraction is whatever the context's
extractor returns (cache only when DEMO_MODE=offline).

Metrics (README -> "Evaluation"):

* Pairwise clustering precision, recall and F1 against ``truth_incident``
* New-incident recall: share of ground-truth incidents whose first call got
  band ``new`` or priority >= 80 (target 100%)
* New-info escalation recall: share of ``truth_new_info`` calls with NEW INFO
* Duplicate collapse rate: 1 - incidents / calls
* Guard stats: verified, pending and rejected claims
* Workload proxy: calls handled as confirm-and-add (``auto``) vs full intake
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from itertools import combinations

from app.context import AppContext
from app.paths import SCENARIO_DIR, EXTRACTION_CACHE_DIR
from app.pipeline.extract import cache_path
from app.sim.replay import load_scenario

NEW_INCIDENT_PRIORITY = 80


@dataclass(frozen=True)
class CallRecord:
    scenario_id: str
    scenario_call_id: str
    t_offset_s: float
    truth_incident: str | None
    truth_new_info: bool | None
    call_id: str
    incident_id: str
    band: str
    priority: int
    new_info: bool
    override_reasons: tuple[str, ...]
    cached: bool


@dataclass
class ScenarioRun:
    scenario_id: str
    ctx: AppContext
    records: list[CallRecord] = field(default_factory=list)

    def by_scenario_id(self) -> dict[str, CallRecord]:
        return {record.scenario_call_id: record for record in self.records}


def run_scenario(
    scenario_id: str,
    ctx: AppContext | None = None,
    *,
    context_factory: Callable[[], AppContext] = AppContext.create,
) -> ScenarioRun:
    """Process every call of a scenario in order, in-process, without sleeping."""
    scenario = load_scenario(scenario_id, SCENARIO_DIR)
    context = ctx or context_factory()
    run = ScenarioRun(scenario_id=scenario_id, ctx=context)
    for item in scenario.calls:
        result = context.runner.process_call(item.call)
        run.records.append(
            CallRecord(
                scenario_id=scenario_id,
                scenario_call_id=item.scenario_call_id,
                t_offset_s=item.t_offset_s,
                truth_incident=item.call.truth_incident,
                truth_new_info=item.call.truth_new_info,
                call_id=result.link.call_id,
                incident_id=result.incident_id,
                band=result.link.band,
                priority=result.queue_item.priority,
                new_info=result.queue_item.new_info,
                override_reasons=tuple(result.queue_item.override_reasons),
                cached=cache_path(item.call.transcript, EXTRACTION_CACHE_DIR).is_file(),
            )
        )
    return run


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def pairwise_counts(records: Sequence[CallRecord]) -> tuple[int, int, int]:
    """True positives, false positives and false negatives over call pairs."""
    tp = fp = fn = 0
    for a, b in combinations(records, 2):
        same_truth = a.truth_incident == b.truth_incident
        same_pred = a.incident_id == b.incident_id
        if same_truth and same_pred:
            tp += 1
        elif same_pred:
            fp += 1
        elif same_truth:
            fn += 1
    return tp, fp, fn


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def evaluate(runs: Iterable[ScenarioRun]) -> dict[str, object]:
    runs = list(runs)
    tp = fp = fn = 0
    first_total = first_hit = 0
    info_total = info_hit = 0
    calls = incidents = auto = 0
    guard = {"verified": 0, "pending_verification": 0, "rejected": 0}
    misses = 0

    for run in runs:
        records = run.records
        a, b, c = pairwise_counts(records)
        tp, fp, fn = tp + a, fp + b, fn + c

        firsts: dict[str, CallRecord] = {}
        for record in sorted(records, key=lambda r: r.t_offset_s):
            if record.truth_incident is not None:
                firsts.setdefault(record.truth_incident, record)
        first_total += len(firsts)
        first_hit += sum(1 for r in firsts.values() if r.band == "new" or r.priority >= NEW_INCIDENT_PRIORITY)

        flagged = [r for r in records if r.truth_new_info]
        info_total += len(flagged)
        info_hit += sum(1 for r in flagged if r.new_info)

        metrics = run.ctx.views.metrics()
        calls += metrics.calls
        incidents += metrics.incidents
        auto += metrics.bands.get("auto", 0)
        guard["verified"] += metrics.guard.verified
        guard["pending_verification"] += metrics.guard.pending_verification
        guard["rejected"] += metrics.guard.rejected
        misses += sum(1 for r in records if not r.cached)

    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall)
        else None
    )
    return {
        "scenarios": [run.scenario_id for run in runs],
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "new_incident_recall": _ratio(first_hit, first_total),
        "new_incident_counts": (first_hit, first_total),
        "new_info_recall": _ratio(info_hit, info_total),
        "new_info_counts": (info_hit, info_total),
        "collapse_rate": 1 - incidents / calls if calls else None,
        "calls": calls,
        "incidents": incidents,
        "guard": guard,
        "auto": auto,
        "full_intake": calls - auto,
        "cache_misses": misses,
    }


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.0f}%"


def _num(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.2f}"


def markdown_table(result: dict[str, object]) -> str:
    guard = result["guard"]
    hit, total = result["new_incident_counts"]
    info_hit, info_total = result["new_info_counts"]
    rows = [
        ("Clustering precision / recall / F1", f"{_num(result['precision'])} / {_num(result['recall'])} / {_num(result['f1'])}"),
        ("New-incident recall", f"{_pct(result['new_incident_recall'])} ({hit}/{total})"),
        ("New-info escalation recall", f"{_pct(result['new_info_recall'])} ({info_hit}/{info_total})"),
        ("Duplicate collapse rate", f"{_pct(result['collapse_rate'])} ({result['calls']} calls → {result['incidents']} incidents)"),
        ("Claims verified / pending / rejected", f"{guard['verified']} / {guard['pending_verification']} / {guard['rejected']}"),
        ("Workload proxy: auto (confirm-and-add) / full intake", f"{result['auto']} / {result['full_intake']}"),
    ]
    lines = ["| Metric | Result |", "|---|---|", *(f"| {name} | {value} |" for name, value in rows)]
    return "\n".join(lines)
