"""General regression: coordinated "do not" lists are not write authority.

Derived from a real HomeBrain read-only native Rule Machine investigation.
The host must preserve grounded model explanations when no action was asked.
Tests never call a hub, model provider, or mutation tool.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from control_intent_guard import (  # noqa: E402
    explicitly_read_only_request, independent_affirmative_mutation_clause,
)
from mcp_agent_orchestrator import (  # noqa: E402
    _explicit_mutation_request, _verified_schedule_write_intent,
    UnifiedMCPAgent,
)
from rule_authoring_service import RuleAuthoringService  # noqa: E402


PROMPT = (
    "Read-only: Find an existing native Rule Machine 5.1 rule with a Certain "
    "Time trigger and a Switch OFF action. Identify its Rule Machine parent "
    "ID and retrieve the exact native trigger/action field names, types and "
    "values using supported read-only tools. Do not open native forms, "
    "create rules, submit confirmations or modify anything. Report any "
    "unavailable evidence."
)


@pytest.mark.parametrize("question", [
    PROMPT,
    "Read-only. Inspect the current rule. Do not open native forms, create rules, or modify anything.",
    "Read only: review the schedule; don't open forms, create rules or submit changes.",
    "Read-only: check a smart switch. Never execute actions, change its state, or delete rules.",
    "Read-only: review Hubitat rules. Do not open forms, create rules, submit confirmations or modify anything.",
    "Inspect the existing native rule. Do not open native forms, create rules, submit confirmations or modify anything.",
])
def test_coordinated_prohibitions_preserve_read_only_authority(question):
    if question.lower().startswith(("read-only", "read only")):
        assert explicitly_read_only_request(question)
    assert not _explicit_mutation_request(question)


@pytest.mark.parametrize("question", [
    "Read-only: inspect rule 4136. Then disable rule 4136.",
    "Read-only: inspect rule 4136, but create a new rule tomorrow.",
    "Read-only: inspect rule 4136. Also block the TV now.",
    "Read-only: do not open forms, create rules or modify anything. Then block the TV.",
])
def test_new_independent_imperative_retains_write_approval_gate(question):
    assert independent_affirmative_mutation_clause(question, start=question.lower().index("read-only") + len("read-only"))
    assert not explicitly_read_only_request(question)
    assert _explicit_mutation_request(question)


def test_native_scheduler_does_not_acquire_permission_from_a_read_only_investigation():
    class NoCalls:
        def __getattr__(self, name):
            raise AssertionError(f"Unexpected external call: {name}")
    rules = RuleAuthoringService(NoCalls(), lambda *_a, **_kw: None)
    assert not _verified_schedule_write_intent(PROMPT, rules)


@pytest.mark.asyncio
async def test_read_only_native_investigation_retains_non_mutating_result(monkeypatch):
    """Exercise the actual request class and publication boundary."""
    class NoHub:
        async def list_tools(self):
            raise AssertionError("Synthetic result must not read the live hub")

    class NoModel:
        async def aclose(self):
            return None

    answer = (
        "Rule 4136 is a candidate. Its parent ID is unverified; "
        "a native-document read receipt was not provided."
    )
    async def synthetic_read(_agent, _prompt, _history, *, session_id):
        assert session_id == "read-only-native-test"
        return answer

    monkeypatch.setattr(UnifiedMCPAgent, "_process_user_request", synthetic_read)
    agent = UnifiedMCPAgent(NoHub(), "synthetic-key", "gemma4:31b", ai_client=NoModel())
    outcome = await agent.process_user_request_result(PROMPT, session_id="read-only-native-test")
    assert outcome.request_class == "live-read"
    assert not outcome.confirmation_required
    assert outcome.confirmation_count == 0
    assert outcome.message == answer
    assert "I could not verify that this action actually ran" not in outcome.message
