"""0.18.114: no diagnostic request can finish as a device inventory.

Exercises the actual catalog and base-agent API boundary with simulated
Hubitat resources; does not call real Hubitat or an AI provider.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_fulfillment_gate import (
    investigating, inventory_without_investigation, inventory_answer,
    observation_sources, retry_instruction, honest_partial_answer,
)
from ai_investigation_routing import (
    ReadRouteDecision, set_request_interpretation, reset_request_interpretation,
)
from tool_catalog_assembly import build_request_tool_catalog
from mcp_agent_orchestrator import UnifiedMCPAgent

REQUEST = (
    "Why does Livingroom Light 1 sometimes stay ON when nobody is in the room? "
    "Investigate its actual controlling automation, configured sensors, "
    "inactivity timers and relevant recorded activity. "
    "Identify the most likely cause using verified evidence. "
    "Read-only. Do not change anything."
)


def _identity_receipts():
    return [
        {"tool": "homebrain_resolve_device",
         "success": True, "effect": "read", "arguments":
         {"name": "Livingroom Light 1"}},
        {"tool": "homebrain_device_inventory",
         "success": True, "effect": "read", "arguments":
         {"group": "Living Room"}},
        {"tool": "hub_read_devices", "sub_tool": "hub_list_devices",
         "success": True, "effect": "read",
         "arguments": {"tool": "hub_list_devices", "args": {
             "labelFilter": "Livingroom Light 1", "detailed": True,
         }}},
    ]


def test_real_failure_replay_inventory_receipts_do_not_satisfy_investigation():
    rows = _identity_receipts()
    assert investigating(REQUEST)
    assert inventory_without_investigation(REQUEST, rows)
    assert observation_sources(rows) == ()
    assert inventory_answer("17 devices in **Living Room**: motion and lights.")
    assert not inventory_answer("The light is OFF based on a live read.")
    message = retry_instruction(REQUEST, rows)
    assert "inventory list is NOT an answer" in message
    assert "app configuration" in message
    assert "virtual/soft sensor is not independent occupancy proof" in message
    assert "read-only" in message.casefold()
    response = honest_partial_answer(REQUEST, rows)
    assert "could not verify" in response
    assert "17 devices" not in response


def test_real_app_config_or_history_counts_as_observation_not_causal_proof():
    rows = _identity_receipts()
    rows.append({
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
        "arguments": {"tool": "hub_get_app_config", "args": {"appId": "4019"}},
        "success": True, "effect": "read", "mutates": False,
        "summary": "object fields: success, app, page",
    })
    assert observation_sources(rows) == ("hub_get_app_config",)
    assert not inventory_without_investigation(REQUEST, rows)


def test_plain_inventory_and_live_state_queries_remain_eligible():
    for question in (
        "list devices in Living Room", "Show all devices",
        "Is Livingroom Light 1 ON or OFF?",
    ):
        assert not investigating(question)
        assert not inventory_without_investigation(question, _identity_receipts())


def test_catalog_hides_inventory_even_after_read_view_and_expansion():
    catalog = build_request_tool_catalog([])
    assert "homebrain_device_inventory" in catalog.available_names
    catalog.replace_declared(["homebrain_device_inventory",
                              "homebrain_resolve_device"])
    assert catalog.declared_tool("homebrain_device_inventory") is not None
    catalog.hide_inventory_during_investigation()
    assert catalog.declared_tool("homebrain_device_inventory") is None
    catalog.replace_declared(["homebrain_device_inventory",
                              "homebrain_resolve_device"])
    assert catalog.declared_tool("homebrain_device_inventory") is None
    catalog.activate_investigation_read_view(max_declared=30)
    assert "homebrain_device_inventory" not in catalog.declared_names
    assert "homebrain_device_inventory" not in [
        schema["function"]["name"] for schema in catalog.schemas()
    ]
    assert "homebrain_resolve_device" in catalog.available_names


def test_interpreted_intent_controls_fulfillment_independent_of_keywords():
    request = "Please investigate the machine."
    token = set_request_interpretation(
        request, ReadRouteDecision(
            "model_led", "model_choice",
            objective="general_investigation", target="machine",
            purpose="find why machine stopped",
        )
    )
    try:
        assert investigating(request)
        assert inventory_without_investigation(request, _identity_receipts())
        assert "machine" in retry_instruction(request, _identity_receipts())
    finally:
        reset_request_interpretation(token)


class _FakeMCP:
    async def list_tools(self):
        return []

    async def get_device_identities(self):
        return []


class _NoProvider:
    async def post(self, *_args, **_kwargs):
        raise AssertionError("No model call should be needed to guard output")
    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_actual_agent_boundary_does_not_return_familiar_wrong_inventory(monkeypatch):
    agent = UnifiedMCPAgent(
        _FakeMCP(), "key", "fake", ai_client=_NoProvider(),
        require_sensitive_confirmation=False,
    )

    async def wrong_investigation(*_args, **_kwargs):
        agent.evidence.record(
            "homebrain_device_inventory", {"group": "Living Room"},
            success=True, effect="read", mutates=False,
            summary="room identity list", supports_live_claim=True,
        )
        return ("17 devices in **Living Room**: FP400 motion sensor, "
                "Livingroom Light 1, Livingroom Soft Sensor.")

    monkeypatch.setattr(agent, "_process_user_request", wrong_investigation)
    outcome = await agent.process_user_request_result(REQUEST)
    assert "17 devices in **Living Room**" not in outcome.message
    assert "could not verify" in outcome.message
    assert outcome.request_class == "live-read"
    assert outcome.confirmation_required is False
    assert all(row.get("mutates") is not True for row in outcome.evidence)


def test_legacy_inventory_shortcut_is_checked_at_actual_tool_agent_boundary():
    source = (APP / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "catalog.hide_inventory_during_investigation()" in source
    assert 'increment_active_metric("investigation_inventory_only_retry")' in source
    assert 'increment_active_metric("investigation_inventory_only_stopped")' in source
    assert 'increment_active_metric("investigation_unfulfilled_at_boundary")' in source
    assert "inventory_answer(message)" in source


def test_host_scope_override_retains_effective_ai_interpretation():
    source = (APP / "app.py").read_text(encoding="utf-8")
    assert 'active_decision = ReadRouteDecision(' in source
    assert 'provenance="host_scope_override"' in source
    assert '"objective": active_decision.objective' in source
