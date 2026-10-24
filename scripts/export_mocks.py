"""Write frontend/src/mocks/*.json from a real in-process replay (KIRO_PROMPTS.md step 0.7).

    python scripts/export_mocks.py

Replays the three scenarios offline (cached extractions), confirms one call and
adds one officer lead, then dumps the read models the console fetches. Because
the mocks come from the real API models, they always match contracts.py;
backend/tests/test_frontend_mocks.py checks that they still validate.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["DEMO_MODE"] = "offline"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_runtime  # noqa: E402
from app.context import AppContext  # noqa: E402
from app.contracts import IncidentDetail, SimStatus, TransferRecord  # noqa: E402
from app.sim.replay import load_scenario  # noqa: E402

OUT = ROOT / "frontend" / "src" / "mocks"
SCENARIOS = ("mass_ave_robbery", "pike_crash", "washington_st")
# Covers every band, a NEW INFO new_weapon call, and Spanish and Portuguese callers.
QUEUE_CALLS = ("c12", "c10", "c01", "w03", "c02", "c04", "p06", "p03")


def dump(name: str, payload: object) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def as_json(model) -> object:
    return model.model_dump(mode="json")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = AppContext.create()
    results = {}
    for scenario_id in SCENARIOS:
        for item in load_scenario(scenario_id).calls:
            results[item.scenario_call_id] = ctx.runner.process_call(item.call)

    ctx.runner.confirm_link(results["c02"].link.call_id)
    robbery = results["c01"].incident_id
    ctx.views.create_lead(robbery, "Canvass Newbury St for camera footage", [])

    wanted = {results[cid].link.call_id for cid in QUEUE_CALLS}
    queue = [item for item in ctx.views.queue() if item.call_id in wanted]
    dump("queue", [as_json(item) for item in queue])

    summaries = {summary.id: summary for summary in ctx.views.incidents()}
    dump("incidents", [as_json(summaries[results[cid].incident_id]) for cid in ("c01", "c12", "p01")])

    detail = ctx.views.incident_detail(robbery)
    # The robbery has no transfer in the scenario; one is added so the banner renders in mock mode.
    transfer = TransferRecord(call_id=results["c08"].link.call_id, from_psap="cambridge-ecc", to_psap="boston-ecc")
    detail = IncidentDetail.model_validate({**detail.model_dump(), "transfers": [transfer.model_dump()]})
    dump("incident", as_json(detail))

    knife = ctx.views.call_detail(results["c10"].link.call_id)
    dump("call", as_json(knife))
    dump("explain", as_json(ctx.views.explain(results["c12"].link.call_id)))

    ambiguous = ctx.views.call_detail(results["w03"].link.call_id)
    dump("ask-next", as_json(ctx.assist.ask_next(ambiguous, ctx.views.incident_detail(ambiguous.link.incident_id))))
    dump("briefing", as_json(ctx.assist.briefing(ctx.views.incident_detail(robbery))))
    dump("metrics", as_json(ctx.views.metrics()))
    dump("settings", as_json(get_runtime()))
    c08 = results["c08"].queue_item
    dump(
        "sim-status",
        as_json(
            SimStatus(
                scenario_id="mass_ave_robbery",
                running=True,
                speed=10,
                t_offset_s=220,
                sim_time=c08.received_at,
                calls_sent=8,
                calls_total=12,
            )
        ),
    )

    contested = [c.attribute for c in detail.consensus if c.contested]
    bands = sorted({item.band for item in queue})
    print(f"wrote {len(list(OUT.glob('*.json')))} mocks; queue bands {bands}; contested {contested}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
