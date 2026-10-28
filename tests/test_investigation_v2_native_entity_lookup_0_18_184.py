"""General-purpose named-device identification in the native MCP agent."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from mcp_client import MCPTool
from investigation_v2.native_entity_lookup import choose_device, NAME
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor

DEVICE = MCPTool(
    "hub_read_devices", "Read devices",
    {"type": "object", "properties": {
        "tool": {"type": "string", "enum": ["hub_get_device", "hub_list_devices"]},
        "args": {"type": "object", "additionalProperties": True},
    }, "required": ["tool", "args"]}, annotations={"readOnlyHint": True}
)


def native(name, args):
    return {"function": {"name": name, "arguments": args}}


def test_authoritative_resolver_never_picks_ambiguous_short_name():
    identities = [
        {"id": "7103", "name": "Tasmota MQTT - Bedroom3_Mesh", "label": "Bedroom 3 Mesh"},
        {"id": "8002", "name": "Test Mesh", "label": "Bedroom 3 Mesh Backup"},
    ]
    answer = choose_device("Bedroom 3 Mesh", identities)
    assert answer["status"] == "unique"
    assert answer["matches"][0]["id"] == "7103"
    assert choose_device("Mesh", identities)["status"] == "not_found"
    identities[1]["label"] = "Bedroom 3 Mesh"
    assert choose_device("Bedroom 3 Mesh", identities)["status"] == "ambiguous"


def test_identity_resolver_cannot_promote_unverified_ids_or_generic_substrings():
    assert choose_device("Bedroom 3 Mesh", [{"id": "not-a-number",
        "label": "Bedroom 3 Mesh"}])["status"] == "not_found"
    assert choose_device("unknown Device", [{"id": "7103",
        "label": "Bedroom 3 Mesh"}])["status"] == "not_found"
    assert choose_device("Mesh", [{"id": "7103",
        "label": "Bedroom 3 Mesh"}])["status"] == "not_found"


@pytest.mark.asyncio
async def test_model_resolves_label_before_specific_device_read_without_full_list():
    mcp = FakeMCP([DEVICE])
    calls = []
    async def fast_identity():
        calls.append("verified_context")
        return [{"id": "7103", "name": "Tasmota MQTT - Bedroom3_Mesh",
                 "label": "Bedroom 3 Mesh"}]
    mcp.get_device_identities = fast_identity
    executor = FakeExecutor(mcp, [{
        "id": "7103", "name": "Tasmota MQTT - Bedroom3_Mesh",
        "label": "Bedroom 3 Mesh",
        "attributes": [{"name": "healthStatus", "value": "offline"},
                       {"name": "lastSeen", "value": "Mon Oct 12 01:30:01 BST 2026"},
                       {"name": "mqttStatus", "value": "connected"}],
    }])
    count = 0
    async def model(messages, tools):
        nonlocal count
        count += 1
        assert any(t["function"]["name"] == NAME for t in tools)
        if count == 1:
            return {"tool_calls": [native(NAME, {"name": "Bedroom 3 Mesh"})]}
        if count == 2:
            assert '"status": "unique"' in messages[-1]["content"]
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_get_device",
                "args": {"deviceId": "7103", "mode": "summary"},
            })]}
        return {"content": (
            "Device 7103 reports offline; lastSeen Oct 12, "
            "while MQTT connected does not prove the plug is online."
        )}
    out = await run_native_read_agent(
        question="Why is Bedroom 3 Mesh offline?",
        chat=model, mcp=mcp, executor=executor,
    )
    assert calls == ["verified_context"]
    assert out["native_diagnostics"]["named_identity_lookups"][0]["status"] == "unique"
    assert out["native_diagnostics"]["successful_reads"] == 1
    assert out["native_diagnostics"]["reads_executed"] == 1
    assert executor.calls[0][1]["args"]["deviceId"] == "7103"
    assert "offline" in out["answer"]["text"]


@pytest.mark.asyncio
async def test_ambiguous_name_produces_no_device_read_permission():
    mcp = FakeMCP([DEVICE])
    async def ambiguous():
        return [{"id": "7103", "label": "Bedroom 3 Mesh"},
                {"id": "8002", "label": "Bedroom 3 Mesh"}]
    mcp.get_device_identities = ambiguous
    executor = FakeExecutor(mcp, [])
    step = 0
    async def model(messages, tools):
        nonlocal step
        step += 1
        if step == 1:
            return {"tool_calls": [native(NAME, {"name": "Bedroom 3 Mesh"})]}
        if step == 2:
            assert '"status": "ambiguous"' in messages[-1]["content"]
        return {"content": "Two devices share that label; the subject is ambiguous."}
    out = await run_native_read_agent(
        question="Investigate Bedroom 3 Mesh",
        chat=model, mcp=mcp, executor=executor,
    )
    assert out["native_diagnostics"]["verified_source_ids"] == 0
    assert executor.calls == []


@pytest.mark.asyncio
async def test_hub_question_does_not_need_identity_lookup():
    mcp = FakeMCP([DEVICE])
    async def forbid():
        raise AssertionError("Whole-hub question should not force device identity")
    mcp.get_device_identities = forbid
    executor = FakeExecutor(mcp, [])
    async def model(messages, tools):
        return {"content": "No source reads have yet been made."}
    out = await run_native_read_agent(
        question="Is the hub healthy?",
        chat=model, mcp=mcp, executor=executor,
    )
    assert out["native_diagnostics"]["named_identity_lookups"] == []
    assert not out["native_diagnostics"]["lazy_identity_lookup_attempted"]
