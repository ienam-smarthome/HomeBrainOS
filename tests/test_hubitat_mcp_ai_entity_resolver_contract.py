from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from assistant_contracts import ResolutionStatus, RouteClass  # noqa: E402
from control_agent_capability_filter import install_control_graph_capability_filter  # noqa: E402
from control_agent_intent import ControlTargetIntent  # noqa: E402
from entity_resolver import EntityResolver  # noqa: E402
from routing_policy import classify_query  # noqa: E402


DEVICES = [
    {
        "id": "1",
        "label": "Livingroom Light 1",
        "room": "Living Room",
        "currentStates": {"switch": "off", "level": 25},
    },
    {
        "id": "2",
        "label": "Livingroom Light 2",
        "room": "Living Room",
        "currentStates": {"switch": "on", "level": 70},
    },
    {
        "id": "3",
        "label": "FP2 Livingroom Lux",
        "room": "Living Room",
        "currentStates": {"illuminance": 12},
    },
    {
        "id": "4",
        "label": "Fan Switch",
        "room": "Living Room",
        "currentStates": {"switch": "on"},
    },
]


def resolver() -> EntityResolver:
    install_control_graph_capability_filter()
    return EntityResolver(DEVICES)


def test_entity_resolver_returns_typed_ordinal_trace():
    resolution, contract = resolver().resolve_for_action(
        ControlTargetIntent(room_hint="Living Room", device_type="light", ordinal=2),
        action="off",
    )

    assert [node.id for node in resolution.nodes] == ["2"]
    assert contract.status is ResolutionStatus.RESOLVED
    assert contract.targets[0].match_reason
    assert contract.targets[0].supports_action is True
    assert "method=room-type-ordinal" in contract.trace
    assert "action=off" in contract.trace


def test_entity_resolver_rejects_unsupported_action_before_execution():
    resolution, contract = resolver().resolve_for_action(
        ControlTargetIntent(name_hint="Fan Switch"),
        action="set_level",
    )

    assert resolution.nodes == []
    assert contract.status is ResolutionStatus.UNSUPPORTED_ACTION
    assert contract.candidates[0].label == "Fan Switch"
    assert contract.candidates[0].supports_action is False


def test_unsupported_candidates_never_become_action_choices():
    resolution, contract = resolver().resolve_for_action(
        ControlTargetIntent(name_hint="fan"),
        action="set_level",
    )

    assert resolution.nodes == []
    assert contract.status is ResolutionStatus.UNSUPPORTED_ACTION
    assert [item.label for item in contract.candidates] == ["Fan Switch"]


def test_routes_expose_one_of_three_public_route_classes():
    assert classify_query("turn off Bedroom 1 Light").route_class is RouteClass.FAST_CONTROL
    assert classify_query("show lights on").route_class is RouteClass.FAST_READ
    assert classify_query("why are the lights on?").route_class is RouteClass.AGENT
