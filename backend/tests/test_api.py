"""HTTP and WebSocket API (README -> "API"), over a context with a fake extractor."""

from __future__ import annotations

import json
import re

import pytest
from fakes import FakeExtractor, claim
from fastapi.testclient import TestClient

from app.context import AppContext
from app.contracts import Flags, LocationMention
from app.main import create_app
from app.paths import REPO_ROOT

STORE = LocationMention(street="Mass Ave", cross_street="Boylston")
WASHINGTON = LocationMention(street="Washington Street")


def robbery_call(transcript, seconds, caller, **extra):
    body = {
        "transcript": transcript,
        "channel": "voice",
        "received_at": f"2026-10-24T14:{seconds // 60:02d}:{seconds % 60:02d}-04:00",
        "caller_hash": caller,
        "device_lat": 42.3470,
        "device_lng": -71.0874,
        "psap_id": "boston-ecc",
    }
    body.update(extra)
    return body


@pytest.fixture
def fake():
    fake = FakeExtractor()
    fake.add("White jacket robbery at Mass Ave and Boylston.", incident_type="robbery", caller_role="victim",
             location=STORE, claims=[claim("suspect", "upper_clothing_color", "white", "White jacket")])
    fake.add("Black jacket, Mass Ave and Boylston.", incident_type="robbery", caller_role="bystander",
             location=STORE, claims=[claim("suspect", "upper_clothing_color", "black", "Black jacket")])
    fake.add("Two men fighting on Washington Street.", incident_type="assault", location=WASHINGTON)
    fake.add("A fight on Washington Street, one has a bottle.", incident_type="assault", location=WASHINGTON,
             flags=Flags(weapon_present=True), claims=[claim("suspect", "weapon", "bottle", "has a bottle")])
    return fake


@pytest.fixture
def ctx(fake, tmp_path):
    scenario = {
        "scenario_id": "mini",
        "title": "Mini",
        "start_time": "2026-10-24T14:00:00-04:00",
        "calls": [
            {"id": "m1", "t_offset_s": 0, **_strip(robbery_call("White jacket robbery at Mass Ave and Boylston.", 0, "m1"))},
            {"id": "m2", "t_offset_s": 1, **_strip(robbery_call("Black jacket, Mass Ave and Boylston.", 40, "m2"))},
        ],
    }
    (tmp_path / "mini.json").write_text(json.dumps(scenario), encoding="utf-8")
    return AppContext.create(extract=fake, scenario_dir=tmp_path)


def _strip(body):
    return {k: v for k, v in body.items() if k != "received_at"}


@pytest.fixture
def client(ctx):
    with TestClient(create_app(lambda: ctx)) as test_client:
        yield test_client


def post(client, transcript, seconds, caller, **extra):
    response = client.post("/api/calls", json=robbery_call(transcript, seconds, caller, **extra))
    assert response.status_code == 200, response.text
    return response.json()


def test_post_call_then_queue(client):
    first = post(client, "White jacket robbery at Mass Ave and Boylston.", 0, "a")
    second = post(client, "Black jacket, Mass Ave and Boylston.", 40, "b")
    assert first["link"]["band"] == "new"
    assert second["link"]["band"] == "auto" and second["incident_id"] == first["incident_id"]

    queue = client.get("/api/queue").json()
    assert [item["call_id"] for item in queue] == [first["link"]["call_id"], second["link"]["call_id"]]
    assert queue[0]["priority"] >= queue[1]["priority"]


def test_websocket_streams_call_processed(client):
    with client.websocket_connect("/ws/dashboard") as ws:
        result = post(client, "White jacket robbery at Mass Ave and Boylston.", 0, "a")
        event = ws.receive_json()
    assert event["type"] == "call.processed"
    assert event["payload"]["call_id"] == result["link"]["call_id"]
    assert event["payload"]["override_reasons"] == ["new_incident"]


