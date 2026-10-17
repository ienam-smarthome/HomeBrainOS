"""Model-visible source evidence tools; no canned source finalization."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from groovy_source_investigation import (
    _source_operations, requested_groovy_app_id, GroovySourceReport,
)
from tool_catalog_assembly import build_request_tool_catalog
from tool_registry import LOCAL_GROOVY_SOURCE_TOOL
from mcp_agent_orchestrator import UnifiedMCPAgent
from mcp_client import MCPTool


PROMPT = (
    "Inspect the Groovy source code for Livingroom Light 1 automation "
    "(app 4019), show motionOffLockoutMinutes getter and state.motionLockout. "
    "Read-only."
)


def test_source_tool_is_available_but_not_a_generic_forced_shortcut():
    catalog = build_request_tool_catalog([])
    assert requested_groovy_app_id(PROMPT) == "4019"
    assert catalog.available_tool(LOCAL_GROOVY_SOURCE_TOOL) is not None
    assert catalog.declared_tool(LOCAL_GROOVY_SOURCE_TOOL) is None
    catalog.replace_declared([*catalog.declared_names, LOCAL_GROOVY_SOURCE_TOOL])
    tool = catalog.declared_tool(LOCAL_GROOVY_SOURCE_TOOL)
    assert tool is not None
    assert tool.input_schema["required"] == ["appId"]
    assert tool.annotations["readOnlyHint"] is True


def test_source_reader_never_treats_gateway_facade_as_source_tool():
    facade = MCPTool("hub_read_apps_code", "Hubitat apps and code gateway", {
        "type": "object",
        "properties": {"tool": {"type": "string", "enum": ["hub_get_app_config"]}},
    })
    assert _source_operations([facade], {}) == []


def test_source_reader_can_select_actual_read_leaf():
    facade = MCPTool("hub_read_apps_code", "Hubitat apps code gateway", {
        "type": "object", "properties": {
            "tool": {"type": "string", "enum": ["hub_get_app_config", "hub_get_source"]},
        },
    })
    assert _source_operations([facade], {}) == [("hub_read_apps_code", "hub_get_source")]


def test_model_receives_source_evidence_not_hardcoded_answer(monkeypatch):
    import groovy_source_investigation as source
    called = []
    async def fake_inspect(self, app_id, symbols=None):
        called.append(app_id)
        return GroovySourceReport(
            f"Model-readable source snippet for app {app_id}. "
            "No conclusions about duration or state have been drawn.",
            retrieved=True,
        )
    monkeypatch.setattr(source.GroovySourceService, "inspect", fake_inspect)
    async def run():
        agent = UnifiedMCPAgent.__new__(UnifiedMCPAgent)
        agent.mcp = object()
        agent.evidence = object()
        response = await agent._read_groovy_source({"appId": "4019"})
        assert response.data["sourceRetrieved"] is True
        assert "snippet" in response.text
        assert "300 minutes" not in response.text
        assert called == ["4019"]
        rejected = await agent._read_groovy_source({"appId": "../4019"})
        assert rejected.data["success"] is False
    asyncio.run(run())
