from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from reasoning_policy import (  # noqa: E402
    arm_controller_followup_budget,
    controller_followup_pending,
    reasoning_budget_exhausted,
    reasoning_budget_status,
    register_model_tool_execution,
    reset_reasoning_budget,
)


def _spend_normal_read_budget() -> None:
    reset_reasoning_budget()
    for index in range(8):
        assert register_model_tool_execution(
            name="homebrain_filter_devices",
            arguments={"attribute": "room", "value": f"Room {index}"},
            mutates=False,
        )


def test_controller_followup_defers_synthesis_after_normal_read_budget() -> None:
    _spend_normal_read_budget()
    assert reasoning_budget_exhausted() is True

    armed = arm_controller_followup_budget([
        {
            "label": "Bedroom 3 Dimmer",
            "suggestedHistoryAttributes": ["pushed", "held"],
        }
    ])

    assert armed is True
    assert controller_followup_pending() is True
    assert reasoning_budget_exhausted() is False


def test_exact_controller_history_gets_one_extra_read() -> None:
    _spend_normal_read_budget()
    arm_controller_followup_budget([
        {
            "label": "Bedroom 3 Dimmer",
            "suggestedHistoryAttributes": ["pushed", "held"],
        }
    ])

    allowed = register_model_tool_execution(
        name="homebrain_device_history",
        arguments={"name": "Bedroom 3 Dimmer", "attribute": "pushed"},
        mutates=False,
    )

    assert allowed is True
    assert controller_followup_pending() is False
    assert reasoning_budget_exhausted() is True
    assert reasoning_budget_status()["readCalls"] == 9


def test_wrong_extra_read_consumes_reservation_and_is_blocked() -> None:
    _spend_normal_read_budget()
    arm_controller_followup_budget([
        {
            "label": "Bedroom 3 Dimmer",
            "suggestedHistoryAttributes": ["pushed"],
        }
    ])

    allowed = register_model_tool_execution(
        name="homebrain_device_history",
        arguments={"name": "Bedroom 3 Soft Sensor", "attribute": "motion"},
        mutates=False,
    )

    assert allowed is False
    assert controller_followup_pending() is False
    assert reasoning_budget_exhausted() is True


def test_wrong_controller_attribute_is_not_allowed_as_extension() -> None:
    _spend_normal_read_budget()
    arm_controller_followup_budget([
        {
            "label": "Bedroom 3 Dimmer",
            "suggestedHistoryAttributes": ["pushed"],
        }
    ])

    allowed = register_model_tool_execution(
        name="homebrain_device_history",
        arguments={"name": "Bedroom 3 Dimmer", "attribute": "motion"},
        mutates=False,
    )

    assert allowed is False
    assert reasoning_budget_exhausted() is True


def test_controller_followup_is_immediate_even_before_generic_budget_is_spent() -> None:
    reset_reasoning_budget()
    assert register_model_tool_execution(
        name="homebrain_device_history",
        arguments={"name": "Bedroom 3 Light", "attribute": "switch"},
        mutates=False,
    )

    arm_controller_followup_budget([
        {
            "label": "Bedroom 3 dimmer - 1",
            "suggestedHistoryAttributes": ["pushed"],
        },
        {
            "label": "Bedroom 3 dimmer - 2",
            "suggestedHistoryAttributes": ["pushed"],
        },
    ])

    assert register_model_tool_execution(
        name="homebrain_device_history",
        arguments={"name": "Bedroom 3 dimmer - 1", "attribute": "pushed"},
        mutates=False,
    ) is True
    assert reasoning_budget_exhausted() is True


def test_only_highest_ranked_controller_candidate_is_reserved() -> None:
    reset_reasoning_budget()
    arm_controller_followup_budget([
        {
            "label": "Bedroom 3 dimmer - 1",
            "suggestedHistoryAttributes": ["pushed"],
        },
        {
            "label": "Bedroom 3 dimmer - 2",
            "suggestedHistoryAttributes": ["pushed"],
        },
    ])

    assert register_model_tool_execution(
        name="homebrain_device_history",
        arguments={"name": "Bedroom 3 dimmer - 2", "attribute": "pushed"},
        mutates=False,
    ) is False
    assert reasoning_budget_exhausted() is True


def test_second_controller_read_in_same_round_is_blocked_after_reserved_read() -> None:
    reset_reasoning_budget()
    arm_controller_followup_budget([
        {
            "label": "Bedroom 3 dimmer - 1",
            "suggestedHistoryAttributes": ["pushed"],
        }
    ])

    assert register_model_tool_execution(
        name="homebrain_device_history",
        arguments={"name": "Bedroom 3 dimmer - 1", "attribute": "pushed"},
        mutates=False,
    ) is True

    assert register_model_tool_execution(
        name="homebrain_device_history",
        arguments={"name": "Bedroom 3 dimmer - 2", "attribute": "pushed"},
        mutates=False,
    ) is False
    assert reasoning_budget_status()["skippedReadCalls"] == 1
