"""Live regression: native Hubitat rule exists despite confirmed write ReadTimeout.

The confirmed 2026-10-22 hub_set_rule call timed out after ~25s, but the
user's Hubitat Rule Machine screenshot visibly shows the six saved triggers
and seven actions. Never auto-retry an ambiguous confirmed mutation.
"""
from __future__ import annotations

import sys
from pathlib import Path
import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from confirmation_policy import ConfirmationPolicy
from confirmation_store import PendingConfirmation
from confirmed_action_coordinator import ConfirmedActionCoordinator
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from request_outcome_policy import classify_completed_request
from tool_catalog_assembly import build_request_tool_catalog
from tool_executor import ToolExecution
from tool_registry import ToolEffect


GATEWAY = "hub_manage_rule_machine"
RULE_NAME = "Livingroom Light 1 – Night Idle OFF – TEST"
def proposal(name=RULE_NAME):
    return {"tool": "hub_set_rule", "args": {
        "name": name, "addAction": {
            "capability": "runCommand",
            "command": "off",
            "deviceIds": ["7805"],
            "capabilityFilter": "Switch",
        }
    }}


def outcome(name, args, *, success, data=None, error=None):
    result = (MCPToolResult(name, args, {}, "", data)
              if data is not None else None)
    return ToolExecution(
        name=name, arguments=args,
        effect=ToolEffect.SENSITIVE_WRITE if name == GATEWAY else ToolEffect.READ,
        success=success, elapsed_ms=25008 if error is not None else 200,
        content="", result=result, error=error,
    )


class ReconcileExecutor:
    def __init__(self, *, inventory=None, read_success=True, error=None):
        self.calls = []
        self.inventory = inventory if inventory is not None else {
            "rules": [{"id": 4273, "name": RULE_NAME}]
        }
        self.read_success = read_success
        self.error = error or httpx.ReadTimeout("")
    async def execute(self, name, args, **kwargs):
        self.calls.append((name, args, kwargs))
        if name == GATEWAY:
            return outcome(name, args, success=False, error=self.error)
        if name == "hub_read_rules":
            return outcome(name, args, success=self.read_success,
                           data=self.inventory)
        raise AssertionError(f"Unexpected operation: {name}")


def catalog():
    return build_request_tool_catalog([
        MCPTool(GATEWAY, GATEWAY, {"type": "object"}),
        MCPTool("hub_read_rules", "read", {"type": "object"}),
    ])


def pending(*proposals):
    return PendingConfirmation(
        expires_at=500.0,
        actions=[(GATEWAY, p) for p in proposals],
        messages=[{"role": "user", "content": "create active TEST"}],
        assistant_message={"role": "assistant", "content": "Confirm creation"},
    )


async def no_model(*_a, **_kw):
    raise AssertionError("Read-only reconciliation must not invoke LLM")


@pytest.mark.asyncio
async def test_timeout_found_one_exact_rule_reports_real_presence_without_second_write():
    executor = ReconcileExecutor()
    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True), executor, no_model, lambda: None,
    )
    report = await coordinator.resume(
        pending(proposal(RULE_NAME), proposal("Another rule")), catalog(),
    )
    assert "**Read-only Rule Machine lookup FOUND**" in report
    assert "appId: 4273" in report
    assert RULE_NAME in report
    assert "not** that the timed-out write" in report
    assert "Do not retry" in report or "Do not retry" in report.lower().capitalize()
    assert [x[0] for x in executor.calls] == [GATEWAY, "hub_read_rules"]
    assert executor.calls[0][1]["args"]["confirm"] is True
    assert executor.calls[1][2]["mutates"] is False
    assert executor.calls[1][2]["evidence_kind"] == "rule_create_timeout_reconciliation"


@pytest.mark.asyncio
@pytest.mark.parametrize("inventory,expected", [
    ({"rules": []}, "outcome remains UNKNOWN"),
    ({"gateway": "native", "mode": "discovery", "tools": []},
     "could not retrieve a complete rules list"),
    ({"rules": [{"name": RULE_NAME}, {"name": RULE_NAME}]},
     "2 matching rules"),
])
async def test_timeout_not_found_ambiguous_or_metadata_never_repeats_write(inventory, expected):
    executor = ReconcileExecutor(inventory=inventory)
    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True), executor, no_model, lambda: None,
    )
    report = await coordinator.resume(pending(proposal()), catalog())
    assert expected in report
    assert "Do not retry" in report or "**Do not retry" in report
    assert [x[0] for x in executor.calls] == [GATEWAY, "hub_read_rules"]


@pytest.mark.asyncio
async def test_non_transport_explicit_rejection_does_not_claim_found_or_lookup():
    executor = ReconcileExecutor(error=ValueError("native rule refused"))
    coordinator = ConfirmedActionCoordinator(
        ConfirmationPolicy(enabled=True), executor, no_model, lambda: None,
    )
    report = await coordinator.resume(pending(proposal()), catalog())
    assert "not verified" in report
    assert [x[0] for x in executor.calls] == [GATEWAY]


def rpc(name=GATEWAY, *, confirmed=True, app_id=None):
    args = {"name": RULE_NAME, "confirm": confirmed}
    if app_id is not None:
        args["appId"] = app_id
    return {
        "jsonrpc": "2.0", "id": 12, "method": "tools/call",
        "params": {
            "name": name,
            "arguments": {"tool": "hub_set_rule", "args": args},
        }
    }


def test_only_exact_confirmed_new_rule_is_eligible_for_longer_read_timeout():
    assert HubitatMCPClient._confirmed_rule_creation_request(rpc())
    assert not HubitatMCPClient._confirmed_rule_creation_request(rpc(confirmed=False))
    assert not HubitatMCPClient._confirmed_rule_creation_request(rpc(app_id=4273))
    assert not HubitatMCPClient._confirmed_rule_creation_request(rpc(name="hub_read_rules"))
    other = rpc()
    other["params"]["arguments"]["tool"] = "hub_set_rule_paused"
    assert not HubitatMCPClient._confirmed_rule_creation_request(other)


@pytest.mark.asyncio
async def test_read_timeout_extended_only_for_approved_rule_create():
    class CaptureHTTP:
        def __init__(self):
            self.calls = []
        async def post(self, url, **kwargs):
            self.calls.append(kwargs)
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 12, "result": {}})
    mcp = HubitatMCPClient("http://127.0.0.1:9000")
    await mcp._http.aclose()
    fake = CaptureHTTP()
    mcp._http = fake
    await mcp._post(rpc())
    assert len(fake.calls) == 1
    timeout = fake.calls[0]["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.read >= 90
    assert timeout.connect == mcp.timeout_seconds
    await mcp._post(rpc(confirmed=False))
    assert len(fake.calls) == 2
    assert "timeout" not in fake.calls[1]


def test_reconciled_timeout_is_unresolved_not_failed_or_success():
    assert classify_completed_request({
        "mutation_verification_failures": 1,
        "rule_create_timeout_found": 1,
    }) == "unresolved"
    assert classify_completed_request({
        "mutation_verification_failures": 1,
        "rule_create_timeout_unknown": 1,
    }) == "unresolved"
    assert classify_completed_request({
        "mutation_verification_failures": 1,
    }) == "failed"
