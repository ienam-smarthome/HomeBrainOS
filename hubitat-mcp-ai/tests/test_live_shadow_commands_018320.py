"""Stage 8.5 bounded read-only Hubitat device-event command/source tests."""
from __future__ import annotations
import importlib
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))
from live_shadow_commands import read_plan, project_command_shadow  # noqa: E402
from webui import render_page  # noqa: E402

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
DAY = "2026-10-12"

def plan():
    return read_plan("123", DAY, NOW)

def record(name, value, at="2026-10-12T00:30:01+00:00", **kw):
    return {"name": name, "value": value, "date": at, "deviceId": "123", **kw}

def tool_result(events, error=False):
    return SimpleNamespace(data={"success": not error, "events": events}, is_error=error)

def responses():
    return [
        ("command-off", tool_result([record(
            "command-off", "", producedBy={
                "appId": 3950, "name": "PRIVATE APP NAME"},
            description="PRIVATE EVENT LOG")])),
        ("command-on", tool_result([])),
        ("switch", tool_result([
            record("switch", "off"),
            record("switch", "on", at="2026-10-12T00:25:00Z"),
            record("switch", "on", deviceId="9999"),
            record("switch", "<secret>", at="2026-10-12T00:22:00Z"),
            record("switch", "on", at="2026-10-13T00:30:01Z"),
        ])),
    ]

def test_strict_date_and_bounded_request():
    p=plan()
    assert p["hours_back"] <= 744
    assert p["operations"] == ("command-off", "command-on", "switch")
    assert p["limit_per_operation"] == 50
    assert p["window_start_utc"] == "2026-10-12T00:00:00+00:00"

@pytest.mark.parametrize("id,date",[
    ("123x", DAY), ("", DAY), ("１２３", DAY), ("123", "2026-09-01"),
    ("123", "2026-11-05"), ("123", "2026-10-xx"), ("123", "2026-02-30"),
])
def test_malformed_or_stale_dates_and_devices_rejected(id,date):
    with pytest.raises(ValueError):
        read_plan(id,date,NOW)

def test_command_and_switch_separated_without_causal_claim():
    p=project_command_shadow(plan(),responses(),read_at_utc=NOW.isoformat())
    assert p["status"] == "bounded_source_evidence"
    assert p["returned_event_count"] == 3
    assert p["events"][0]["kind"] == "reported_switch_state"
    assert p["events"][1]["kind"] == "recorded_command"
    assert p["events"][1]["recorded_issuer_app_id"] == "3950"
    assert p["events"][2]["kind"] == "reported_switch_state"
    assert p["complete_history_proven"] is False
    assert p["physical_execution_verified"] is False
    assert p["delivery_verified"] is False
    assert p["causal_attribution_verified"] is False
    assert p["cloud_requests"] == p["device_commands"] == 0
    assert p["publisher_approval"] is False
    for sensitive in ("PRIVATE APP", "PRIVATE EVENT", "secret", "9999"):
        assert sensitive not in str(p)

def test_one_failed_upstream_page_not_misreported_as_absence():
    rs=responses()
    rs[0]=("command-off",tool_result([],error=True))
    p=project_command_shadow(plan(),rs,read_at_utc=NOW.isoformat())
    assert p["status"] == "partial_or_failed_read"
    assert p["read_status"]["command-off"] == "upstream_read_failed"
    assert p["complete_history_proven"] is False

def test_mismatched_read_operation_rejected():
    rs=responses()
    rs[0]=("hub_run_command",rs[0][1])
    assert project_command_shadow(plan(),rs,read_at_utc=NOW.isoformat())[
        "status"]=="blocked_unexpected_read_operation"

def test_empty_successful_history_not_global_absence():
    rs=[(op,tool_result([])) for op in plan()["operations"]]
    p=project_command_shadow(plan(),rs,read_at_utc=NOW.isoformat())
    assert p["returned_event_count"]==0
    assert p["complete_history_proven"] is False

def test_mobile_ui_has_independent_consent_and_date():
    html=render_page("HomeBrainOS","0.18.320")
    for snippet in (
        'id="liveShadowIncidentDate" type="date"',
        'id="liveShadowCommandConsent"',
        'id="runLiveShadowCommands" disabled',
        "api/live-shadow/command-events",
        "x-homebrain-command-readonly",
        "confirm_command_read:true",
        "Historical completeness proven: NO",
    ):
        assert snippet in html

def test_end_to_end_route_requires_consent_and_only_calls_three_read_subtools(monkeypatch,tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path/"missing.json"))
    sys.modules.pop("app",None)
    module=importlib.import_module("app")
    monkeypatch.setattr(module.mcp,"endpoint_url","http://example.invalid/mcp")
    call_args=[]
    async def mock_call(name,args):
        assert name=="hub_read_devices"
        assert args["tool"]=="hub_list_device_events"
        assert args["args"]["deviceId"]=="123"
        assert args["args"]["limit"]==50
        assert args["args"]["attribute"] in ("command-off","command-on","switch")
        assert 1 <= args["args"]["hoursBack"] <= 744
        call_args.append(args)
        ev=next(x[1].data["events"] for x in responses() if x[0]==args["args"]["attribute"])
        return tool_result(ev)
    async def forbid_cloud(*args,**kwargs):
        raise AssertionError("Cloud prohibited in shadow")
    monkeypatch.setattr(module.mcp,"call_tool",mock_call)
    monkeypatch.setattr(module.agent.transport,"_chat_post",forbid_cloud)
    # Test clock is dynamic; use today's UTC date, not a fixed stale date.
    from datetime import datetime, timezone
    today=datetime.now(timezone.utc).date().isoformat()
    body={"device_id":"123","incident_utc_date":today,"confirm_command_read":True}
    headers={"x-homebrain-command-readonly":"confirmed", "Origin":"http://testserver"}
    with TestClient(module.app) as client:
        assert client.post("/api/live-shadow/command-events",json=body).status_code==403
        assert client.post("/api/live-shadow/command-events",json=body,
            headers={**headers,"Origin":"https://evil.test"}).status_code==403
        assert client.post("/api/live-shadow/command-events",json={**body,
            "confirm_command_read":False},headers=headers).status_code==403
        assert client.post("/api/live-shadow/command-events",json={**body,
            "device_id":"123xyz"},headers=headers).status_code==422
        assert call_args == []
        response=client.post("/api/live-shadow/command-events",json=body,headers=headers)
        assert response.status_code==200,response.text
        assert response.headers["cache-control"]=="no-store"
        assert len(call_args)==3
        assert response.json()["publisher_approval"] is False

def test_publisher_and_live_control_paths_remain_separate():
    for file in ("causal_claim_publication.py","mcp_agent_orchestrator.py",
                 "tool_executor.py","final_answer_coordinator.py"):
        assert "live_shadow_commands" not in (APP/file).read_text()
