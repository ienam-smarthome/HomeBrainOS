from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from answer_guard_registry import AnswerGuardRegistry
from named_rule_status_route import build_named_rule_status_terminal_route


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def run(coro):
    return asyncio.run(coro)


def test_named_rule_status_route_delegates_unmatched_queries_without_mcp_read():
    class Controller:
        class MCP:
            async def call_tool(self, name, arguments):
                raise AssertionError("unmatched query must not read rules")

        mcp = MCP()

    route = build_named_rule_status_terminal_route(Controller())

    assert run(route(SimpleNamespace(query="turn on the lamp"))) is None


def test_named_rule_status_route_runs_as_registry_terminal_route():
    class Result:
        is_error = False
        data = {
            "rules": [
                {"id": 42, "name": "Night lights", "disabled": False, "paused": False}
            ]
        }

    class Controller:
        class MCP:
            async def call_tool(self, name, arguments):
                assert name == "hub_list_rules"
                return Result()

        mcp = MCP()

        @staticmethod
        def _rule_rows(data):
            return [{"id": 42, "name": "Night lights"}]

        @staticmethod
        def _exact_matches(rules, intent):
            return rules

        @staticmethod
        def _possible_matches(rules, intent):
            return []

    async def base(request):
        raise AssertionError("matched status query must be terminal")

    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)
    registry.register_terminal_route(
        "named-rule-status",
        build_named_rule_status_terminal_route(Controller()),
    )
    handler = registry.install()

    answer = run(handler(SimpleNamespace(query="status of Night lights rule")))

    assert answer["route"] == "mcp-rule-status"
    assert answer["rule"]["id"] == 42
    assert answer["rule"]["disabled"] is False
    assert answer["rule"]["paused"] is False


def test_public_entrypoint_uses_named_rule_status_registry_at_same_position():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "from named_rule_status_route import build_named_rule_status_terminal_route" in source
    assert 'register_terminal_route(\n    "named-rule-status",' in source
    assert '"named-rule-status-registry",\n    named_rule_status_registry.install,' in source
    assert "install_named_rule_status_route" not in source
    assert source.index("climate-extrema-registry") < source.index("named-rule-status-registry")
    assert source.index("named-rule-status-registry") < source.index("answer-guard-registry")
