"""Replay every scenario in-process with cached extractions and print metrics.

    python scripts/evaluate.py

Runs with DEMO_MODE=offline, so it never calls the API: a call without a cached
extraction falls back to the minimal extraction and is counted as a cache miss.
Prints the README "Evaluation" table as markdown, then a per-call breakdown.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["DEMO_MODE"] = "offline"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.sim.evaluation import evaluate, markdown_table, run_scenario  # noqa: E402
from app.sim.replay import list_scenarios  # noqa: E402


def main() -> int:
    runs = [run_scenario(scenario_id) for scenario_id in list_scenarios()]
    result = evaluate(runs)
    print(markdown_table(result))
    print()
    print(f"Scenarios: {', '.join(result['scenarios'])}. Cache misses: {result['cache_misses']}.")
    print()
    print("| Scenario | Call | Truth | Incident | Band | Priority | NEW INFO | Reasons |")
    print("|---|---|---|---|---|---|---|---|")
    for run in runs:
        for r in run.records:
            truth = f"{r.truth_incident}{' *' if r.truth_new_info else ''}"
            reasons = ", ".join(r.override_reasons) or "-"
            print(
                f"| {r.scenario_id} | {r.scenario_call_id} | {truth} | {r.incident_id} | {r.band} "
                f"| {r.priority} | {'yes' if r.new_info else 'no'} | {reasons} |"
            )
    print()
    print("Truth marked * = truth_new_info. Incident ids restart per scenario (one fresh graph each).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
