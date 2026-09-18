from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import _controller_followup_arguments  # noqa: E402


def test_controller_followup_uses_only_top_ranked_candidate() -> None:
    arguments = _controller_followup_arguments([
        {
            "label": "Bedroom 3 dimmer - 1",
            "suggestedHistoryAttributes": ["pushed", "held"],
        },
        {
            "label": "Bedroom 3 dimmer - 2",
            "suggestedHistoryAttributes": ["pushed"],
        },
    ])

    assert arguments == {
        "name": "Bedroom 3 dimmer - 1",
        "attribute": "pushed",
    }


def test_controller_followup_requires_label_and_suggested_attribute() -> None:
    assert _controller_followup_arguments([]) is None
    assert _controller_followup_arguments([{"label": "Bedroom 3 dimmer - 1"}]) is None
    assert _controller_followup_arguments([
        {"suggestedHistoryAttributes": ["pushed"]}
    ]) is None


def test_controller_followup_does_not_expand_to_other_candidates() -> None:
    arguments = _controller_followup_arguments([
        {
            "label": "Remote",
            "suggestedHistoryAttributes": ["released", "pushed"],
        },
        {
            "label": "Bedroom 3 dimmer - 1",
            "suggestedHistoryAttributes": ["pushed"],
        },
    ])

    assert arguments == {"name": "Remote", "attribute": "released"}
