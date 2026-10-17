"""Live regressions: paid-prefixed historical reads and explicit tool-free knowledge.

No LLM network or Hubitat MCP calls are made by this test module.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from mcp_agent_orchestrator import UnifiedMCPAgent, _explicit_mutation_request
from tool_free_knowledge_policy import eligible_tool_free_knowledge, tool_free_messages


def test_paid_prefix_does_not_turn_historical_question_into_write():
    assert not _explicit_mutation_request(
        "Use paid model. Why did Bathroom Light 1 turn on at 08:45?"
    )
    assert not _explicit_mutation_request(
        "Use paid model. Investigate why Bathroom Light 1 turned on this morning. Read-only."
    )
    assert not _explicit_mutation_request(
        "Premium model: Why was Bathroom Light 1 switched on?"
    )


def test_paid_prefix_keeps_real_write_intent_and_mixed_actions():
    assert _explicit_mutation_request("Use paid model. Turn on Bathroom Light 1.")
    assert _explicit_mutation_request(
        "Use paid model. Why did Bathroom Light 1 turn on? Also turn off Kitchen Light."
    )
    assert _explicit_mutation_request(
        "Use paid model. Investigate why Bathroom Light 1 turned on and then turn off Kitchen Light."
    )
    assert _explicit_mutation_request(
        "Use paid model. Please set the Bedroom 1 thermostat to 20."
    )


def test_tool_free_explicit_static_programming_question():
    question = (
        "Use paid model. Explain in two sentences the difference between a "
        "Groovy application's defaultValue and its persisted settings value. "
        "Answer from general knowledge without using Hubitat MCP tools. Read-only."
    )
    assert eligible_tool_free_knowledge(question)
    assert len(tool_free_messages(question)) == 2


def test_tool_free_rejects_live_investigations_and_control():
    prompts = (
        "Why did Bathroom Light 1 turn on? No Hubitat tools required.",
        "Explain my app 4019 current settings from general knowledge.",
        "Use paid model. Turn on Bathroom Light 1; no Hubitat tools required.",
        "Explain which of my livingroom sensors is online. Answer from general knowledge.",
        "Explain the defaultValue in my app 4019 source without using tools.",
        "Explain programming terminology.",
    )
    for question in prompts:
        assert not eligible_tool_free_knowledge(question), question


def test_explicit_static_explanation_skips_mcp_catalog_entirely():
    class FailIfMCPCalled:
        async def list_tools(self):
            raise AssertionError("Tool-free request must not query Hubitat MCP")

    class OneRoundTransport:
        def __init__(self):
            self.calls = []
        async def chat(self, messages, tools):
            self.calls.append((messages, tools))
            return {"content": "defaultValue is the initial input. Persisted settings override it."}

    async def scenario():
        agent = UnifiedMCPAgent.__new__(UnifiedMCPAgent)
        agent.mcp = FailIfMCPCalled()
        agent.transport = OneRoundTransport()
        question = (
            "Explain the difference between Groovy defaultValue and persisted settings. "
            "No Hubitat tools are required. Answer from general knowledge."
        )
        result = await agent._process_user_request(question)
        assert "Persisted settings" in result
        assert len(agent.transport.calls) == 1
        assert agent.transport.calls[0][1] == []
    asyncio.run(scenario())
