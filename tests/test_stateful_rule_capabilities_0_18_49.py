"""0.18.49 Rule Machine authoring: live schema preflight and structure guards."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from stateful_rule_capabilities import (  # noqa: E402
    inspect_stateful_rule_capabilities,
    cumulative_rule_proposal_error,
)


class FakeMCP:
    def __init__(self, missing=()):
        self.missing = set(missing)
        self.called = []

    async def call_tool(self, name, arguments):
        assert name == "hub_get_tool_guide"  # no writes, not even probes
        section = arguments["section"]
        self.called.append((name, section))
        content = {
            "set_rule_reference_triggers": "Device-state Switch trigger; Periodic Schedule everyN Minutes",
            "set_rule_reference_actions": (
                "setVariable add number; setLocalVariable; "
                "ifThen; elseIf; else; endIf; switch action off"
            ),
            "set_rule_reference_conditions": "Variable expressions and nested comparators",
            "variables": "Hub Variable Number and Decimal configuration",
        }.get(section, "")
        return SimpleNamespace(
            is_error=section in self.missing,
            data={"success": section not in self.missing, "content": content},
        )


@pytest.mark.asyncio
async def test_preflight_only_reads_exact_live_capability_sections():
    mcp = FakeMCP()
    receipts = []
    preflight = await inspect_stateful_rule_capabilities(
        mcp, lambda *a, **kw: receipts.append((a, kw)),
        frozenset({"hub_get_tool_guide", "hub_manage_rule_machine"}),
    )
    assert preflight.ready
    assert len(mcp.called) == 4
    assert all(name == "hub_get_tool_guide" for name, section in mcp.called)
    assert len(receipts) == 4
    assert all(row[1]["evidence_kind"] == "stateful_rule_capability_reference" for row in receipts)
    assert "native" in preflight.instruction.casefold()
    assert "confirmation" in preflight.instruction
    assert "Do not pause, edit, delete" in preflight.instruction


@pytest.mark.asyncio
async def test_missing_guide_does_not_claim_rule_machine_is_impossible():
    mcp = FakeMCP(missing={"set_rule_reference_actions"})
    preflight = await inspect_stateful_rule_capabilities(
        mcp, lambda *a, **kw: None,
        {"hub_get_tool_guide", "hub_manage_rule_machine"},
    )
    assert not preflight.ready
    assert "set_rule_reference_actions" in preflight.missing
    assert "No automation was created or queued" in preflight.instruction
    assert "has not positively established" in preflight.instruction


@pytest.mark.asyncio
async def test_no_write_gateway_aborts_without_any_mcp_calls():
    mcp = FakeMCP()
    preflight = await inspect_stateful_rule_capabilities(
        mcp, lambda *a, **kw: None, {"hub_get_tool_guide"}
    )
    assert not preflight.ready
    assert "hub_manage_rule_machine" in preflight.missing
    assert mcp.called == []


def valid_rule():
    return {
        "tool": "hub_set_rule",
        "args": {
            "name": "TV cumulative allowance - separate from old rule",
            "addTriggers": [
                {"capability": "Periodic Schedule", "periodic": {
                    "frequency": "Minutes", "everyN": 1}},
                {"capability": "Switch", "deviceIds": ["6923"], "state": "off"},
            ],
            "addLocalVariable": {"name": "TV_Minutes_Used", "type": "Number", "value": 0},
            "addActions": [
                {"capability": "ifThen", "expression": {"conditions": [
                    {"capability": "Switch", "deviceIds": ["6923"], "state": "off"}]}},
                {"capability": "setLocalVariable", "variable": "TV_Minutes_Used", "value": 0},
                {"capability": "elseIf", "expression": {"conditions": [
                    {"capability": "Switch", "deviceIds": ["4221"], "state": "on"}]}},
                {"capability": "setLocalVariable", "variable": "TV_Minutes_Used",
                 "numOp": "add number", "value": 1},
                {"capability": "ifThen", "expression": {"conditions": [
                    {"capability": "Variable", "variable": "TV_Minutes_Used",
                     "comparator": ">=", "value": 60}]}},
                {"capability": "switch", "deviceIds": ["6923"], "action": "off"},
                {"capability": "endIf"},
                {"capability": "endIf"},
            ],
        },
    }


def test_complete_typed_reference_rule_passes_structural_review():
    assert cumulative_rule_proposal_error(valid_rule()) is None


@pytest.mark.parametrize("modify,expected", [
    (lambda p: p["addTriggers"].pop(0), "periodic"),
    (lambda p: p["addTriggers"].pop(1), "switch-OFF"),
    (lambda p: p["addActions"].pop(), "Unclosed"),
    (lambda p: p["addActions"].pop(3), "arithmetic"),
    (lambda p: p["addActions"].pop(1), "zero reset"),
    (lambda p: p["addActions"].pop(5), "OFF action"),
    (lambda p: p.update(appId="3985"), "must not edit"),
])
def test_incomplete_or_existing_rule_proposals_blocked(modify, expected):
    proposal = valid_rule()
    modify(proposal["args"])
    assert expected in cumulative_rule_proposal_error(proposal)


def test_malformed_proposal_fails_closed_without_readable_schema():
    assert "structured" in cumulative_rule_proposal_error({"tool": "hub_set_rule", "args": None})
    assert cumulative_rule_proposal_error({"tool": "hub_get_rule"}) is None
