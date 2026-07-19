from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from routing_policy import classify_query  # noqa: E402


def test_exact_absolute_level_command_is_mcp_fast_not_planner():
    decision = classify_query("set Bedroom 1 Light to 30%")

    assert decision.route == "mcp-fast"
    assert "deterministic Control Agent" in decision.reason


def test_spelled_percent_absolute_level_command_is_mcp_fast():
    decision = classify_query("dim the Bedroom 1 Light to 45 percent")

    assert decision.route == "mcp-fast"


def test_contextual_level_command_still_requires_interpretation():
    decision = classify_query("set it to 30%")

    assert decision.route == "ollama-planner"


def test_out_of_range_level_command_is_not_fast_executed():
    decision = classify_query("set Bedroom 1 Light to 130%")

    assert decision.route == "ollama-planner"