def test_call_detail_explain_ask_next_incident_and_briefing(client):
    post(client, "White jacket robbery at Mass Ave and Boylston.", 0, "a")
    second = post(client, "Black jacket, Mass Ave and Boylston.", 40, "b")
    call_id, incident_id = second["link"]["call_id"], second["incident_id"]

    detail = client.get(f"/api/calls/{call_id}").json()
    assert detail["claims"][0]["status"] == "verified"
    assert detail["location"]["kind"] == "intersection"

    explain = client.get(f"/api/calls/{call_id}/explain").json()
    assert set(explain["components"]) == {"geo", "time", "type", "entity"}
    assert explain["decided_by"] == "system"

    ask = client.get(f"/api/calls/{call_id}/ask-next").json()
    assert ask["confirm_line"].startswith("We have a report near ")
    assert 2 <= len(ask["questions"]) <= 3
    assert "Can you describe their jacket or top?" in ask["questions"]
    assert not any(re.search(r"\b(white|black)\b", q, re.I) for q in ask["questions"])

    incident = client.get(f"/api/incidents/{incident_id}").json()
    assert incident["incident"]["call_count"] == 2
    assert incident["consensus"][0]["contested"] is True
    assert incident["dispatch"]["illustrative"] is True

    briefing = client.get(f"/api/incidents/{incident_id}/briefing").json()
    assert all(briefing[line] for line in ("known", "disputed", "open"))
    assert "white" in briefing["disputed"] and "black" in briefing["disputed"]
    assert len(client.get("/api/incidents").json()) == 1


def test_ambiguous_caller_is_asked_which_town(client):
    post(client, "Two men fighting on Washington Street.", 0, "w1", device_lat=42.3555, device_lng=-71.0605)
    ambiguous = post(client, "A fight on Washington Street, one has a bottle.", 120, "w3",
                     device_lat=None, device_lng=None)
    assert ambiguous["link"]["band"] == "suggest"
    ask = client.get(f"/api/calls/{ambiguous['link']['call_id']}/ask-next").json()
    assert "Which town are you in?" in ask["questions"]
    assert "Boston" not in ask["confirm_line"]


def test_confirm_and_split_routes(client, ctx):
    first = post(client, "White jacket robbery at Mass Ave and Boylston.", 0, "a")
    second = post(client, "Black jacket, Mass Ave and Boylston.", 40, "b")

    assert client.post(f"/api/links/{first['link']['call_id']}/confirm").status_code == 409
    assert client.post("/api/links/c-9999/confirm").status_code == 404

    confirmed = client.post(f"/api/links/{second['link']['call_id']}/confirm").json()
    assert confirmed["link"]["band"] == "confirmed"

    split = client.post(f"/api/links/{second['link']['call_id']}/split")
    assert split.status_code == 200
    assert split.json()["incident_id"] != first["incident_id"]
    changes = [e for e in ctx.bus.recent() if e.type == "link.changed"]
    assert [e.payload["action"] for e in changes] == ["confirm", "split"]
    assert changes[-1].payload["previous_incident_id"] == first["incident_id"]
    actions = [e["action"] for e in client.get("/api/audit").json()]
    assert actions[-2:] == ["link.confirmed", "link.split"]


def test_leads_create_and_update(client):
    result = post(client, "White jacket robbery at Mass Ave and Boylston.", 0, "a")
    created = client.post("/api/leads", json={"incident_id": result["incident_id"], "description": "Canvass Newbury St"})
    assert created.status_code == 201 and created.json()["status"] == "open"
    lead_id = created.json()["id"]

    updated = client.patch(f"/api/leads/{lead_id}", json={"status": "assigned", "assigned_unit": "B-101"})
    assert updated.json()["status"] == "assigned" and updated.json()["assigned_unit"] == "B-101"
    assert client.post("/api/leads", json={"incident_id": "inc-9999", "description": "x"}).status_code == 404
    assert client.patch("/api/leads/lead-9999", json={"status": "cleared"}).status_code == 404
    assert client.post("/api/leads", json={"incident_id": result["incident_id"], "description": ""}).status_code == 422


