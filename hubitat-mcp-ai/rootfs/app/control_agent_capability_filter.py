from __future__ import annotations

import re
from typing import Any, Callable

from control_agent_graph import ControlDeviceGraph, DeviceNode
from device_intelligence_index import _attributes, _device_id, _label, _room_name
from spoken_device_name import spoken_name_key


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


def _selected_aliases(raw: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for key in ("label", "name"):
        value = str(raw.get(key) or "").strip()
        if not value:
            continue
        aliases.add(value)
        base = re.sub(r"\s*(?:\([^)]*\)|\[[^]]*\])\s*$", "", value).strip()
        if base:
            aliases.add(base)
    label = _label(raw)
    room = _room_name(raw)
    if label and room:
        aliases.add(f"{room} {label}")
    return aliases


def exact_non_control_matches(graph: ControlDeviceGraph, value: str) -> list[dict[str, Any]]:
    """Return exact selected-device matches deliberately excluded from control.

    This distinguishes a known read-only sensor from an unknown or misspelt target.
    It must never perform fuzzy matching: only a canonical spoken-name equality is
    strong enough to suppress normal device clarification.
    """

    key = spoken_name_key(value)
    if not key:
        return []
    index = getattr(graph, "_non_control_alias_index", {})
    rows = index.get(key, []) if isinstance(index, dict) else []
    return [dict(item) for item in rows if isinstance(item, dict)]


def non_control_kind(raw: dict[str, Any]) -> str:
    """Describe a selected read-only device without claiming unsupported metadata."""

    attributes = {str(key).strip().lower() for key in _attributes(raw)}
    text = " ".join(str(raw.get(key) or "") for key in ("label", "name")).lower()
    if "illuminance" in attributes or re.search(r"\b(?:lux|illuminance|light\s+sensor)\b", text):
        return "illuminance (Lux) sensor"
    if "motion" in attributes or re.search(r"\bmotion\b", text):
        return "motion sensor"
    if "presence" in attributes or "occupancy" in attributes or re.search(r"\b(?:presence|occupancy)\b", text):
        return "presence sensor"
    if "contact" in attributes or re.search(r"\b(?:contact|door\s+sensor)\b", text):
        return "contact sensor"
    if "temperature" in attributes and "humidity" in attributes:
        return "temperature and humidity sensor"
    if "temperature" in attributes or re.search(r"\b(?:temperature|temp)\b", text):
        return "temperature sensor"
    if "humidity" in attributes or re.search(r"\bhumidity\b", text):
        return "humidity sensor"
    if "battery" in attributes or re.search(r"\bbattery\b", text):
        return "battery sensor"
    return "read-only selected device"


def non_control_public(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(_device_id(raw) or ""),
        "label": _label(raw),
        "room": _room_name(raw),
        "kind": non_control_kind(raw),
        "attributes": sorted(str(key) for key in _attributes(raw)),
    }


def install_control_graph_capability_filter() -> None:
    """Restrict control resolution while retaining exact read-only device evidence."""

    if getattr(ControlDeviceGraph, "_capability_filter_installed", False):
        return

    original_init = ControlDeviceGraph.__init__
    original_build: Callable[[list[dict[str, Any]], dict[str, str]], list[DeviceNode]] = (
        ControlDeviceGraph._build_nodes
    )

    def init_control_graph(
        self: ControlDeviceGraph,
        devices: Any,
        *,
        learned_aliases: dict[str, str] | None = None,
    ) -> None:
        selected = [dict(item) for item in list(devices) if isinstance(item, dict)]
        non_control_index: dict[str, list[dict[str, Any]]] = {}
        for raw in selected:
            if bool(raw.get("disabled")) or is_control_capable(raw):
                continue
            seen_keys: set[str] = set()
            for alias in _selected_aliases(raw):
                key = spoken_name_key(alias)
                if not key or key in seen_keys:
                    continue
                seen_keys.add(key)
                non_control_index.setdefault(key, []).append(raw)
        self._non_control_alias_index = non_control_index
        original_init(self, selected, learned_aliases=learned_aliases)

    def build_control_nodes(
        cls: type[ControlDeviceGraph],
        devices: list[dict[str, Any]],
        learned_aliases: dict[str, str],
    ) -> list[DeviceNode]:
        del cls
        eligible = [raw for raw in devices if is_control_capable(raw)]
        return original_build(eligible, learned_aliases)

    ControlDeviceGraph.__init__ = init_control_graph
    ControlDeviceGraph._build_nodes = classmethod(build_control_nodes)
    ControlDeviceGraph._capability_filter_installed = True


__all__ = [
    "exact_non_control_matches",
    "install_control_graph_capability_filter",
    "is_control_capable",
    "non_control_kind",
    "non_control_public",
]
