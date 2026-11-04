"""Regression: quoted existing Rule Machine reads must not become full inventory."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from automation_status_service import AutomationStatusService
from mcp_client import MCPToolResult
from named_rule_document_read import parse_named_rule_read, read_named_rule_document


PROMPT = (
    'Read the existing Hubitat Rule Machine rule named "One-off block TV". '
    'Find its exact rule ID, then retrieve its native rule document using '
    'operation="read" only. Report the saved trigger type and time, ordered '
    'actions, OFF command, 15-minute wait, ON command, rule health and scheduled '
    'job status. Do not open an edit form, create, execute, pause, delete or '
    'change anything.'
)


class FakeMCP:
    def __init__(self, *, found=True, duplicate=False, failed_read=False):
        self.calls = []
        self.found = found
        self.duplicate = duplicate
        self.failed_read = failed_read

    async def list_tools(self):
        return [SimpleNamespace(name="hub_manage_native_rules_and_apps")]

    async def call_tool(self, gateway, args):
        self.calls.append((gateway, args))
        if gateway == "hub_read_rules":
            rows = [{"id": "4285", "name": "One-off block TV"}] if self.found else []
            if self.duplicate:
                rows.append({"id": "4286", "name": "One-off block TV"})
            data = {"rules": rows, "count": len(rows)}
        else:
            assert gateway == "hub_manage_native_rules_and_apps"
            assert args["tool"] == "hub_set_rule"
            assert args["args"]["operation"] == "read"
            assert args["args"]["rule_id"] == 4285
            assert "confirm" not in args["args"]
            data = {
                "rule_id": 4285,
                "triggers": {"1": "at 8:00 AM"},
                "actions": [
                    {"id": "1", "value": {"method": "getOnOffSwitch"}},
                    {"id": "3", "value": {"method": "getWaitEvents"}},
                    {"id": "4", "value": {"method": "getOnOffSwitch"}},
                ],
                "settings": [
                    {"name": "time1", "type": "enum", "value": "A specific time"},
                    {"name": "atTime1", "type": "time", "value": "08:00"},
                    {"name": "date1", "type": "bool", "value": ""},
                    {"name": "onOff.1", "type": "bool", "value": False},
                    {"name": "onOffSwitch.1", "type": "capability.switch",
                     "value": "unavailable", "device_ids": ["6923"]},
                    {"name": "delayAct.3", "type": "enum", "value": "hrs:min:sec"},
                    {"name": "delayMin.3", "type": "number", "value": 15},
                    {"name": "onOff.4", "type": "bool", "value": True},
                    {"name": "onOffSwitch.4", "type": "capability.switch",
                     "value": "unavailable", "device_ids": ["6923"]},
                    {"name": "secretToken", "type": "text", "value": "do-not-expose"},
                ],
                "conditions": {}, "expressions": {}, "variables": {},
            }
        return MCPToolResult(gateway, args, {}, "", data, is_error=(gateway != "hub_read_rules" and self.failed_read))


def test_exact_quoted_rule_read_preempts_global_status():
    assert parse_named_rule_read(PROMPT) == "One-off block TV"
    assert AutomationStatusService.matches_request(PROMPT) is False
    assert AutomationStatusService.matches_request("List all automations and their status")
    assert parse_named_rule_read("Show me all automations") is None
    assert parse_named_rule_read("Read a rule that seems like One-off block TV") is None


@pytest.mark.asyncio
async def test_named_read_has_exact_id_and_single_native_read():
    mcp = FakeMCP()
    outcome = await read_named_rule_document(mcp, "One-off block TV")
    assert outcome.route == "named-rule-read"
    assert outcome.complete
    assert "4285" in outcome.message
    assert "15 minutes configured" in outcome.message
    assert "Set switch **OFF**" in outcome.message
    assert "Set switch **ON**" in outcome.message
    assert "no dated one-time trigger verified" in outcome.message
    assert "One-off" in outcome.message  # exact name, not temporal proof
    assert "getWaitEvents" not in outcome.message
    assert "secretToken" not in outcome.message
    assert "do-not-expose" not in outcome.message
    assert "delayMin.3" not in outcome.message
    assert len(mcp.calls) == 2
    assert all(x.get("mutates") is False for x in outcome.evidence)
    assert all(x.get("effect") == "read" for x in outcome.evidence)
    assert outcome.evidence[-1]["details"]["projectionVerified"] is True


@pytest.mark.parametrize("missing,duplicate", [(True, False), (False, True)])
@pytest.mark.asyncio
async def test_missing_or_duplicate_name_fails_without_native_read(missing, duplicate):
    mcp = FakeMCP(found=not missing, duplicate=duplicate)
    outcome = await read_named_rule_document(mcp, "One-off block TV")
    assert not outcome.complete
    assert len(mcp.calls) == 1
    assert "won't guess" in outcome.message


@pytest.mark.asyncio
async def test_native_failure_is_reported_without_inventory_substitution():
    mcp = FakeMCP(failed_read=True)
    outcome = await read_named_rule_document(mcp, "One-off block TV")
    assert not outcome.complete
    assert len(mcp.calls) == 2
    assert "Source read NOT VERIFIED" in outcome.message
    assert "165 automation" not in outcome.message
