from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from entity_resolution import (  # noqa: E402
    ResolutionRequest,
    ResolutionStatus,
    infer_ordinal,
    resolve_devices,
)


def device(
    device_id: str,
    label: str,
    room: str,
    *,
    capabilities: list[str] | None = None,
    category: str = "",
) -> dict:
    return {
        "id": device_id,
        "label": label,
        "room": room,
        "category": category,
        "capabilities": capabilities or [],
        "attributes": {"switch": "off"} if "Switch" in (capabilities or []) else {},
    }


def test_exact_label_wins_over_broader_similar_device():
    devices = [
        device("1", "Fan Switch (Tuya Local)", "Bathroom", capabilities=["Switch"]),
        device("2", "Fan Boost", "Bathroom", capabilities=["Switch"]),
    ]

    result = resolve_devices(
        devices,
        ResolutionRequest(target_phrase="fan boost", action="off", device_type="fan"),
    )

    assert result.status is ResolutionStatus.RESOLVED
    assert result.targets[0].device_id == "2"
    assert "exact label" in result.targets[0].match_reasons


def test_room_and_ordinal_resolve_second_living_room_light():
    devices = [
        device("10", "Livingroom Light 1", "Living Room", capabilities=["Switch", "Switch Level"]),
        device("11", "Livingroom Light 2", "Living Room", capabilities=["Switch", "Switch Level"]),
        device("12", "Bedroom 2 Light", "Bedroom 2", capabilities=["Switch", "Switch Level"]),
    ]

    result = resolve_devices(
        devices,
        ResolutionRequest(
            target_phrase="the second living room light",
            room="Living Room",
            device_type="light",
            ordinal=2,
            action="off",
        ),
    )

    assert result.status is ResolutionStatus.RESOLVED
    assert result.targets[0].device_id == "11"
    assert "ordinal" in result.targets[0].match_reasons
    assert "exact room" in result.targets[0].match_reasons


def test_non_controllable_sensor_is_rejected_for_switch_action():
    devices = [
        device("20", "FP2 Bedroom 3 Lux", "Bedroom 3", capabilities=["Illuminance Measurement"], category="sensor"),
        device("21", "Bedroom 3 Light", "Bedroom 3", capabilities=["Switch", "Switch Level"], category="light"),
    ]

    result = resolve_devices(
        devices,
        ResolutionRequest(target_phrase="bedroom 3 light", room="Bedroom 3", device_type="light", action="off"),
    )

    assert result.status is ResolutionStatus.RESOLVED
    assert result.targets[0].device_id == "21"
    assert result.targets[0].supported is True


def test_ambiguous_singular_fan_request_does_not_guess():
    devices = [
        device("30", "Fan Switch", "Bathroom", capabilities=["Switch"]),
        device("31", "Fan Boost", "Bathroom", capabilities=["Switch"]),
    ]

    result = resolve_devices(
        devices,
        ResolutionRequest(target_phrase="fan", room="Bathroom", device_type="fan", action="off"),
    )

    assert result.status is ResolutionStatus.AMBIGUOUS
    assert {item.device_id for item in result.candidates} == {"30", "31"}


def test_explicit_group_request_can_resolve_multiple_close_matches():
    devices = [
        device("40", "Fan Switch", "Bathroom", capabilities=["Switch"]),
        device("41", "Fan Boost", "Bathroom", capabilities=["Switch"]),
    ]

    result = resolve_devices(
        devices,
        ResolutionRequest(
            target_phrase="bathroom fan",
            room="Bathroom",
            device_type="fan",
            action="off",
            allow_group=True,
        ),
    )

    assert result.status is ResolutionStatus.RESOLVED_GROUP
    assert {item.device_id for item in result.targets} == {"40", "41"}


def test_matching_device_without_required_capability_reports_unsupported_action():
    devices = [
        device("50", "Front Door Contact", "Entrance", capabilities=["Contact Sensor"], category="contact"),
    ]

    result = resolve_devices(
        devices,
        ResolutionRequest(target_phrase="front door contact", action="off", device_type="contact"),
    )

    assert result.status is ResolutionStatus.UNSUPPORTED_ACTION
    assert result.candidates[0].supported is False


def test_low_score_target_reports_not_found():
    devices = [
        device("60", "Kitchen Light", "Kitchen", capabilities=["Switch"]),
    ]

    result = resolve_devices(
        devices,
        ResolutionRequest(target_phrase="front door", action="off"),
    )

    assert result.status is ResolutionStatus.NOT_FOUND


def test_spoken_and_numeric_ordinals_are_normalised():
    assert infer_ordinal("living room second light") == 2
    assert infer_ordinal("living room light 2") == 2
    assert infer_ordinal("bedroom three light") == 3
