"""Stage 8.3 local Historical Journal shadow: bounded, private, fail-closed."""
from __future__ import annotations
import importlib
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from live_shadow_journal import project_shadow_history  # noqa: E402
from webui import render_page  # noqa: E402

T0 = "2026-10-02T00:00:00+00:00"
T1 = "2026-11-01T00:00:00+00:00"

def archive():
    return {
        "events": [
            {"stream": "events", "device_id": "7103", "attribute": "switch",
             "value": "off", "source_time": "2026-10-12T01:30:01+00:00",
             "observed_at": "2026-10-12T01:30:01+00:00",
             "received_at": "2026-10-12T01:30:02+00:00",
             "display_name": "Private house", "message": "SECRET"},
            {"stream": "events", "device_id": "7103", "attribute": "power",
             "value": "8", "source_time": "",
             "observed_at": "2026-10-12T01:30:02+00:00",
             "received_at": "2026-10-12T01:30:02+00:00",
             "message": "Bearer token"},
            {"stream": "logs", "device_id": "7103", "attribute": "switch",
             "value": "off", "observed_at": T0,
             "received_at": T0, "message": "SECRET app message"},
            {"stream": "events", "device_id": "9999", "attribute": "switch",
             "value": "on", "observed_at": T0, "received_at": T0},
            {"stream": "events", "device_id": "7103", "attribute": "lastError",
             "value": "password:secret", "observed_at": T0, "received_at": T0},
        ],
        "gaps": [{"stream": "events", "started_at": "2026-10-15T12:00:00+00:00",
                  "ended_at": "2026-10-15T12:04:00+00:00", "reason": "SECRET"},
                 {"stream": "logs", "started_at": T0, "ended_at": T1, "reason": "SECRET"}],
        "offset": 0, "has_more": False, "coverage_complete": False,
    }

def project(a=None):
    return project_shadow_history("7103", archive() if a is None else a,
                                  window_start=T0, window_end=T1, read_at=T1)

def test_history_tracks_source_and_receipt_without_physical_proof():
    p = project()
    assert p["status"] == "bounded_archive_evidence"
    assert p["returned_event_count"] == 2
    assert p["events"][0]["source_time_utc"] == "2026-10-12T01:30:01+00:00"
    assert p["events"][0]["received_at_utc"] == "2026-10-12T01:30:02+00:00"
    assert p["events"][1]["source_time_utc"] is None
    assert p["events"][1]["timestamp_basis"] == "collector_only"
    assert len(p["collection_gaps"]) == 1
    assert p["history_complete"] is False
    assert p["missing_events_prove_inactivity"] is False
    assert p["causal_attribution_verified"] is False
    assert p["publisher_approval"] is False
    assert p["cloud_requests"] == p["device_commands"] == 0
    for secret in ("SECRET", "password", "Private house", "Bearer", "9999"):
        assert secret not in str(p)

def test_empty_archive_is_not_inactivity_or_global_absence():
    p = project({"events": [], "gaps": [], "offset": 0, "has_more": False})
    assert p["returned_event_count"] == 0
    assert not p["missing_events_prove_inactivity"]
    assert not p["history_complete"]

@pytest.mark.parametrize("bad", [
    None, [], {"events": "oops", "gaps": []},
    {"events": [], "gaps": {}},
])
def test_bad_archives_blocked(bad):
    assert project(bad)["status"] == "blocked_archive_shape"

def test_oversized_or_offset_results_blocked():
    a = archive()
    a["offset"] = 10
    assert project(a)["status"] == "blocked_unbounded_archive_page"
    a["offset"] = 0
    a["events"] = a["events"] * 12
    assert project(a)["status"] == "blocked_unbounded_archive_page"

def test_no_untrusted_strings_in_projected_values():
    a=archive()
    a["events"][0]["value"]="<script>private</script>"
    a["events"][1]["value"]="nan"
    p=project(a)
    assert p["events"] == []
    assert "private" not in str(p)

def test_phone_ui_explicit_separate_archive_consent():
    html=render_page("HomeBrainOS","0.18.318")
    for word in (
        "liveShadowHistoryConsent", "runLiveShadowHistory",
        "api/live-shadow/journal-history", "x-homebrain-archive-readonly",
        "confirm_archive_read:true", "source time is NOT independently authenticated",
        "No retained, allowlisted device events returned",
    ):
        assert word in html

def test_endpoint_is_read_only_with_explicit_consent(monkeypatch,tmp_path):
    monkeypatch.setenv("CONFIG_PATH",str(tmp_path/"missing.json"))
    sys.modules.pop("app",None)
    module=importlib.import_module("app")
    queries=[]
    def fake_query(**kw):
        queries.append(kw)
        assert kw["device_id"]=="7103"
        assert kw["limit"]==50 and kw["offset"]==0
        return archive()
    monkeypatch.setattr(module.historical_journal,"enabled",True)
    monkeypatch.setattr(module.historical_journal,"_started",True)
    monkeypatch.setattr(module.historical_journal,"query",fake_query)
    async def forbid(*args,**kwargs):
        raise AssertionError("No model or hub command permitted")
    monkeypatch.setattr(module.mcp,"call_tool",forbid)
    monkeypatch.setattr(module.agent.transport,"_chat_post",forbid)
    body={"device_id":"7103","confirm_archive_read":True}
    headers={"x-homebrain-archive-readonly":"confirmed","Origin":"http://testserver"}
    with TestClient(module.app) as client:
        assert client.post("/api/live-shadow/journal-history",json=body).status_code==403
        assert client.post("/api/live-shadow/journal-history",json=body,
            headers={**headers,"Origin":"https://evil.example"}).status_code==403
        assert client.post("/api/live-shadow/journal-history",json=body,
            headers={**headers,"sec-fetch-site":"cross-site"}).status_code==403
        assert client.post("/api/live-shadow/journal-history",json={**body,
            "confirm_archive_read":False},headers=headers).status_code==403
        assert client.post("/api/live-shadow/journal-history",json={**body,
            "device_id":"7103x"},headers=headers).status_code==422
        assert not queries
        r=client.post("/api/live-shadow/journal-history",json=body,headers=headers)
        assert r.status_code==200,r.text
        assert r.headers["cache-control"]=="no-store"
        assert r.json()["returned_event_count"]==2
        assert len(queries)==1

def test_production_publisher_unchanged():
    for name in ("mcp_agent_orchestrator.py","tool_executor.py",
                 "causal_claim_publication.py","final_answer_coordinator.py"):
        assert "live_shadow_journal" not in (APP/name).read_text()
