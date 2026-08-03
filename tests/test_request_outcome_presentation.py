from __future__ import annotations

import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from technical_metrics_presenter import (  # noqa: E402
    present_request_metrics,
    present_request_outcome,
)


@pytest.mark.parametrize(
    ("outcome", "label", "tone"),
    [
        ("success", "Success", "positive"),
        ("unresolved", "Unresolved", "warning"),
        ("refused", "Refused", "warning"),
        ("cancelled", "Cancelled", "neutral"),
        ("failed", "Failed", "critical"),
    ],
)
def test_present_request_outcome_has_stable_label_and_tone(
    outcome: str,
    label: str,
    tone: str,
) -> None:
    assert present_request_outcome(outcome) == {
        "value": outcome,
        "label": label,
        "tone": tone,
    }


def test_present_request_outcome_normalises_safe_fixed_values() -> None:
    assert present_request_outcome("  FAILED  ") == {
        "value": "failed",
        "label": "Failed",
        "tone": "critical",
    }


@pytest.mark.parametrize("value", [None, True, 1, "", "unknown", "device-name"])
def test_present_request_outcome_rejects_unknown_or_dynamic_values(value: object) -> None:
    assert present_request_outcome(value) is None


def test_metric_row_output_remains_backwards_compatible() -> None:
    rows = present_request_metrics(
        {"outcome": "unresolved", "counters": {}, "timings_ms": {}}
    )

    assert rows == [{"label": "Outcome", "value": "unresolved"}]
