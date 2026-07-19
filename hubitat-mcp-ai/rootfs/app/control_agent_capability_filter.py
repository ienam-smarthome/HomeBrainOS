from __future__ import annotations

from typing import Any, Callable

from control_agent_graph import ControlDeviceGraph, DeviceNode
from device_intelligence_index import _attributes


_CONTROL_ATTRIBUTES = {"switch", "level"}
_CONTROL_CAPABILITIES = {"switch", "switchlevel", "switch level"}
_CONTROL_COMMANDS = {"on", "off", "setlevel", "set level"}


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
    """Return true only when the selected-device record proves actuation support.

    Control Agent v1 supports on, off and absolute level only. A label containing
    words such as light or lamp is therefore insufficient evidence: Lux,
    illuminance, battery and presence sensors must not enter its resolution graph.
    """

    attributes = {str(key).strip().lower() for key in _attributes(raw)}
    if attributes & _CONTROL_ATTRIBUTES:
        return True

    capabilities = _names(raw.get("capabilities"))
    if capabilities & _CONTROL_CAPABILITIES:
        return True

    commands = _names(raw.get("commands"))
    return bool(commands & _CONTROL_COMMANDS)


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
