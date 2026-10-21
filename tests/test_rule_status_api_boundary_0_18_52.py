"""v0.18.52 API integration: native-rule logic must bypass every status shortcut."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rule_machine_analysis import requires_rule_logic_inspection  # noqa: E402
from scoped_app_status_read import scoped_status_app_id  # noqa: E402
from test_deep_rule_status_routing_0_18_51 import LIVE_PERFORM_PROMPT  # noqa: E402


@pytest.mark.asyncio
async def test_actual_api_routing_rejects_status_and_inventory_shortcuts(monkeypatch):
    # Test the actual API dispatch, not just the recognizer. No model or
    # Hubitat tools are invoked: both alternative shortcuts are forbidden.
    import app as service
    import scoped_app_status_read

    observed = []

    async def forbidden_status(*args, **kwargs):
        raise AssertionError("Detailed logic was sent to scoped-app-status")

    async def expected_agent(request):
        observed.append(request.message)
        return SimpleNamespace(
            message="Detailed native-rule read path chosen; actual action tree not yet verified.",
            route="unified-mcp-agent", request_class="live-read",
            confirmation_required=False, confirmation_count=0,
            choices=[], evidence=[], investigation_coverage=None,
        )

    async def immediate_run(key, operation, **kwargs):
        return await operation

    monkeypatch.setattr(scoped_app_status_read, "read_scoped_app_status", forbidden_status)
    monkeypatch.setattr(service, "_agent_request", expected_agent)
    monkeypatch.setattr(service.request_coordinator, "run", immediate_run)
    monkeypatch.setattr(service, "apply_shared_investigation_completion", lambda outcome, prompt: outcome)
    monkeypatch.setattr(service, "calibrate_api_outcome", lambda outcome, prompt: outcome)
    # Even if an inventory matcher overmatches "status", the explicit
    # Rule Machine inspection guard must take precedence.
    monkeypatch.setattr(service.automation_status, "matches_request", lambda prompt: True)
    monkeypatch.setattr(service.automation_status, "snapshot", forbidden_status)
    monkeypatch.setattr(service, "plan_investigation", lambda prompt: None)

    assert requires_rule_logic_inspection(LIVE_PERFORM_PROMPT)
    assert scoped_status_app_id(LIVE_PERFORM_PROMPT) is None
    request = service.ChatRequest(prompt=LIVE_PERFORM_PROMPT)
    outcome = await service._answer_result(request)
    assert observed == [LIVE_PERFORM_PROMPT]
    assert outcome.route == "unified-mcp-agent"
    assert outcome.request_class == "live-read"
    assert not outcome.confirmation_required


@pytest.mark.asyncio
async def test_partial_app_status_message_is_generic_not_motion_lockout_template():
    from scoped_app_status_read import read_scoped_app_status

    class ReadOnlyAppMCP:
        async def list_tools(self):
            return [SimpleNamespace(name="hub_read_apps_code")]

        async def call_tool(self, name, arguments):
            assert name == "hub_read_apps_code"
            assert arguments["tool"] == "hub_get_app_config"
            return SimpleNamespace(
                is_error=False,
                data={"success": True, "app": {"id": 4239},
                      "page": {"sections": []}},
            )

    result = await read_scoped_app_status(ReadOnlyAppMCP(), 4239)
    assert "motion and countdown remain unverified" not in result.message
    assert "runtime behaviour or rule execution" in result.message
    assert "enabled, paused or status" in result.message
    assert result.complete is False
    assert len(result.evidence) == 1 and result.evidence[0]["success"]


@pytest.mark.asyncio
async def test_status_fallback_reads_native_rule_health_when_page_is_empty():
    from scoped_app_status_read import read_scoped_app_status

    class RuleMCP:
        def __init__(self):
            self.calls = []

        async def list_tools(self):
            return [SimpleNamespace(name="hub_read_apps_code"),
                    SimpleNamespace(name="hub_read_rules")]

        async def call_tool(self, name, args):
            self.calls.append((name, args))
            if name == "hub_read_apps_code":
                return SimpleNamespace(is_error=False, data={
                    "success": True, "app": {"id": 4239},
                    "page": {"sections": []},
                })
            if name == "hub_read_rules":
                assert args == {"tool": "hub_get_rule_health",
                                "args": {"appId": "4239"}}
                return SimpleNamespace(is_error=False, data={
                    "ok": True, "paused": False, "stopped": None,
                    "broken": False, "label": "Internet: Google TV block",
                })
            raise AssertionError("Unknown read tool: " + name)

    mcp = RuleMCP()
    result = await read_scoped_app_status(mcp, 4239)
    assert len(mcp.calls) == 2
    assert result.complete is True
    assert "paused=false" in result.message
    assert "broken=false" in result.message
    assert "stopped=" not in result.message
    assert "Actual trigger/action logic and runtime execution" in result.message
    assert all(not receipt["mutates"] for receipt in result.evidence)
    assert len(result.evidence) == 2


@pytest.mark.asyncio
async def test_health_fallback_with_unknown_fields_never_infers_paused_from_label():
    from scoped_app_status_read import read_scoped_app_status

    class RuleMCP:
        async def list_tools(self):
            return [SimpleNamespace(name="hub_read_apps_code"),
                    SimpleNamespace(name="hub_read_rules")]

        async def call_tool(self, name, args):
            if name == "hub_read_apps_code":
                return SimpleNamespace(is_error=False, data={
                    "success": True, "app": {"id": 4239},
                    "page": {"sections": []},
                })
            return SimpleNamespace(is_error=False, data={
                "ok": True, "paused": None,
                "label": "Literal (Paused) - do not trust suffix",
            })

    result = await read_scoped_app_status(RuleMCP(), 4239)
    assert not result.complete
    assert "no" not in result.message.lower() or "fields" in result.message
    assert "paused=false" not in result.message
    assert "paused=true" not in result.message
    assert len(result.evidence) == 2
