"""v0.18.175 regression: only exact LIVE-advertised READ operation aliases
can be canonicalised; schema/target/effect gates remain authoritative.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect
from investigation_v2 import build_case_file
from investigation_v2.read_operation_canonicalizer import canonicalize_read_suboperations
from investigation_v2.planning import review_model_read_proposals
from investigation_v2.read_loop import run_read_only_investigation


def gateway(name="hub_read_devices", operations=None, *, writable=False,
            open_args=False):
    if operations is None:
        operations = ["hub_list_device_events", "hub_get_device"]
    nested = ({"type": "object"} if open_args else {
        "type": "object",
        "properties": {
            "deviceId": {"type": "string"},
            "attribute": {"type": "string"},
            "hoursBack": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": ["deviceId"],
        "additionalProperties": False,
    })
    return MCPTool(name, "Safe read gateway", {
        "type": "object",
        "properties": {
            "tool": {"type": "string", "enum": operations},
            "args": nested,
        },
        "required": ["tool", "args"],
        "additionalProperties": False,
    }, annotations={"readOnlyHint": not writable, "mutates": writable})


def alias(*, operation="hub_list_device_events", args=None, name=None):
    return {
        "tool": name or operation,
        "arguments": {"deviceId": "7828", "attribute": "switch",
                      "hoursBack": 24, "limit": 50} if args is None else args,
        "discriminator": "Get a different bounded view of switch changes",
        "information_gain": "Test whether the history includes a command or initiating source",
        "hypothesis_ids": [],
    }


def reviewed(proposals, manifest=None):
    return review_model_read_proposals(
        build_case_file("Why did Livingroom Light 2 switch off?", []),
        proposals, manifest or [gateway()], verified_entity_ids=("7828",),
        max_total_reads=4,
    )


def test_read_suboperation_alias_becomes_exact_live_gateway_and_passes_host_review():
    proposed = alias()
    fixed, repaired = canonicalize_read_suboperations(
        [proposed], [gateway()], verified_entity_ids=("7828",))
    assert repaired == 1
    assert fixed[0]["tool"] == "hub_read_devices"
    assert fixed[0]["arguments"] == {
        "tool": "hub_list_device_events",
        "args": {"deviceId": "7828", "attribute": "switch",
                 "hoursBack": 24, "limit": 50},
    }
    result = reviewed(fixed)
    assert len(result.approved) == 1 and not result.rejected
    assert proposed["tool"] == "hub_list_device_events"  # No input mutation.


def test_host_may_supply_single_verified_id_but_never_override_explicit_id():
    no_id = alias(args={"attribute": "switch", "hoursBack": 24, "limit": 50})
    fixed, repaired = canonicalize_read_suboperations(
        [no_id], [gateway()], verified_entity_ids=("7828",))
    assert repaired == 1
    assert fixed[0]["arguments"]["args"]["deviceId"] == "7828"
    assert len(reviewed(fixed).approved) == 1
    unknown = alias(args={"deviceId": "9999", "attribute": "switch",
                          "hoursBack": 24, "limit": 50})
    fixed, repaired = canonicalize_read_suboperations(
        [unknown], [gateway()], verified_entity_ids=("7828",))
    assert repaired == 1
    assert fixed[0]["arguments"]["args"]["deviceId"] == "9999"
    result = reviewed(fixed)
    assert not result.approved
    assert result.rejected[0].reason == "target ID has no independent verified scope"
    ambiguous, repaired = canonicalize_read_suboperations(
        [no_id], [gateway()], verified_entity_ids=("7828", "7829"))
    assert repaired == 0
    assert ambiguous == [no_id]


@pytest.mark.parametrize("proposal,manifest", [
    (alias(name="hub_list_fictitious"), [gateway()]),
    (alias(name="hub_set_rule"), [gateway()]),
    (alias(name="hub_list_device_events"), [gateway(writable=True)]),
    (alias(), [gateway(operations=["hub_get_device"])]),
    (alias(), [gateway(), gateway(name="hub_read_diagnostics")]),
    (alias(args={"deviceId": "7828", "command": "off"}), [gateway()]),
    (alias(args={"tool": "hub_get_device", "args": {"deviceId": "7828"}}), [gateway()]),
])
def test_nonunique_unadvertised_mutating_or_contradictory_alias_is_not_repaired(
    proposal, manifest,
):
    original = [proposal]
    fixed, repaired = canonicalize_read_suboperations(
        original, manifest, verified_entity_ids=("7828",))
    assert fixed == original
    assert repaired == 0


def test_preexisting_real_gateway_is_never_rewritten():
    p = alias(name="hub_read_devices",
              args={"tool": "hub_list_device_events", "args": {"deviceId": "7828"}})
    fixed, count = canonicalize_read_suboperations(
        [p], [gateway()], verified_entity_ids=("7828",))
    assert count == 0 and fixed == [p]


class FakeMCP:
    async def list_tools(self):
        return [gateway()]


class FakeExecutor:
    def __init__(self, mcp):
        self.mcp = mcp
        self.calls = []

    async def execute(self, name, arguments, **kwargs):
        self.calls.append((name, arguments))
        result = MCPToolResult(
            name, arguments, {}, "UNTRUSTED PRIVATE MESSAGE", {
                "deviceId": "7828",
                "events": [{"deviceId": "7828", "name": "switch",
                            "value": "off", "date": "2026-10-28T00:14:57Z"}],
            })
        return ToolExecution(
            name=name, arguments=arguments, effect=ToolEffect.READ,
            success=True, elapsed_ms=5, content="", result=result)


@pytest.mark.asyncio
async def test_read_loop_executes_repaired_alias_but_only_after_normal_review():
    mcp = FakeMCP()
    executor = FakeExecutor(mcp)
    async def proposer(_case, _round):
        return {"reads": [alias()], "finish": False, "hypotheses": []}
    result = await run_read_only_investigation(
        question="Investigate the latest OFF transition",
        mcp=mcp, executor=executor, propose=proposer,
        verified_entity_ids=("7828",), max_rounds=1,
    )
    assert result.executed_reads == 1
    assert executor.calls[0][0] == "hub_read_devices"
    assert executor.calls[0][1]["tool"] == "hub_list_device_events"
    assert result.planning_diagnostics[0]["canonical_read_aliases"] == 1
    assert result.case.records[0].stage == "state_reported"


@pytest.mark.asyncio
async def test_unknown_tool_does_not_waste_two_long_model_rounds():
    mcp = FakeMCP()
    executor = FakeExecutor(mcp)
    rounds = []
    async def proposer(_case, round_index):
        rounds.append(round_index)
        return {"reads": [alias(name="nonexistent_source")],
                "finish": False, "hypotheses": []}
    result = await run_read_only_investigation(
        question="Why did Livingroom Light 2 turn off?",
        mcp=mcp, executor=executor, propose=proposer,
        verified_entity_ids=("7828",), max_rounds=3,
    )
    assert rounds == [0]
    assert not executor.calls
    assert result.stopped_because == "model_read_tools_unavailable"
    assert result.planning_diagnostics[0]["unavailable_model_tool_count"] == 1
    assert "tool not in live MCP manifest" in result.rejected_proposals
