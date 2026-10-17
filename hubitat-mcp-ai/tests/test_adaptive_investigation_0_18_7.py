"""Model-led investigative routing, tool permission boundaries and domain breadth."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from adaptive_investigation_policy import model_led_investigation_request
from homebrain_agent import UnifiedMCPAgent
from mcp_agent_orchestrator import AgentOutcome
from tool_catalog_assembly import build_request_tool_catalog
from mcp_client import MCPTool


def test_adaptive_eligibility_spans_unrelated_subjects():
    for request in (
        "Inspect the Groovy implementation of installed app 4019. Read-only.",
        "Investigate why Bathroom Light 1 turned on using button events and logs. Read-only.",
        "Analyse all scheduled jobs and identify unnecessary executions, read-only.",
        "Diagnose intermittent Zigbee device connectivity from telemetry. Read-only.",
        "Audit unusual energy monitoring activity using logs and metrics. Read-only.",
        "Why did Bathroom Light 1 turn on at 08:45?",
    ):
        assert model_led_investigation_request(request), request


def test_simple_status_and_actions_do_not_enter_readonly_planner():
    for request in (
        "Is my bathroom light on?",
        "What is the current temperature?",
        "Show the current persisted lockout setting for app 4019.",
        "Turn off Bathroom Light 1.",
        "Analyse the logs. Also switch on Bathroom Light 1.",
        "Change the bathroom automation settings.",
    ):
        assert not model_led_investigation_request(request), request


def test_installed_read_view_cannot_offer_write_functions():
    catalog = build_request_tool_catalog([
        MCPTool("hub_read_apps_code", "Read installed apps", {"type":"object"}),
        MCPTool("hub_manage_rule_machine", "Manage rules", {"type":"object"}),
        MCPTool("hub_search_tools", "Discover capabilities", {"type":"object"}),
    ])
    names = catalog.activate_investigation_read_view(max_declared=30)
    assert "hub_read_apps_code" in names
    assert "hub_search_tools" in names
    assert "hub_manage_rule_machine" not in names
    assert "homebrain_control_devices" not in names


def test_complex_request_bypasses_specialised_shortcuts(monkeypatch):
    from mcp_agent_orchestrator import UnifiedMCPAgent as BaseAgent
    calls = []
    async def base(self, question, history=None, *, session_id="default"):
        calls.append(("base", question))
        return AgentOutcome(
            message="Model investigation pending evidence.",
            request_class="live-read", evidence=[], choices=[],
        )
    monkeypatch.setattr(BaseAgent, "process_user_request_result", base)

    class Observation:
        async def run(self, operation):
            return await operation()
    class Metrics:
        def increment(self, name):
            calls.append(("counter", name))
    async def no_pending(self, question, *, session_key):
        return None
    monkeypatch.setattr(UnifiedMCPAgent, "_resolve_pending_confirmation", no_pending)

    async def run():
        agent = UnifiedMCPAgent.__new__(UnifiedMCPAgent)
        agent.request_observation = Observation()
        agent.request_metrics = Metrics()
        agent._clarification_choices = {}
        agent._clarification_objectives = {}
        question = "Analyse all scheduled jobs and identify unnecessary activity. Read-only."
        result = await agent.process_user_request_result(question)
        assert result.request_class == "live-read"
        assert ("base", question) in calls
        assert ("counter", "investigation_snapshot_shortcut_bypassed") in calls
    asyncio.run(run())
