from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_recommendation_webui import (  # noqa: E402
    install_automation_recommendation_webui,
)
from automation_rule_workflow import (  # noqa: E402
    AutomationRuleWorkflow,
    install_automation_rule_workflow,
)
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def tool_result(name: str, data: Any, *, error: bool = False, text: str = "") -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments={},
        raw=data if isinstance(data, dict) else {"data": data},
        text=text,
        data=data,
        is_error=error,
    )


class FakeClient:
    def __init__(
        self,
        *,
        existing: list[dict[str, Any]] | None = None,
        safe_create: bool = True,
    ) -> None:
        self.existing = list(existing or [])
        self.safe_create = safe_create
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool(
                name="hub_manage_rules",
                description=(
                    "Gateway for hub_create_visual_rule, hub_run_rule, "
                    "hub_resume_rule and hub_pause_rule."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                    },
                },
            )
        ]

    async def gateway_map(self, refresh: bool = False):
        return {
            "hub_create_visual_rule": "hub_manage_rules",
            "hub_run_rule": "hub_manage_rules",
            "hub_resume_rule": "hub_manage_rules",
            "hub_pause_rule": "hub_manage_rules",
        }

    def _catalogue(self):
        create_properties = {
            "name": {"type": "string"},
            "rule": {"type": "object"},
        }
        create_required = ["name", "rule"]
        if self.safe_create:
            create_properties.update(
                {
                    "paused": {"type": "boolean"},
                    "enabled": {"type": "boolean"},
                }
            )
            create_required.append("paused")
        return {
            "gateway": "hub_manage_rules",
            "mode": "catalog",
            "tools": [
                {
                    "name": "hub_create_visual_rule",
                    "description": "Create a Visual Rules Builder rule.",
                    "inputSchema": {
                        "type": "object",
                        "properties": create_properties,
                        "required": create_required,
                    },
                },
                {
                    "name": "hub_run_rule",
                    "description": "Run one rule once.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"ruleId": {"type": "string"}},
                        "required": ["ruleId"],
                    },
                },
                {
                    "name": "hub_resume_rule",
                    "description": "Resume a paused rule.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"ruleId": {"type": "string"}},
                        "required": ["ruleId"],
                    },
                },
                {
                    "name": "hub_pause_rule",
                    "description": "Pause a rule.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"ruleId": {"type": "string"}},
                        "required": ["ruleId"],
                    },
                },
            ],
        }

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_manage_rules" and not args:
            return tool_result(name, self._catalogue())
        if name == "hub_list_rules":
            return tool_result(name, {"rules": list(self.existing)})
        if name == "hub_create_visual_rule":
            created = {
                "id": "501",
                "name": args.get("name") or "Created rule",
                "status": "Paused",
                "paused": True,
                "enabled": False,
            }
            self.existing.append(created)
            return tool_result(name, {"rule": created})
        if name == "hub_run_rule":
            return tool_result(name, {"success": True, "run": True})
        if name == "hub_resume_rule":
            return tool_result(name, {"success": True, "status": "Active"})
        if name == "hub_pause_rule":
            return tool_result(name, {"success": True, "status": "Paused"})
        return tool_result(name, {}, error=True, text=f"Unexpected tool {name}")


class FakeIndex:
    async def exact_device(self, label: str):
        return (
            {
                "id": "77",
                "label": label,
                "room": "Appliances",
                "currentStates": {"contact": "closed"},
            },
            [],
        )


RECOMMENDATION = {
    "type": "cold-storage-door",
    "title": "Fridge Door left-open alert",
    "room": "Appliances",
    "devices": ["Fridge Door"],
    "trigger": "Trigger when Fridge Door remains open for 2 minutes.",
    "action": "Send a high-priority phone notification and repeat once after 5 minutes if it is still open.",
    "safeguard": "Cancel all pending alerts immediately when the contact closes.",
    "reason": "Prevent wasted energy and food warming.",
}


def make_service(*, existing=None, safe_create=True):
    client = FakeClient(existing=existing, safe_create=safe_create)
    app = SimpleNamespace(mcp=client, VERSION="0.4.21-alpha")
    service = AutomationRuleWorkflow(app, FakeIndex())
    return service, client


async def remember(service: AutomationRuleWorkflow, session: str = "phone"):
    return await service.store.remember(session, RECOMMENDATION)


def request(query: str, session: str = "phone"):
    return SimpleNamespace(query=query, session_id=session)


def test_build_compiles_paused_draft_without_writing():
    service, client = make_service()

    async def run():
        await remember(service)
        return await service.handle(request("Build this rule"), "build")

    answer = asyncio.run(run())

    assert answer["success"] is True
    assert answer["intent"] == "automation-rule-draft"
    assert answer["write_ready"] is True
    assert answer["rule_draft"]["enabled"] is False
    assert answer["rule_draft"]["paused"] is True
    assert answer["rule_draft"]["trigger"]["duration_seconds"] == 120
    assert answer["display"]["actions"][0]["query"] == "Create this rule"
    writes = [name for name, _ in client.calls if name.startswith("hub_create_")]
    assert writes == []


