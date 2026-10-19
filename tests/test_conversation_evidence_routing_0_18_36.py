"""0.18.36: chat-only recall and attribute-grounded current state."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from conversation_recall import (
    conversation_reference_answer, conversation_reference_intent,
)
from current_state_claim_contract import ground_current_device_status
from api_response_builder import build_agent_response
from mcp_agent_orchestrator import UnifiedMCPAgent


@pytest.mark.parametrize("text,expected", [
    ("What was my last question?", "last_user_question"),
    ("What did I just ask you?", "last_user_question"),
    ("Repeat my previous question", "last_user_question"),
    ("Repeat your last answer", "last_assistant_answer"),
    ("Which device did I just ask about?", "contextual_recall"),
    ("Summarise our recent conversation", "contextual_recall"),
    ("What are we currently discussing?", None),
    ("What is the current status of Bedroom 3 Mesh?", None),
    ("Which device did I just ask about and turn it off?", None),
    ("What did I just ask? Also read device 7103", None),
    ("Turn off Bedroom 3 Mesh", None),
    ("Investigate the source code for app 4019", None),
])
def test_conversation_intent_boundary(text, expected):
    assert conversation_reference_intent(text) == expected


def test_direct_recall_uses_verbatim_previous_user_text():
    history = [
        {"role": "user", "content": "Tell me the status of Bedroom 3 Mesh."},
        {"role": "assistant", "content": "It's offline."},
        {"role": "user", "content": "Why was it offline?"},
        {"role": "assistant", "content": "Cause is unknown."},
    ]
    reply, messages = conversation_reference_answer("What was my last question?", history)
    assert reply == "Your previous question was: Why was it offline?"
    assert messages is None
    reply, messages = conversation_reference_answer("Repeat your last answer", history)
    assert reply == "My previous answer was:\nCause is unknown."
    assert messages is None


def test_chat_history_is_not_cross_session_and_never_fabricated():
    text, messages = conversation_reference_answer(
        "Which device did I just ask about?", []
    )
    assert "no earlier messages" in text.lower()
    assert messages is None


def test_interpretive_recall_has_one_bounded_model_prompt_and_no_tools():
    history = [
        {"role": "user", "content": "What is the status of Bedroom 3 Mesh?"},
        {"role": "assistant", "content": "Offline"},
    ]
    deterministic, prompt = conversation_reference_answer(
        "Which device did I just ask about?", history
    )
    assert deterministic is None
    assert [m["role"] for m in prompt] == ["system", "user", "assistant", "user"]
    assert "Bedroom 3 Mesh" in prompt[1]["content"]
    assert "Do not query Hubitat" in prompt[0]["content"]


@pytest.mark.asyncio
async def test_model_recall_completes_one_round_without_hubitat_mcp_or_discovery():
    class NoTools:
        async def list_tools(self):
            raise AssertionError("conversation recall must not ask MCP for tools")

        async def get_cached_devices(self, *args, **kwargs):
            raise AssertionError("conversation recall must not query hub state")

    agent = UnifiedMCPAgent(NoTools(), "unused")
    calls = []
    async def fake_chat(messages, tools):
        calls.append((messages, tools))
        return {"role": "assistant", "content": "Bedroom 3 Mesh."}
    agent.transport.chat = fake_chat
    result = await agent.process_user_request_result(
        "Which device did I just ask about?",
        [{"role": "user", "content": "What is the status of Bedroom 3 Mesh?"},
         {"role": "assistant", "content": "Offline"}],
        session_id="test-ask",
    )
    assert result.request_class == "conversational"
    assert result.message == "Bedroom 3 Mesh."
    assert result.evidence == []
    assert len(calls) == 1 and calls[0][1] == []
    await agent.close()


@pytest.mark.asyncio
async def test_exact_previous_question_uses_zero_provider_calls():
    class NoTools:
        async def list_tools(self):
            raise AssertionError("No tools expected")
    agent = UnifiedMCPAgent(NoTools(), "unused")
    async def fail(*args, **kwargs):
        raise AssertionError("No model call expected")
    agent.transport.chat = fail
    result = await agent.process_user_request_result(
        "What was my last question?",
        [{"role": "user", "content": "What is the current mode?"},
         {"role": "assistant", "content": "The hub reports Evening mode."}],
        session_id="test-ask",
    )
    assert result.message == "Your previous question was: What is the current mode?"
    assert result.request_class == "conversational"
    assert result.evidence == []
    await agent.close()


@pytest.mark.asyncio
async def test_missing_history_does_not_hallucinate_a_device():
    class NoTools:
        async def list_tools(self):
            raise AssertionError("No tools expected")
    agent = UnifiedMCPAgent(NoTools(), "unused")
    async def fail(*args, **kwargs):
        raise AssertionError("No model call expected")
    agent.transport.chat = fail
    result = await agent.process_user_request_result(
        "Which device did I just ask about?", [],
        session_id="new-chat",
    )
    assert "no earlier messages" in result.message.lower()
    assert result.evidence == []
    await agent.close()


def _lookup(device, attrs):
    return [{
        "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
        "evidence_kind": "targeted_device_lookup", "success": True,
        "details": {"reportedDeviceState": {
            "deviceId": device["id"], "label": device["label"],
            "reportedAttributes": attrs,
            "isPhysicalConnectivityProof": False,
        }},
    }, {
        "tool": "homebrain_resolve_device",
        "evidence_kind": "deterministic_targeted_device_resolution",
        "success": True,
    }]


def test_real_mesh_status_unsupported_power_removed_without_losing_valid_state():
    evidence = _lookup({"id": "7103", "label": "Bedroom 3 Mesh"}, {
        "healthStatus": "offline", "mqttStatus": "connected",
        "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
        "dataAgeSeconds": "162325", "switch": "off",
    })
    text, fields = ground_current_device_status(
        "Bedroom 3 Mesh is currently offline (last seen Oct 12). "
        "Last reported state was off, with power draw of 8W.",
        evidence, "live-read",
    )
    assert fields == ["power"]
    assert "**Health:** offline" in text
    assert "**Switch:** off" in text
    assert "**MQTT:** connected" in text
    assert "**Last seen:** Mon Oct 12" in text
    assert "8W" not in text
    assert "physical" in text


def test_real_offline_trv_does_not_gain_invented_temperatures_and_modes():
    evidence = _lookup({"id": "4718", "label": "Livingroom TRV"}, {
        "healthStatus": "offline",
    })
    text, fields = ground_current_device_status(
        "Livingroom TRV is currently offline. Its last reported status was:\n"
        "* **Temperature:** 18.0°C\n* **Setpoint:** 20.0°C\n"
        "* **Mode:** Heat\n* **Operating State:** Idle",
        evidence, "live-read",
    )
    assert set(fields) == {"temperature", "setpoint", "mode", "operatingstate"}
    assert "**Health:** offline" in text
    for stale in ("18.0°C", "20.0°C", "Heat", "Idle"):
        assert stale not in text


def test_matching_values_and_additional_real_source_are_not_overridden():
    evidence = _lookup({"id": "4718", "label": "Livingroom TRV"}, {
        "healthStatus": "offline", "temperature": 18.0,
        "heatingSetpoint": 20.0, "thermostatMode": "heat",
        "thermostatOperatingState": "idle",
    })
    answer = (
        "Livingroom TRV is currently offline.\n"
        "* **Temperature:** 18.0°C\n* **Setpoint:** 20.0°C\n"
        "* **Mode:** Heat\n* **Operating State:** Idle"
    )
    assert ground_current_device_status(answer, evidence, "live-read") == (answer, [])
    evidence.append({
        "tool": "hub_read_devices", "sub_tool": "hub_get_device",
        "success": True, "evidence_kind": "full_device_configuration",
    })
    no_change = "Livingroom TRV is currently offline, temperature 25.0°C."
    assert ground_current_device_status(no_change, evidence, "live-read") == (no_change, [])


def test_history_and_mutation_outcomes_not_rewritten():
    evidence = _lookup({"id": "4718", "label": "Livingroom TRV"}, {"healthStatus": "offline"})
    text = "Livingroom TRV is currently offline with temperature 18°C."
    assert ground_current_device_status(text, evidence, "write") == (text, [])


def test_api_response_exposes_status_fields_reconciled_without_mutation():
    evidence = _lookup({"id": "4718", "label": "Livingroom TRV"}, {"healthStatus": "offline"})
    result = build_agent_response(SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message="Livingroom TRV is currently offline, temperature 18°C.",
        choices=[], evidence=evidence, confirmation_required=False,
        confirmation_count=0, automation_items=[], investigation_coverage=None,
        metrics={"counters": {}, "timings_ms": {}, "outcome": "success"},
    ), model="gemma4:31b", elapsed_ms=1000, version="0.18.36")
    assert "18°C" not in result["message"]
    assert "temperature" in result["evidence_validation"]["unsupported_status_fields_removed"]
    assert result["confirmation_required"] is False
    assert result["request_class"] == "live-read"