def test_settings_read_update_and_validation(client, ctx):
    assert client.get("/api/settings").json()["auto_link_threshold"] == 0.85
    updated = client.put("/api/settings", json={"mass_event_mode": True, "auto_link_threshold": 0.88})
    assert updated.status_code == 200
    assert updated.json()["mass_event_mode"] is True and updated.json()["suggest_threshold"] == 0.5
    assert client.get("/api/settings").json()["auto_link_threshold"] == 0.88
    assert any(e.type == "settings.updated" for e in ctx.bus.recent())

    assert client.put("/api/settings", json={"suggest_threshold": 0.95}).status_code == 422
    assert client.put("/api/settings", json={"radius_m": {"moon": 5}}).status_code == 422
    assert client.put("/api/settings", json={"unknown_field": 1}).status_code == 422


def test_metrics_and_audit(client):
    post(client, "White jacket robbery at Mass Ave and Boylston.", 0, "a")
    post(client, "Black jacket, Mass Ave and Boylston.", 40, "b")
    metrics = client.get("/api/metrics").json()
    assert (metrics["calls"], metrics["incidents"]) == (2, 1)
    assert metrics["collapse_rate"] == 0.5
    assert metrics["bands"] == {"auto": 1, "suggest": 0, "new": 1, "confirmed": 0}
    assert metrics["guard"]["verified"] == 2
    assert [e["action"] for e in client.get("/api/audit").json()] == ["link.decided", "link.decided"]
    assert len(client.get("/api/audit?limit=1").json()) == 1


def test_simulation_replay_stop_and_reset(client, ctx):
    status = client.post("/api/simulation/start", json={"scenario_id": "mini", "speed": 50}).json()
    assert status["running"] is True and status["calls_total"] == 2
    ctx.replay.join(timeout=10)

    assert len(client.get("/api/queue").json()) == 2
    sim_events = [e.payload for e in ctx.bus.recent() if e.type == "sim.status"]
    assert sim_events[-1]["running"] is False and sim_events[-1]["calls_sent"] == 2
    assert sim_events[-1]["sim_time"].startswith("2026-10-24T14:00:01")
    processed = [e.payload for e in ctx.bus.recent() if e.type == "call.processed"]
    assert [p["scenario_call_id"] for p in processed] == ["m1", "m2"]

    assert client.post("/api/simulation/stop").json()["running"] is False
    reset = client.post("/api/reset").json()
    assert reset["calls_sent"] == 0
    assert client.get("/api/queue").json() == [] and client.get("/api/audit").json() == []

    assert client.post("/api/simulation/start", json={"scenario_id": "nope", "speed": 1}).status_code == 404
    assert client.post("/api/simulation/start", json={"scenario_id": "../etc", "speed": 1}).status_code == 404
    assert client.post("/api/simulation/start", json={"scenario_id": "mini", "speed": 0}).status_code == 422


def readme_endpoints():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    section = text.split("## API", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| ([A-Z, ]+) \| `([^`]+)` \|", section, re.M)
    return [(methods, path) for methods, path in rows]


def shape(path: str) -> str:
    """URL shape without parameter names: README writes {id}, routes say {call_id}."""
    return re.sub(r"\{[^}]+\}", "{}", path)


def test_openapi_lists_every_readme_endpoint(client):
    paths = {shape(path): ops for path, ops in client.get("/openapi.json").json()["paths"].items()}
    websocket_paths = {route.path for route in client.app.routes if type(route).__name__ == "APIWebSocketRoute"}
    endpoints = readme_endpoints()
    assert len(endpoints) == 20
    for methods, path in endpoints:
        if path == "/api/agent/turn":
            continue  # stretch S2, added in its own stage
        if methods.strip() == "WS":
            assert path in websocket_paths
            continue
        assert shape(path) in paths, path
        for method in (m.strip().lower() for m in methods.split(",")):
            assert method in paths[shape(path)], (method, path)


def test_spa_fallback_serves_index_but_not_for_api(ctx, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>nexus911</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    with TestClient(create_app(lambda: ctx, frontend_dist=dist)) as spa_client:
        assert "nexus911" in spa_client.get("/").text
        assert "nexus911" in spa_client.get("/operator").text
        assert spa_client.get("/assets/app.js").text == "console.log(1)"
        assert spa_client.get("/api/nothing").status_code == 404
        assert spa_client.get("/api/queue").json() == []
