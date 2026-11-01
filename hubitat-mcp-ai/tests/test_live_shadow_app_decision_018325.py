"""Stage 9.1: scoped app decision follow-up with independent, fresh identity read.

No live Hubitat requests are made by tests. All source data is synthetic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from live_shadow_app_decision import (  # noqa: E402
    app_decision_read_plan, verified_issuer, project_verified_app_logs,
)
from webui import render_page  # noqa: E402


NOW = datetime(2026,11,1,14,0,tzinfo=timezone.utc)
WHEN = "2026-11-01T13:32:59.835000+00:00"


def envelope(data):
    return SimpleNamespace(data=data,is_error=False)


def command(*, with_id=True, app_id="4012", timestamp=WHEN):
    x = {
        "name": "command-off",
        "date": timestamp,
        "producedBy": {"type":"app","id":app_id,"label":"PRIVATE AUTOMATION NAME"},
    }
    if with_id:
        x["deviceId"] = "7829"
    return x


def plan():
    return app_decision_read_plan("7829", WHEN, NOW)


def log(at=WHEN, message="Motion timeout: turning off PRIVATE BEDROOM", **kwargs):
    return {"date":at,"message":message,**kwargs}


def test_exact_command_identity_allows_narrow_log_request_only():
    p=plan()
    result=verified_issuer(p,envelope({"success":True,"events":[command()]}))
    assert result["command_record_verified_in_bounded_page"]
    assert result["recorded_issuer_app_id"]=="4012"
    assert result["command_row_device_id_explicit"]
    args=result["log_read_arguments"]
    assert args["tool"]=="hub_get_logs"
    assert args["args"]["appId"]=="4012"
    assert args["args"]["limit"]==100
    assert args["args"]["since"]=="2026-11-01T13:30:59.835000Z"
    assert args["args"]["until"]=="2026-11-01T13:34:59.835000Z"
    assert result["physical_execution_proven"] is False
    assert result["causal_link_proven"] is False
    assert result["production_publisher_approval"] is False


def test_missing_row_id_fails_to_backend_scoped_provenance_not_independent_device_proof():
    p=plan()
    result=verified_issuer(p,envelope({"success":True,"events":[command(with_id=False)]}))
    assert result["status"]=="issuer_verified_from_backend_scoped_page"
    assert not result["command_row_device_id_explicit"]
    assert result["log_scope_basis"]=="backend_target_filter_and_app_producer"
    assert result["recorded_issuer_app_id"]=="4012"
    assert not result["causal_link_proven"]


@pytest.mark.parametrize("rows", [
    [],
    [command(app_id="not-numeric")],
    [command(timestamp="2026-11-01T13:32:59.000Z")],
    [{**command(), "deviceId":"123"}],
    [command(),command(app_id="3999")],
    [{"name":"switch","value":"off","date":WHEN,"deviceId":"7829",
      "producedBy":{"type":"app","id":"4012","label":"SECRET"}}],
])
def test_no_unambiguous_exact_issuer_no_log_request(rows):
    r=verified_issuer(plan(),envelope({"success":True,"events":rows}))
    assert not r["command_record_verified_in_bounded_page"]
    assert "log_read_arguments" not in r


@pytest.mark.parametrize("id,when",[
    ("7x29",WHEN),("１２３",WHEN),("7829","2026-10-01T13:32:59Z"),
    ("7829","2026-11-02T13:32:59Z"),("7829","not-a-timestamp"),
])
def test_bad_input_fails_closed(id,when):
    with pytest.raises(ValueError):
        app_decision_read_plan(id,when,NOW)


def test_private_log_text_never_published_and_app_identity_reviewed():
    p=verified_issuer(plan(),envelope({"success":True,"events":[command()]}))
    output=project_verified_app_logs(p,envelope({"success":True,"logs":[
        log(appId="4012",message="Turning off Secret Hallway Light password=private"),
        log(appId="9999",message="Action: Off: Should not be accepted"),
        log(message="Button pressed near token:xyz@example.com"),
        log(at="2026-11-01T01:00:00Z",appId="4012",message="Action: Off: Too old"),
    ]}))
    assert output["status"]=="bounded_app_declarations_found"
    assert output["app_log_rows_returned"]==4
    assert output["excluded_other_app_rows"]==1
    assert output["rows_without_explicit_app_identity"]==1
    assert len(output["classified_decision_rows"])==2
    assert output["classified_decision_rows"][0]["classification"]=="reported-off-request"
    assert output["classified_decision_rows"][1]["app_identity_basis"]=="backend_filter_only_unverified"
    assert "log_read_arguments" not in output
    for secret in ("Secret Hallway","password=private","xyz@example.com","Should not be accepted"):
        assert secret not in str(output)
    assert not output["app_decision_or_action_proven"]
    assert not output["causal_link_proven"]


def test_malformed_or_failed_log_source_is_not_successful_empty_history():
    p=verified_issuer(plan(),envelope({"success":True,"events":[command()]}))
    assert project_verified_app_logs(p,envelope({"success":True}))["status"]=="app_log_payload_unusable"
    broken=SimpleNamespace(data={"success":False},is_error=True)
    assert project_verified_app_logs(p,broken)["status"]=="app_log_read_failed"


def test_mobile_ui_requires_separate_consent_for_app_log_read():
    page=render_page("HomeBrainOS","0.18.325")
    for phrase in (
        'id="liveShadowAppConsent"',
        'id="runLiveShadowAppDecision" disabled',
        'id="liveShadowAppFollowup" hidden',
        "api/live-shadow/app-decision",
        "x-homebrain-app-log-readonly",
        "confirm_app_decision_read:true",
        "recorded.length===1",
    ):
        assert phrase in page


def test_route_requires_consent_and_has_exact_read_only_subtools(monkeypatch,tmp_path):
    monkeypatch.setenv("CONFIG_PATH",str(tmp_path/"missing.json"))
    sys.modules.pop("app",None)
    module=importlib.import_module("app")
    monkeypatch.setattr(module.mcp,"endpoint_url","http://test.invalid/mcp")
    now=datetime.now(timezone.utc)
    stamp=(now-timedelta(minutes=10)).isoformat()
    read_args=[]
    async def reader(name,args):
        if name=="hub_get_info":
            # The app's own startup health read is unrelated to this route.
            return envelope({"success":True,"info":{}})
        read_args.append((name,args))
        if len(read_args)==1:
            assert name=="hub_read_devices"
            assert args["tool"]=="hub_list_device_events"
            assert args["args"]["attribute"]=="command-off"
            assert args["args"]["deviceId"]=="7829"
            assert args["args"]["limit"]==50
            return envelope({"success":True,"events":[{
                **command(timestamp=stamp), "deviceId":"7829"
            }]})
        assert name=="hub_read_diagnostics"
        assert args["tool"]=="hub_get_logs"
        assert args["args"]["appId"]=="4012"
        assert args["args"]["limit"]==100
        return envelope({"success":True,"logs":[log(at=stamp,appId="4012")]})
    async def forbid_cloud(*a,**k):
        raise AssertionError("Cloud is prohibited")
    monkeypatch.setattr(module.mcp,"call_tool",reader)
    monkeypatch.setattr(module.agent.transport,"_chat_post",forbid_cloud)
    headers={"x-homebrain-app-log-readonly":"confirmed","Origin":"http://testserver"}
    body={"device_id":"7829","command_at_utc":stamp,"confirm_app_decision_read":True}
    with TestClient(module.app) as client:
        assert client.post("/api/live-shadow/app-decision",json=body).status_code==403
        assert client.post("/api/live-shadow/app-decision",json={
            **body,"confirm_app_decision_read":False
        },headers=headers).status_code==403
        assert client.post("/api/live-shadow/app-decision",json=body,
            headers={**headers,"Origin":"https://attacker.example"}).status_code==403
        assert read_args==[]
        res=client.post("/api/live-shadow/app-decision",json=body,headers=headers)
        assert res.status_code==200,res.text
        assert res.headers["cache-control"]=="no-store"
        assert len(read_args)==2
        data=res.json()
        assert data["recorded_issuer_app_id"]=="4012"
        assert data["app_log_rows_returned"]==1
        assert not data["physical_execution_proven"]
        assert not data["causal_link_proven"]


def test_current_production_publisher_does_not_import_shadow_module():
    for f in ("causal_claim_publication.py","mcp_agent_orchestrator.py",
              "tool_executor.py","final_answer_coordinator.py"):
        assert "live_shadow_app_decision" not in (APP/f).read_text()


def test_stage91_copy_buttons_include_both_rendered_reports_and_reset_stale_results():
    page = render_page("HomeBrainOS", "0.18.326")
    # No new API call is needed to share results from the mobile Web UI.
    assert 'id="copyLiveShadowCommandResult" disabled' in page
    assert 'id="copyLiveShadowAppResult" disabled' in page
    assert "document.getElementById('copyLiveShadowCommandResult').onclick" in page
    assert "document.getElementById('copyLiveShadowAppResult').onclick" in page
    assert "document.getElementById('liveShadowCommandReport').textContent" in page
    assert "document.getElementById('liveShadowAppReport').textContent" in page
    assert "'Command Shadow (bounded device history):" in page
    assert "'\\n\\nApp-decision follow-up (bounded logs):" in page
    assert "void copyText(combined,button,'Copy test results')" in page
    assert "void copyText(report,button,'Copy command results')" in page
    # Prevent copying an old follow-up when a new command comparison is run.
    assert "document.getElementById('copyLiveShadowAppResult').disabled=true;" in page
    assert "document.getElementById('liveShadowAppReport').textContent='Not run. Separate consent required.'" in page
    # Full details are the already privacy-projected on-screen text, not
    # previously hidden API fields or private raw diagnostic log messages.
    copy_handler = page.split("document.getElementById('copyLiveShadowAppResult').onclick=()=>{", 1)[1].split(
        "function liveShadowAppRefreshButton()", 1
    )[0]
    assert "JSON.stringify(data)" not in copy_handler
    assert "fetch(" not in copy_handler
