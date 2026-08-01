from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from capability_grounding import (  # noqa: E402
    CAPABILITY_ACTION_FAILURE,
    CAPABILITY_RETRY_INSTRUCTION,
    CapabilityAction,
    CapabilityGroundingPolicy,
)


def test_ordinary_answer_is_accepted_without_discovery():
    policy = CapabilityGroundingPolicy()

    decision = policy.decide("The hallway light is off.")

    assert decision.action is CapabilityAction.ACCEPT
    assert decision.message is None


def test_explicit_capability_denials_trigger_one_recovery():
    examples = [
        "I cannot create new rules.",
        "I can only manage existing rules.",
        "This assistant does not support dashboard creation.",
        "That operation is unsupported.",
    ]

    for answer in examples:
        policy = CapabilityGroundingPolicy()
        decision = policy.decide(answer)
        assert (decision.action, decision.message) == (
            CapabilityAction.DISCOVER,
            CAPABILITY_RETRY_INSTRUCTION,
        )


def test_repeated_denial_is_blocked_when_recovery_found_gateways():
    policy = CapabilityGroundingPolicy()
    assert policy.decide("I cannot create that.").action is CapabilityAction.DISCOVER
    policy.record_discovery(2)

    decision = policy.decide("I cannot create that.")

    assert (decision.action, decision.message) == (
        CapabilityAction.REJECT_UNGROUNDED,
        CAPABILITY_ACTION_FAILURE,
    )


def test_grounded_denial_can_stand_when_recovery_found_no_gateway():
    policy = CapabilityGroundingPolicy()
    assert policy.decide("I cannot create that.").action is CapabilityAction.DISCOVER
    policy.record_discovery(0)

    decision = policy.decide("This operation is not supported.")

    assert decision.action is CapabilityAction.ACCEPT
    assert decision.message is None
