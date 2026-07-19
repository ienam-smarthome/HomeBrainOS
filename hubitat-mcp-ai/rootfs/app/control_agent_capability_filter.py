from __future__ import annotations

import re
from typing import Any, Callable

from control_agent_graph import ControlDeviceGraph, DeviceNode
from device_intelligence_index import _attributes


_CONTROL_ATTRIBUTES = {"switch", "level"}
_CONTROL_CAPABILITIES = {"switch", "switchlevel", "switch level"}
_CONTROL_COMMANDS = {"on", "off", "setlevel", "set level"}
_SENSOR_ONLY_LABEL = re.compile(
    r"\b(?:lux|illuminance|light\s+sensor|motion|presence|occupancy|battery|"
    r"temperature|temp|humidity|contact|door\s+sensor|meter|power\s+display)\b",
    re.IGNORECASE,
)
_CLEAR_ACTUATOR_LABEL = re.compile(
    r"\b(?:light|lamp|bulb|dimmer|fan|switch|socket|outlet|plug|tv|television|"
    r"dehumidifier|humidifier|purifier|heater|radiator|thermostat|trv|valve|"
    r"camera|cam|vacuum|roborock)\b",
    re.IGNORECASE,
)


def _names(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    names: set[str] = set()
    for item in value:
        if isinstance(item, dict):
            raw = item.get("name") or item.get("capability") or item.get("command")
        else:
            raw = item
        text = str(raw or "").strip().lower()
        if text:
            names.add(text)
    return names


def is_control_capable(raw: dict[str, Any]) -> bool:
    """Keep only selected devices the Control Agent can plausibly actuate.

    Live switch/level state, capability metadata or command metadata are strong
    evidence. Compact Hubitat summaries occasionally omit those fields for a real
    actuator, so a conservative label fallback is allowed only for clear actuator
    nouns and never for sensor-only labels such as Lux or motion devices.
    """

    attributes = {str(key).strip().lower() for key in _attributes(raw)}
    if attributes & _CONTROL_ATTRIBUTES:
        return True

    capabilities = _names(raw.get("capabilities"))
    if capabilities & _CONTROL_CAPABILITIES:
        return True

    commands = _names(raw.get("commands"))
    if commands & _CONTROL_COMMANDS:
        return True

    label_text = " ".join(
        str(raw.get(key) or "").strip()
        for key in ("label", "name")
        if str(raw.get(key) or "").strip()
    )
    if not label_text or _SENSOR_ONLY_LABEL.search(label_text):
        return False
    return bool(_CLEAR_ACTUATOR_LABEL.search(label_text))


def install_control_graph_capability_filter() -> None:
    """Restrict the Control Agent graph to devices it can actually command."""

    if getattr(ControlDeviceGraph, "_capability_filter_installed", False):
        return

    original: Callable[[list[dict[str, Any]], dict[str, str]], list[DeviceNode]] = (
        ControlDeviceGraph._build_nodes
    )

    def build_control_nodes(
        cls: type[ControlDeviceGraph],
        devices: list[dict[str, Any]],
        learned_aliases: dict[str, str],
    ) -> list[DeviceNode]:
        del cls
        eligible = [raw for raw in devices if is_control_capable(raw)]
        return original(eligible, learned_aliases)

    ControlDeviceGraph._build_nodes = classmethod(build_control_nodes)
    ControlDeviceGraph._capability_filter_installed = True


__all__ = ["install_control_graph_capability_filter", "is_control_capable"]
