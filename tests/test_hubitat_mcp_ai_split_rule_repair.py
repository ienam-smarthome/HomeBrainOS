from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import MethodType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_live import LiveRuleTool  # noqa: E402
from automation_rule_workflow_split_repair import (  # noqa: E402
    SplitRepairWashingRuleMachineWorkflow,
    _clean_rule_label,
)
from automation_rule_workflow_washing import _washing_rule_plan  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


def result(name: str, data: Any) -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments={},
        raw={"isError": False},
        text="",
        data=data,
        is_error=False,
    )


def test_html_paused_label_is_normalised_to_exact_rule_name():
    raw = "Washing machine finished notification <span style='color:red'>(Paused)</span>"

    assert _clean_rule_label(raw) == "Washing machine finished notification"


def test_washing_plan_uses_exact_native_power_meter_trigger_capability():
    draft = {
        "type": "washing-complete",
        "name": "Washing machine finished notification",
        "washing_power_device": {"id": 7107, "label": "Washing Machine (MQTT)"},
        "notification_candidates": [{"id": 7485, "label": "SM-S938B"}],
        "unresolved": [],
    }

    plan, error = _washing_rule_plan(draft)

    assert error is None
    assert plan is not None
    assert [trigger["capability"] for trigger in plan["triggers"]] == [
        "Power meter",
        "Power meter",
    ]
    assert plan["triggers"][1]["andStays"] == {"seconds": 180}


def test_combined_population_is_split_into_one_trigger_write_and_short_action_writes():
    service = object.__new__(SplitRepairWashingRuleMachineWorkflow)
    calls: list[dict[str, Any]] = []

    async def fake_write(self, tool, arguments):
        calls.append(dict(arguments))
        return result(tool.name, {"success": True, "partial": False})

    service._idempotent_write = MethodType(fake_write, service)
    tool = LiveRuleTool(
        name="hub_set_rule",
        description="native Rule Machine upsert",
        schema={},
        gateway="hub_manage_rule_machine",
    )
    arguments = {
        "appId": 4154,
        "addTriggers": [
            {
                "capability": "Power meter",
                "deviceIds": [7107],
                "comparator": ">",
                "value": 10,
            },
            {
                "capability": "Power meter",
                "deviceIds": [7107],
                "comparator": "<",
                "value": 5,
                "andStays": {"seconds": 180},
            },
        ],
        "addActions": [
            {"capability": "ifThen", "expression": {"conditions": [], "operator": "AND"}},
            {"capability": "setLocalVariable", "variable": "cycleArmed", "value": 1},
        ],
        "confirm": True,
        "bestPracticeKey": "BP-TEST",
        "opToken": "old-combined-token",
    }

    answer = asyncio.run(service._call_rule_tool(tool, arguments))

    assert answer.is_error is False
    assert answer.data["splitPopulation"] is True
    assert answer.data["phase"] == "complete"
    assert len(calls) == 3
    assert calls[0]["appId"] == 4154
    assert calls[0]["addTriggers"] == arguments["addTriggers"]
    assert "addActions" not in calls[0]
    assert calls[0]["opToken"].startswith("homebrain-rule-4154-")
    assert calls[0]["opToken"].endswith("-triggers")
    assert calls[1]["addAction"] == arguments["addActions"][0]
    assert calls[2]["addAction"] == arguments["addActions"][1]
    assert calls[1]["opToken"].endswith("-create-action-1")
    assert calls[2]["opToken"].endswith("-create-action-2")
    assert all(call["confirm"] is True for call in calls)
    assert all(call["bestPracticeKey"] == "BP-TEST" for call in calls)


def test_matching_rules_finds_all_html_paused_duplicates_and_selects_newest():
    service = object.__new__(SplitRepairWashingRuleMachineWorkflow)

    async def fake_hidden_read(self, tool_name, arguments):
        assert tool_name == "hub_list_rules"
        return (
            result(
                tool_name,
                {
                    "rules": [
                        {
                            "id": 4149,
                            "label": "Washing machine finished notification <span style='color:red'>(Paused)</span>",
                            "name": "Rule-5.1",
                        },
                        {
                            "id": 4154,
                            "label": "Washing machine finished notification <span style='color:red'>(Paused)</span>",
                            "name": "Rule-5.1",
                        },
                        {
                            "id": 4151,
                            "label": "Washing machine finished notification <span style='color:red'>(Paused)</span>",
                            "name": "Rule-5.1",
                        },
                        {"id": 99, "label": "Unrelated rule", "name": "Rule-5.1"},
                    ]
                },
            ),
            {"gateway": "hub_read_rules"},
        )

    service._call_hidden_read = MethodType(fake_hidden_read, service)

    matches, details = asyncio.run(
        service._matching_rules("Washing machine finished notification")
    )

    assert [int(item["id"]) for item in matches] == [4154, 4151, 4149]
    assert all(item["paused"] is True for item in matches)
    assert all(item["name"] == "Washing machine finished notification" for item in matches)
    assert details["match_count"] == 3


def test_release_installs_health_verified_repair_workflow():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "version: '0.4.35-alpha'" in config
    assert 'PREVIOUS_RELEASE_VERSION = "0.4.34-alpha"' in entrypoint
    assert 'RELEASE_VERSION = "0.4.35-alpha"' in entrypoint
    assert "install_repair_id_safe_rule_machine_workflow" in entrypoint
