from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_repair_id_safe import (  # noqa: E402
    RepairIdSafeWashingRuleMachineWorkflow,
)
from automation_rule_workflow_split_repair import _REPAIR_RE  # noqa: E402
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


def service() -> RepairIdSafeWashingRuleMachineWorkflow:
    app = SimpleNamespace(mcp=SimpleNamespace(), VERSION="test")
    return RepairIdSafeWashingRuleMachineWorkflow(app, object())


def test_health_verifies_rule_4155_from_rendered_label_not_generic_type_name():
    item = service()

    async def fake_hidden_read(self, tool_name, arguments):
        assert tool_name == "hub_get_rule_health"
        assert arguments == {"appId": 4155, "source": "auto"}
        return (
            result(
                tool_name,
                {
                    "ok": True,
                    "unreadable": False,
                    "ruleFormat": "rm",
                    "label": "Washing machine finished notification <span style='color:red'>(Paused)</span>",
                },
            ),
            {"request_tool": "hub_manage_native_rules_and_apps"},
        )

    item._call_hidden_read = MethodType(fake_hidden_read, item)

    row, details = asyncio.run(
        item._health_verified_rule(4155, "Washing machine finished notification")
    )

    assert row is not None
    assert row["id"] == 4155
    assert row["name"] == "Washing machine finished notification"
    assert row["paused"] is True
    assert details["clean_label"] == "Washing machine finished notification"


def test_generic_rule_list_falls_back_to_health_labels_and_finds_newest_match():
    item = service()
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_hidden_read(self, tool_name, arguments):
        calls.append((tool_name, dict(arguments)))
        if tool_name == "hub_list_rules":
            return (
                result(
                    tool_name,
                    {
                        "rules": [
                            {"id": 4154, "name": "Rule-5.1"},
                            {"id": 4155, "name": "Rule-5.1"},
                            {"id": 4000, "name": "Rule-5.1"},
                        ]
                    },
                ),
                {"request_tool": "hub_read_rules"},
            )
        if tool_name == "hub_get_rule_health":
            app_id = int(arguments["appId"])
            label = (
                "Washing machine finished notification <span style='color:red'>(Paused)</span>"
                if app_id in {4154, 4155}
                else "Unrelated rule <span style='color:red'>(Paused)</span>"
            )
            return (
                result(
                    tool_name,
                    {
                        "ok": True,
                        "unreadable": False,
                        "ruleFormat": "rm",
                        "label": label,
                    },
                ),
                {"request_tool": "hub_manage_native_rules_and_apps"},
            )
        raise AssertionError(tool_name)

    item._call_hidden_read = MethodType(fake_hidden_read, item)

    matches, details = asyncio.run(
        item._matching_rules("Washing machine finished notification")
    )

    assert [match["id"] for match in matches] == [4155, 4154]
    assert all(match["paused"] is True for match in matches)
    assert details["health_label_fallback"]["match_count"] == 2
    assert any(name == "hub_get_rule_health" for name, _ in calls)


def test_repair_command_and_installer_dispatch_rule_4155():
    match = _REPAIR_RE.fullmatch("Repair rule 4155")
    source = (APP_DIR / "automation_rule_workflow_repair_id_safe.py").read_text(
        encoding="utf-8"
    )

    assert match is not None
    assert match.group(1) == "4155"
    assert "repair_match = _REPAIR_RE.fullmatch(query)" in source
    assert "answer = await service.repair(request, requested)" in source


def test_release_uses_id_safe_repair_workflow():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "install_repair_id_safe_rule_machine_workflow" in entrypoint
