"""v0.18.53 regression: rule 4239 health and variable proof without writes."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from native_rule_evidence_prefetch import (  # noqa: E402
    prefetch_native_rule_evidence, _variables, _verified_health,
)
from evidence_recorder import EvidenceRecorder  # noqa: E402


class FakeMCP:
    def __init__(self, *, fail_health=False, variables=None):
        self.calls = []
        self.fail_health = fail_health
        self.variables = variables if variables is not None else [
            {"name": "TV_Minutes_Used", "type": "Number", "value": "42"},
            {"name": "credential", "type": "String", "value": "privatepassword"},
        ]

    async def call_tool(self, gateway, args):
        self.calls.append((gateway, args))
        assert gateway == "hub_read_rules"
        assert args["args"] == {"appId": "4239"}
        if args["tool"] == "hub_get_rule_health":
            if self.fail_health:
                return SimpleNamespace(is_error=True, data={"error": "not readable"})
            return SimpleNamespace(
                is_error=False, data={
                    "ok": True, "paused": False,
                    "stopped": None, "broken": False,
                    "name": "Internet: Google TV block after 1hr total TV-on time",
                },
            )
        assert args["tool"] == "hub_list_rule_local_variables"
        return SimpleNamespace(
            is_error=False, data={"appId": "4239", "localVariables": self.variables,
                                  "total": len(self.variables)},
        )


@pytest.mark.asyncio
async def test_native_rule_prefetch_reads_only_health_and_owned_variables():
    mcp = FakeMCP()
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        messages = [{"role": "user", "content": "Inspect app 4239"}]
        attempted = await prefetch_native_rule_evidence(
            mcp, evidence, app_id="4239", available_names={"hub_read_rules"},
            messages=messages,
        )
        assert attempted
        assert [(gateway, args["tool"]) for gateway, args in mcp.calls] == [
            ("hub_read_rules", "hub_get_rule_health"),
            ("hub_read_rules", "hub_list_rule_local_variables"),
        ]
        receipts = evidence.receipts()
        assert len(receipts) == 2
        assert all(r["success"] and not r["mutates"] and r["effect"] == "read" for r in receipts)
        assert receipts[0]["details"]["verifiedHealth"] == {
            "paused": False, "broken": False,
        }
        assert receipts[1]["details"]["numericVariables"] == [{
            "name": "TV_Minutes_Used", "type": "Number", "value": 42,
        }]
        assert "TV_Minutes_Used" in messages[-1]["content"]
        assert "privatepassword" not in messages[-1]["content"]
        assert "Local variables belong to their owning app" in messages[-1]["content"]
        assert "does NOT prove" in messages[-1]["content"]
    finally:
        evidence.reset(token)


@pytest.mark.asyncio
async def test_blocked_health_read_is_reported_unknown_not_paused_or_broken():
    mcp = FakeMCP(fail_health=True)
    evidence = EvidenceRecorder()
    token = evidence.begin()
    try:
        messages = []
        assert await prefetch_native_rule_evidence(
            mcp, evidence, app_id="4239", available_names={"hub_read_rules"},
            messages=messages,
        )
        receipts = evidence.receipts()
        assert receipts[0]["success"] is False
        assert receipts[1]["success"] is True
        assert "healthReadFailed" in messages[-1]["content"]
        assert '"paused": false' not in messages[-1]["content"]
    finally:
        evidence.reset(token)


@pytest.mark.asyncio
async def test_unavailable_native_read_gateway_causes_zero_mcp_calls():
    mcp = FakeMCP()
    evidence = EvidenceRecorder()
    messages = []
    assert not await prefetch_native_rule_evidence(
        mcp, evidence, app_id="4239",
        available_names={"hub_read_apps_code"}, messages=messages,
    )
    assert mcp.calls == [] and messages == []


def test_missing_health_booleans_and_nonnumeric_variable_values_not_inferred():
    assert _verified_health({"ok": True, "paused": None, "broken": "false"}) == {}
    variables, parsed = _variables({
        "localVariables": [
            {"name": "SafeNumber", "value": "7", "type": "Number"},
            {"name": "SensitiveString", "value": "secret123"},
            {"name": "Missing"},
        ]
    })
    assert parsed
    assert variables == [
        {"name": "SafeNumber", "type": "Number", "value": 7},
        {"name": "SensitiveString"},
        {"name": "Missing"},
    ]
    assert _variables({"localVariables": {}}) == ([], False)
