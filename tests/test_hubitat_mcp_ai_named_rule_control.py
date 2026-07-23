from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from named_rule_control import install_named_rule_controller, parse_named_rule_intent  # noqa: E402


def result(name: str, data: Any, *, error: bool = False) -> MCPToolResult:
    return MCPToolResult(name=name, arguments={}, raw={}, text="error" if error else "", data=data, is_error=error)


class FakeMCP:
    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        self.rules = rules or [
            {"id": 2967, "label": "Appliance: Fridge door left door", "rmVersion": "5.x"},
            {"id": 2844, "label": "Appliance: Fridge and Freezer - Auto ON", "rmVersion": "5.x"},
        ]
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool("hub_read_rules", "hub_list_rules", {}),
            MCPTool(
                "hub_manage_rule_machine",
                "hub_call_rule hub_set_rule_paused hub_set_rule_private_boolean",
                {},
            ),
        ]

    async def gateway_map(self, refresh: bool = False):
        return {
            "hub_list_rules": "hub_read_rules",
            "hub_call_rule": "hub_manage_rule_machine",
            "hub_set_rule_paused": "hub_manage_rule_machine",
        }

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_list_rules":
            return result(name, {"rules": self.rules})
        if name == "hub_set_rule_paused":
            return result(name, {"success": True, "ruleId": args["ruleId"], "paused": args["paused"]})
        if name == "hub_call_rule":
            return result(name, {"success": True, "ruleId": args["ruleId"], "action": args["action"]})
        raise AssertionError(f"Unexpected tool call: {name} {args}")


def application(client: FakeMCP):
    async def fallback(_request: Any):
        return {"success": True, "route": "fallback", "message": "fallback"}

    app = SimpleNamespace(mcp=client, ask=fallback, VERSION="0.10.9")
    install_named_rule_controller(app)
    return app


def ask(app: Any, query: str):
    return asyncio.run(app.ask(SimpleNamespace(query=query, session_id="test")))


def test_parser_accepts_requested_actions_and_rejects_non_rule_questions():
    for action in ("pause", "resume", "enable", "disable", "run", "stop"):
        intent = parse_named_rule_intent(f"{action} Appliance: Fridge door left door rule")
        assert intent is not None
        assert intent.action == action
        assert "appliance fridge door left door" in intent.variants

    assert parse_named_rule_intent("is Appliance: Fridge door left door paused?") is None
    assert parse_named_rule_intent("list active automation rules") is None


def test_pause_exact_name_with_optional_rule_suffix_needs_no_choice():
    client = FakeMCP()
    answer = ask(application(client), "pause Appliance: Fridge door left door rule")

    assert answer["success"] is True
    assert answer["route"] == "mcp-rule-control"
    assert answer["intent"] == "automation-rule-pause-verified"
    assert client.calls == [
        ("hub_list_rules", {}),
        ("hub_set_rule_paused", {"ruleId": 2967, "paused": True}),
    ]


def test_enable_disable_and_resume_map_to_idempotent_pause_tool():
    expected = {"disable": True, "enable": False, "resume": False}
    for action, paused in expected.items():
        client = FakeMCP()
        answer = ask(application(client), f"{action} rule Appliance: Fridge door left door")
        assert answer["success"] is True
        assert client.calls[-1] == ("hub_set_rule_paused", {"ruleId": 2967, "paused": paused})


def test_run_and_stop_use_distinct_rule_machine_actions():
    for action, mcp_action in (("run", "rule"), ("stop", "stop")):
        client = FakeMCP()
        answer = ask(application(client), f"{action} automation Appliance: Fridge door left door")
        assert answer["success"] is True
        assert client.calls[-1] == ("hub_call_rule", {"ruleId": 2967, "action": mcp_action})


def test_rule_id_resolves_without_name_matching():
    client = FakeMCP()
    answer = ask(application(client), "pause rule id 2967")

    assert answer["success"] is True
    assert client.calls[-1] == ("hub_set_rule_paused", {"ruleId": 2967, "paused": True})


def test_partial_or_missing_name_never_executes_a_write():
    client = FakeMCP()
    answer = ask(application(client), "pause Fridge")

    assert answer["success"] is False
    assert answer["route"] == "mcp-rule-clarification"
    assert [name for name, _ in client.calls] == ["hub_list_rules"]
    assert "Possible rules" in answer["message"]


def test_duplicate_exact_labels_require_rule_id_and_do_not_write():
    client = FakeMCP(
        [
            {"id": 1, "label": "Duplicate Rule"},
            {"id": 2, "label": "Duplicate Rule"},
        ]
    )
    answer = ask(application(client), "pause Duplicate Rule")

    assert answer["success"] is False
    assert [name for name, _ in client.calls] == ["hub_list_rules"]
    assert "Rule ID 1" in answer["message"]
    assert "Rule ID 2" in answer["message"]


def test_unrelated_queries_continue_to_the_existing_assistant():
    client = FakeMCP()
    answer = ask(application(client), "what is the fridge temperature?")

    assert answer["route"] == "fallback"
    assert client.calls == []


def test_device_like_action_with_no_rule_match_returns_to_existing_assistant():
    client = FakeMCP()
    answer = ask(application(client), "stop Roborock")

    assert answer["route"] == "fallback"
    assert client.calls == [("hub_list_rules", {})]

def test_resume_uses_write_response_as_verified_confirmation():
    client = FakeMCP()
    answer = ask(application(client), "resume rule Appliance: Fridge and Freezer - Auto ON")

    assert answer["success"] is True
    assert answer["intent"] == "automation-rule-resume-verified"
    assert "Rule resumed" in answer["message"]
    assert "paused: false" in answer["message"]
    assert answer["display"]["title"] == "Rule resumed"
    assert answer["display"]["subtitle"] == "Confirmed by the hub_set_rule_paused response."
    assert '"command_verified": true' in answer["technical"]
    assert '"verification_source": "hub_set_rule_paused response"' in answer["technical"]
    assert '"post_state_verified": true' in answer["technical"]
    assert '"inventory_readback_verified": false' in answer["technical"]


def test_pause_uses_write_response_as_verified_confirmation():
    client = FakeMCP()
    answer = ask(application(client), "pause rule Appliance: Fridge door left door")

    assert answer["intent"] == "automation-rule-pause-verified"
    assert "Rule paused" in answer["message"]
    assert "paused: true" in answer["message"]
    assert answer["display"]["title"] == "Rule paused"