def test_create_requires_built_draft_and_sends_paused_arguments():
    service, client = make_service()

    async def run():
        await remember(service)
        blocked = await service.handle(request("Create this rule"), "create")
        await service.handle(request("Build this rule"), "build")
        created = await service.handle(request("Create this rule"), "create")
        return blocked, created

    blocked, created = asyncio.run(run())

    assert blocked["success"] is False
    assert "Build this rule first" in blocked["message"]
    assert created["success"] is True
    assert created["intent"] == "automation-rule-created"
    create_calls = [args for name, args in client.calls if name == "hub_create_visual_rule"]
    assert len(create_calls) == 1
    assert create_calls[0]["paused"] is True
    assert create_calls[0]["enabled"] is False
    assert create_calls[0]["rule"]["trigger"]["device"]["id"] == "77"


def test_existing_named_rule_blocks_duplicate_write():
    service, client = make_service(
        existing=[
            {
                "id": "99",
                "name": "Fridge Door left-open alert",
                "status": "Paused",
                "paused": True,
            }
        ]
    )

    async def run():
        await remember(service)
        await service.handle(request("Build this rule"), "build")
        return await service.handle(request("Create this rule"), "create")

    answer = asyncio.run(run())

    assert answer["intent"] == "automation-rule-duplicate"
    assert [name for name, _ in client.calls if name == "hub_create_visual_rule"] == []


def test_test_enable_and_pause_are_separate_explicit_operations():
    service, client = make_service()

    async def run():
        await remember(service)
        await service.handle(request("Build this rule"), "build")
        await service.handle(request("Create this rule"), "create")
        tested = await service.handle(request("Run test once"), "test")
        enabled = await service.handle(request("Enable this rule"), "enable")
        paused = await service.handle(request("Pause this rule"), "pause")
        return tested, enabled, paused

    tested, enabled, paused = asyncio.run(run())

    assert tested["intent"] == "automation-rule-tested"
    assert enabled["intent"] == "automation-rule-enabled"
    assert paused["intent"] == "automation-rule-paused"
    names = [name for name, _ in client.calls]
    assert "hub_run_rule" in names
    assert "hub_resume_rule" in names
    assert "hub_pause_rule" in names


def test_unsafe_create_schema_is_review_only():
    service, client = make_service(safe_create=False)

    async def run():
        await remember(service)
        built = await service.handle(request("Build this rule"), "build")
        create = await service.handle(request("Create this rule"), "create")
        return built, create

    built, create = asyncio.run(run())

    assert built["write_ready"] is False
    assert all(item["query"] != "Create this rule" for item in built["display"]["actions"])
    assert "paused or disabled" in built["message"]
    assert create["success"] is False
    assert [name for name, _ in client.calls if name == "hub_create_visual_rule"] == []


def test_recommendation_wrapper_adds_build_action_and_remembers_per_session():
    client = FakeClient()

    async def original_ask(req):
        return {
            "success": True,
            "route": "mcp-automation-recommendation",
            "message": "Recommendation",
            "recommendation": dict(RECOMMENDATION),
            "display": {"title": RECOMMENDATION["title"], "note": "Review only"},
        }

    app = SimpleNamespace(
        mcp=client,
        VERSION="0.4.21-alpha",
        ask=original_ask,
    )
    service = install_automation_rule_workflow(app, FakeIndex())

    answer = asyncio.run(app.ask(request("Suggest one useful automation")))
    pending = asyncio.run(service.store.get("phone"))

    assert answer["display"]["actions"][0]["query"] == "Build this rule"
    assert pending is not None
    assert pending.recommendation["title"] == RECOMMENDATION["title"]


def test_rule_action_renderer_and_release_metadata():
    class Module:
        @staticmethod
        def patch_page(page: str) -> str:
            return page

    install_automation_recommendation_webui(Module)
    page = Module.patch_page(
        "<style></style>"
        "<button class=\"secondary\" data-q=\"What can Ollama help with?\">🤖 AI question guide</button>"
        "function routeLabel(route){const labels={'error':'Error'}}"
        "if(answer.display.note)output.appendChild(el('div','mini',answer.display.note));"
        "if(answer.message&&!answer.display.metrics?.length&&!answer.display.items?.length)"
    )
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (
        ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"
    ).read_text(encoding="utf-8")

    assert "function ruleActionButtons(items)" in page
    assert "submit(query)" in page
    assert "workflowActions" in page
    assert 'return box}"' not in page
    assert "version: '0.4.21-alpha'" in config
    assert 'RELEASE_VERSION = "0.4.21-alpha"' in entrypoint
    assert "install_washing_rule_machine_workflow" in entrypoint
