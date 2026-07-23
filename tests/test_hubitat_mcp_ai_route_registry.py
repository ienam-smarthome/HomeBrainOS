from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from route_catalogue import build_route_registry  # noqa: E402
from route_registry import RouteDescriptor, RouteRegistry  # noqa: E402


def selected(query: str) -> str | None:
    match = build_route_registry().select(query).selected
    return match.name if match else None


def test_working_measurement_questions_keep_authoritative_priority():
    assert selected("What is the lux reading from FP2 Bedroom 3 Lux?") == "device-measurement"
    assert selected("What is the bathroom humidity?") == "device-measurement"
    assert selected("How much power is the freezer using?") == "device-measurement"


def test_destructive_hub_requests_beat_generic_control_and_ai():
    decision = build_route_registry().select("Restart the hub")
    assert decision.selected is not None
    assert decision.selected.name == "hub-administration"
    assert decision.selected.terminal is True
    assert "general-assistant" in {match.name for match in decision.matches}


def test_reasoning_questions_use_ai_evidence_before_general_assistant():
    decision = build_route_registry().select("Why is the bathroom so humid?")
    assert decision.selected is not None
    assert decision.selected.name == "ai-evidence"
    assert [match.name for match in decision.matches][-1] == "general-assistant"


def test_duplicate_route_names_are_rejected():
    registry = RouteRegistry()
    route = RouteDescriptor("same", 1, False, lambda query: True, "test")
    registry.register(route)
    try:
        registry.register(route)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate route registration should fail")


def test_route_selection_is_stable_for_equal_priorities():
    registry = RouteRegistry(
        (
            RouteDescriptor("z-route", 100, False, lambda query: True, "z"),
            RouteDescriptor("a-route", 100, False, lambda query: True, "a"),
        )
    )
    assert registry.select("anything").selected.name == "a-route"
