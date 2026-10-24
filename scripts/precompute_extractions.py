"""Fill the extraction cache for every scenario call (KIRO_PROMPTS.md step I2).

    python scripts/precompute_extractions.py [--workers 4]

Needs ANTHROPIC_API_KEY in .env and DEMO_MODE=cache_first. Calls that are
already cached are skipped, so the script can be re-run after deleting a bad
cache file. Exit code 0 when every call is cached, 2 when some failed.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.pipeline.extract import Extractor  # noqa: E402
from app.sim.replay import list_scenarios, load_scenario  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=4, help="parallel API calls (default 4)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = get_settings()
    if settings.demo_mode == "offline":
        print("DEMO_MODE=offline: refusing to call the API. Set DEMO_MODE=cache_first.")
        return 1
    if not settings.anthropic_api_key:
        print("ANTHROPIC_API_KEY is not set (add it to .env).")
        return 1
    print(f"Model: {settings.claude_model_extract}", flush=True)

    extractor = Extractor()
    jobs = [
        (scenario_id, item)
        for scenario_id in list_scenarios()
        for item in load_scenario(scenario_id).calls
    ]
    counts: Counter[str] = Counter()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(extractor.precompute, item.call): (sid, item) for sid, item in jobs}
        for future in as_completed(futures):
            scenario_id, item = futures[future]
            try:
                outcome = future.result()
            except Exception as exc:  # noqa: BLE001 - report and keep going
                outcome = "failed"
                print(f"{scenario_id}/{item.scenario_call_id}: error {type(exc).__name__}: {exc}", flush=True)
            counts[outcome] += 1
            print(f"{scenario_id}/{item.scenario_call_id}: {outcome}", flush=True)

    print(f"done: cached={counts['cached']} extracted={counts['extracted']} failed={counts['failed']}", flush=True)
    return 0 if counts["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
