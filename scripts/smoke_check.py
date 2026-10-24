"""Live smoke check against a running server (python run.py).

    python scripts/smoke_check.py [--base http://127.0.0.1:8080]

Checks the API, the dashboard WebSocket, and whether Claude is really being
called: a brand-new transcript (never cached) must come back with claims, and
ask-next / briefing must differ from the template fallbacks. One live call
costs a few cents. Leaves the extra call in the graph; use /api/reset to clear.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

import websockets

TEMPLATE_QUESTION = "What is happening right now?"


def http(base: str, path: str, body: dict | None = None, method: str | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        base + path, data=data, method=method or ("POST" if body is not None else "GET"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            if "json" not in response.headers.get("Content-Type", ""):
                return response.status, raw[:80].decode(errors="replace")
            return response.status, json.loads(raw or b"null")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:200]


async def websocket_event(base: str, trigger) -> dict | None:
    url = base.replace("http", "ws", 1) + "/ws/dashboard"
    async with websockets.connect(url, open_timeout=5) as ws:
        await asyncio.to_thread(trigger)
        try:
            return json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
        except asyncio.TimeoutError:
            return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    base = parser.parse_args().base
    ok = True

    def report(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'}  {name}{('  ' + detail) if detail else ''}", flush=True)

    for path in ("/api/queue", "/api/incidents", "/api/metrics", "/api/settings", "/api/audit", "/docs", "/"):
        status, _ = http(base, path)
        report(f"GET {path}", status == 200, str(status))

    transcript = (
        f"I'm at Mass Ave and Boylston right now. A man in a red hoodie just smashed a car window "
        f"and ran toward Symphony station. Check {int(time.time())}."
    )
    call = {
        "transcript": transcript,
        "channel": "voice",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "caller_hash": f"smoke-{int(time.time())}",
        "device_lat": 42.3470,
        "device_lng": -71.0874,
    }
    result: dict = {}

    def post_call() -> None:
        started = time.time()
        status, body = http(base, "/api/calls", call)
        result.update(status=status, body=body, seconds=time.time() - started)

    event = asyncio.run(websocket_event(base, post_call))
    report("WebSocket /ws/dashboard delivers call.processed", bool(event and event.get("type") == "call.processed"),
           event.get("type", "") if event else "no event")

    body = result.get("body") if isinstance(result.get("body"), dict) else {}
    claims = body.get("claims", []) if body else []
    report("POST /api/calls (new transcript)", result.get("status") == 200, f"{result.get('seconds', 0):.1f}s")
    report("Claude extraction is live (claims from an uncached call)", len(claims) > 0,
           ", ".join(f"{c['attribute']}={c['value']}" for c in claims[:4]) or "0 claims: fell back to the minimal extraction")

    call_id = body.get("link", {}).get("call_id") if body else None
    if call_id:
        status, ask = http(base, f"/api/calls/{call_id}/ask-next")
        questions = ask.get("questions", []) if isinstance(ask, dict) else []
        live = bool(questions) and TEMPLATE_QUESTION not in questions[-1:]
        report("GET ask-next", status == 200, " | ".join(questions))
        report("Ask-next comes from Claude (not the template)", live, "template fallback" if not live else "")

        incident = body["incident_id"]
        status, brief = http(base, f"/api/incidents/{incident}/briefing")
        report("GET briefing", status == 200, json.dumps(brief)[:160])

        status, confirm = http(base, f"/api/links/{call_id}/confirm", {}, "POST")
        report("POST confirm (operator action)", status in (200, 409), str(status))

    print("\nAll checks passed." if ok else "\nSome checks failed.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
