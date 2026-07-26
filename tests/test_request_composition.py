from __future__ import annotations

import asyncio
import ast
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import mcp_agent_orchestrator as orchestrator  # noqa: E402
from request_composition import AskLayer, compose_ask_layers  # noqa: E402


def test_compose_ask_layers_declares_and_preserves_order():
    calls: list[str] = []

    async def base(_request):
        calls.append("legacy")
        return {"route": "legacy"}

    def layer(name: str) -> AskLayer:
        def factory(next_handler):
            async def handler(request):
                calls.append(f"{name}:before")
                answer = await next_handler(request)
                calls.append(f"{name}:after")
                return answer

            return handler

        return AskLayer(name, factory)

    handler = compose_ask_layers(
        base,
        layer("control-agent"),
        layer("unified-mcp-agent"),
    )
    answer = asyncio.run(handler(SimpleNamespace(query="status")))

    assert answer == {"route": "legacy"}
    assert calls == [
        "unified-mcp-agent:before",
        "control-agent:before",
        "legacy",
        "control-agent:after",
        "unified-mcp-agent:after",
    ]
    assert handler.__homebrain_ask_layers__ == (
        "unified-mcp-agent",
        "control-agent",
        "legacy-route-stack",
    )


def test_unified_builder_does_not_mutate_application(monkeypatch):
    async def legacy(request):
        return {"route": "legacy", "query": request.query}

    application = SimpleNamespace(ask=legacy, VERSION="test")
    monkeypatch.setattr(orchestrator, "should_use_unified_agent", lambda _query: False)

    handler = orchestrator.build_unified_mcp_agent_handler(application, legacy)

    assert application.ask is legacy
    assert asyncio.run(handler(SimpleNamespace(query="status"))) == {
        "route": "legacy",
        "query": "status",
    }


def test_live_entrypoint_uses_explicit_composition_not_orchestrator_installer():
    source = (APP_DIR / "entrypoint_core.py").read_text(encoding="utf-8")

    assert "legacy_request_layer = application.ask" in source
    assert "unified_agent_layer = AskLayer(" in source
    assert "application.ask = compose_ask_layers(" in source
    assert "install_unified_mcp_agent_orchestrator(application)" not in source


def test_unified_builder_has_no_application_ask_assignment():
    tree = ast.parse(
        (APP_DIR / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    )
    builder = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_unified_mcp_agent_handler"
    )

    assignments = [
        node
        for node in ast.walk(builder)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "application"
            and target.attr == "ask"
            for target in node.targets
        )
    ]
    assert assignments == []
