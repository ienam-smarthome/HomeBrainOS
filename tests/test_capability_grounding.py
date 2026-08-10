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


def test_a_grounded_statement_about_one_devices_hardware_limits_is_not_a_denial():
    """Regression test: the "does not support" pattern used to have no
    subject anchor, so it also matched ordinary factual statements about a
    *device's* hardware limits, not just the assistant's own operational
    ability -- turning an already-correct, grounded answer into a false
    REJECT_UNGROUNDED cycle.
    """

    policy = CapabilityGroundingPolicy()

    decision = policy.decide("The dimmer does not support color temperature.")

    assert decision.action is CapabilityAction.ACCEPT
    assert decision.message is None


def test_contraction_denial_phrasing_is_still_recognised():
    """Regression test: the denial patterns required spelled-out "do not"/
    "am unable to" and missed contractions -- "I don't have the ability to
    control locks." bypassed denial detection entirely, silently disabling
    the one-shot discovery-recovery mechanism for the most natural phrasing
    of a real capability gap.
    """

    policy = CapabilityGroundingPolicy()

    decision = policy.decide("I don't have the ability to control locks.")

    assert decision.action is CapabilityAction.DISCOVER
    assert decision.message == CAPABILITY_RETRY_INSTRUCTION


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
