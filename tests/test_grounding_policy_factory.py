from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from grounding_policy import (  # noqa: E402
    GroundingPolicy,
    reset_grounding_policy_factory,
    set_grounding_policy_factory,
)


class AlternatePolicy:
    def __init__(self, *, logs_requested: bool, conversational: bool) -> None:
        self.logs_requested = logs_requested
        self.conversational = conversational


def test_factory_override_is_bounded_and_resettable() -> None:
    def factory(*, logs_requested: bool, conversational: bool) -> AlternatePolicy:
        return AlternatePolicy(
            logs_requested=logs_requested,
            conversational=conversational,
        )

    token = set_grounding_policy_factory(factory)
    try:
        selected = GroundingPolicy(
            logs_requested=True,
            conversational=False,
        )
    finally:
        reset_grounding_policy_factory(token)

    default = GroundingPolicy(
        logs_requested=False,
        conversational=True,
    )

    assert isinstance(selected, AlternatePolicy)
    assert selected.logs_requested is True
    assert selected.conversational is False
    assert type(default) is GroundingPolicy


def test_default_constructor_bypasses_active_factory() -> None:
    def factory(**_kwargs: object) -> AlternatePolicy:
        raise AssertionError("factory should not be used")

    token = set_grounding_policy_factory(factory)
    try:
        policy = GroundingPolicy.default(
            logs_requested=False,
            conversational=False,
        )
    finally:
        reset_grounding_policy_factory(token)

    assert type(policy) is GroundingPolicy
