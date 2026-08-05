from __future__ import annotations

import sys
from contextvars import ContextVar
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from confirmation_policy import ConfirmationPolicy  # noqa: E402
from confirmation_store import ConfirmationStore  # noqa: E402
from rule_authoring_service import RuleAuthoringDecision  # noqa: E402
from rule_proposal_confirmation import RuleProposalConfirmation  # noqa: E402


def _coordinator(**policy_kwargs):
    mutation_seen: ContextVar[bool] = ContextVar("test_mutation_seen", default=False)
    coordinator = RuleProposalConfirmation(
        ConfirmationPolicy(**policy_kwargs),
        ConfirmationStore(120),
        mutation_seen,
    )
    return coordinator, mutation_seen


def test_direct_message_decision_is_returned_unchanged() -> None:
    coordinator, mutation_seen = _coordinator()
    decision = RuleAuthoringDecision(handled=True, message="Cannot compile that schedule.")

    result = coordinator.resolve(
        decision,
        user_prompt="turn on the porch light every day at 6pm",
        session_id="session-1",
    )

    assert result == "Cannot compile that schedule."
    # A direct message means no rule-machine write was proposed at all.
    assert mutation_seen.get() is False


def test_proposed_actions_are_queued_for_confirmation() -> None:
    coordinator, mutation_seen = _coordinator()
    decision = RuleAuthoringDecision(
        handled=True,
        actions=({"name": "Evening Lights", "trigger": "18:00"},),
    )

    result = coordinator.resolve(
        decision,
        user_prompt="turn on the porch light every day at 6pm",
        session_id="session-1",
    )

    assert "confirm" in result.lower() or result
    assert mutation_seen.get() is True


def test_default_session_is_rejected_not_queued() -> None:
    coordinator, mutation_seen = _coordinator()
    decision = RuleAuthoringDecision(
        handled=True,
        actions=({"name": "Evening Lights", "trigger": "18:00"},),
    )

    result = coordinator.resolve(
        decision,
        user_prompt="turn on the porch light every day at 6pm",
        session_id="default",
    )

    assert "session" in result.lower()


def test_disabled_confirmation_policy_bypasses_queue() -> None:
    coordinator, mutation_seen = _coordinator(enabled=False)
    decision = RuleAuthoringDecision(
        handled=True,
        actions=({"name": "Evening Lights", "trigger": "18:00"},),
    )

    result = coordinator.resolve(
        decision,
        user_prompt="turn on the porch light every day at 6pm",
        session_id="session-1",
    )

    assert isinstance(result, str)
    assert mutation_seen.get() is True
