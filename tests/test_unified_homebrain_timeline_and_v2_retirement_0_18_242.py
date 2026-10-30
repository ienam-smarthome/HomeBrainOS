"""v0.18.242 real Bathroom live-response omission and retired V2 HTTP surface.

Checks the actual post-model original-agent boundary, not only a helper.
Keeps V2 source projection tests as offline reusable library coverage.
"""
from __future__ import annotations
import importlib
import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from unified_investigation_bridge import (
    verified_group_timeline, reconcile_unified_investigation_answer,
)
from mcp_agent_orchestrator import UnifiedMCPAgent
from test_unified_homebrain_investigation_0_18_241 import (
    QUESTION, bathroom, reported, command, read_device,
)


def complete_bathroom_receipts():
    rows = bathroom()
    for r in rows:
        args = r.get("arguments", {}).get("args", {})
        if r.get("sub_tool") != "hub_list_device_events":
            continue
        if args.get("deviceId") == "7818":
            r["details"]["observedEvents"] += [
                command("off", "03:04:16.978", "1568", "button 3 pushed"),
                reported("switch", "03:04:18.218", "off"),
            ]
        if args.get("deviceId") == "7821":
            r["details"]["observedEvents"] += [
                command("off", "03:04:16.993", "1568", "button 3 pushed"),
                reported("switch", "03:04:18.278", "off"),
            ]
    return rows


LIVE_WRONG = (
    "The light activations were primarily driven by motion and occupancy sensors, "
    "with specific overrides from physical button presses.\n\n"
    "### **Causal Analysis**\n"
    "The evidence shows a Hubitat app command followed by state. "
    "This confirms the lights were controlled by hub automations.\n"
    "**Shower Light:** Triggered by the Shower app.\n"
    "**Bathroom Light 1 (07:15):** ON (50%) because of School Run.\n\n"
    "### **Chronological Timeline**\n"
    "| Time | Device | Event |\n|---|---|---|\n"
    "| 02:13:30 | Shower Light | ON |\n"
    "| 07:15:02 | Bathroom Light 1 | ON |\n"
    "| 07:27:48 | Shower Light | ON |\n\n"
    "### **Unverified Evidence**\n"
    "Historical app execution log coverage remains unverified."
)


def test_full_source_timeline_preserves_every_returned_bathroom_light():
    output = verified_group_timeline(complete_bathroom_receipts(), QUESTION)
    assert output is not None
    for device in ("Bathroom Light 1", "Bathroom Light 2", "Shower Light"):
        assert device in output
    for time in ("03:04:18", "03:40:21", "03:40:22",
                 "03:46:05", "03:46:06", "07:12:33", "07:12:34"):
        assert time in output
    assert "07:12:33 | Bathroom Light 1 | ON" in output
    assert "07:12:34 | Bathroom Light 2 | ON" in output
    assert "07:15:02 | Bathroom Light 1 | ON" not in output
    assert "02:18:15" not in output  # Claude-only log row not in this receipt
    assert "02:52:44" not in output  # must not invent unseen events
    assert output.index("03:40:21") < output.index("03:40:22")
    assert output.index("03:40:22") < output.index("03:46:05")
    assert "App 1568 issued off()" in output
    assert "App 1569 issued off()" in output
    assert "ON reported before app 4013's setLevel adjustment" in output


def test_wrong_model_timeline_is_replaced_and_unverified_on_cause_corrected():
    result, changed = reconcile_unified_investigation_answer(
        LIVE_WRONG, complete_bathroom_receipts(), QUESTION)
    assert changed
    assert result.count("### Verified device-transition timeline") == 1
    assert "### **Chronological Timeline**" not in result
    assert "This confirms the lights were controlled" not in result
    assert "Triggered by the Shower app" not in result
    assert "07:12:33 | Bathroom Light 1 | ON" in result
    assert "07:12:34 | Bathroom Light 2 | ON" in result
    assert "07:15:02 | Bathroom Light 1 | ON" not in result
    assert "Historical app execution log coverage remains unverified" in result
    assert "correlations, not proof" in result
    assert "external controller remains unverified" in result


def test_no_verification_means_no_fabricated_source_timeline():
    original, changed = reconcile_unified_investigation_answer(
        LIVE_WRONG, bathroom(sensors=False)[3:5], QUESTION)
    assert not changed
    assert original == LIVE_WRONG


class _FakeMCP:
    async def list_tools(self):
        return []
    async def get_device_identities(self):
        return []


class _NoProvider:
    async def post(self, *args, **kwargs):
        raise AssertionError("An extra model call is not needed for final coverage")
    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_actual_original_agent_early_return_still_corrects_three_light_timeline(monkeypatch):
    agent = UnifiedMCPAgent(_FakeMCP(), "key", "fake",
                            ai_client=_NoProvider(),
                            require_sensitive_confirmation=False)
    async def wrong_model(*_args, **_kwargs):
        for receipt in complete_bathroom_receipts():
            agent.evidence.record(
                receipt["tool"], receipt["arguments"],
                success=True, mutates=False, effect="read", elapsed_ms=1,
                supports_live_claim=True,
                evidence_kind="tool_result",
                details=receipt["details"],
                sub_tool=receipt["sub_tool"],
            )
        return LIVE_WRONG
    monkeypatch.setattr(agent, "_process_user_request", wrong_model)
    outcome = await agent.process_user_request_result(QUESTION)
    assert "### Verified device-transition timeline" in outcome.message
    assert "Bathroom Light 1 | ON" in outcome.message
    assert "Bathroom Light 2 | ON" in outcome.message
    assert "Shower Light | ON" in outcome.message
    assert "07:12:33 | Bathroom Light 1" in outcome.message
    assert "07:12:34 | Bathroom Light 2" in outcome.message
    assert all(r.get("mutates") is False for r in outcome.evidence)
    assert not outcome.confirmation_required


def test_legacy_v2_browser_test_is_removed_but_offline_provenance_survives(monkeypatch, tmp_path):
    cfg = tmp_path / "options.json"
    cfg.write_text(json.dumps({
        "morning_health_check_enabled": False,
        "one_time_rule_cleanup_enabled": False
    }))
    monkeypatch.setenv("CONFIG_PATH", str(cfg))
    sys.modules.pop("app", None)
    application = importlib.import_module("app")
    with TestClient(application.app) as client:
        for verb, path in (
            ("get", "/v2-test"),
            ("post", "/api/v2/test"),
            ("get", "/api/v2/auth/status"),
            ("post", "/api/v2/auth/remember"),
            ("post", "/api/v2/auth/forget"),
        ):
            assert getattr(client, verb)(path).status_code == 404
        assert client.get("/").status_code == 200
        assert "Investigation V2 Test" not in client.get("/").text
    import investigation_v2.native_provenance as retained
    assert callable(retained.event_summary)
    assert "investigation_v2_testing_enabled" not in (APP.parent.parent / "config.yaml").read_text()
