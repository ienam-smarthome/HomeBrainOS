"""Command semantics for state-change investigations.

A Hubitat command event is a different kind of evidence from a switch state
event or a nearby sensor report. Preserve the *actual command method* and its
arguments. Only promote commands whose documented effect is compatible with
the observed switch transition, and whose event precedes that boundary.

The registry is extensible. Vendor-specific colour, scene and toggle methods
may be state-affecting but do not get promoted to a definitive ON/OFF command
without driver-specific confirmation.
"""
from __future__ import annotations

import re
from typing import Any

_LEVEL_DESCRIPTION = re.compile(
    r"\b(?:Command\s+called\s*:\s*)?setLevel\s*\(\s*"
    r"([0-9]{1,3}(?:\.[0-9]+)?)\s*(?:[,)]|$)",
    re.I,
)

# Additional commands worth investigating when advertised by a driver.
# They may change a device's switch state, but that effect is not universal.
_DRIVER_DEPENDENT_EFFECTS = frozenset({
    "setcolor", "setcolortemperature", "sethue", "setsaturation",
    "activatescene", "pushscene", "toggle", "startlevelchange",
})


def _metadata_name(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("command")
    return str(value or "").strip()


def _names(value: Any) -> set[str]:
    if isinstance(value, dict):
        values = value.keys()
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = ()
    return {
        re.sub(r"[^a-z0-9]", "", name.casefold())
        for row in values
        if (name := _metadata_name(row))
    }


def dimmer_command_supported(target: dict[str, Any]) -> bool:
    """Require *positive* dimmer metadata, not a light-sounding label.

    Old bridge identity records may omit command names but advertise
    SwitchLevel or a numeric/current level attribute instead.
    """
    commands = _names(target.get("commands"))
    capabilities = _names(target.get("capabilities"))
    attrs = _names(target.get("attributes"))
    return (
        "setlevel" in commands
        or "switchlevel" in capabilities
        or ("level" in attrs and "switch" in attrs)
    )


def command_actions_for_history(
    target: dict[str, Any],
    actions: tuple[str, ...],
) -> tuple[str, ...]:
    """Extend explicit switch-cause reads without changing plain switch plugs."""

    result = list(dict.fromkeys(actions))
    if dimmer_command_supported(target) and "setLevel" not in result:
        result.append("setLevel")
    return tuple(result)


def _level_from_event(event: dict[str, Any]) -> float | None:
    raw = event.get("value")
    if isinstance(raw, dict):
        raw = raw.get("level") if "level" in raw else raw.get("value")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        value = float(raw)
    elif isinstance(raw, str) and re.fullmatch(r"\s*\d{1,3}(?:\.\d+)?\s*", raw):
        value = float(raw)
    else:
        value = None

    if value is None:
        description = str(
            event.get("description") or event.get("descriptionText") or ""
        )
        match = _LEVEL_DESCRIPTION.search(description)
        if match:
            value = float(match.group(1))
    return value if value is not None and 0 <= value <= 100 else None


def classify_state_command(
    event: dict[str, Any],
    transition: str,
) -> dict[str, Any] | None:
    """State compatibility for an observed ON/OFF boundary.

    'compatible' is a command-semantic determination, NOT evidence that the
    bridge executed it; command-to-state alignment is checked separately.
    """

    name = str(event.get("name") or "").strip().casefold()
    action = str(transition or "").strip().casefold()
    if not name.startswith("command-") or action not in {"on", "off"}:
        return None
    method = name[len("command-"):]
    if method in {"on", "off"}:
        if method != action:
            return None
        return {
            "method": method,
            "display": f"{method}()",
            "semantics": "explicit-switch-command",
            "level": None,
            "compatible": True,
            "provenEffect": True,
        }
    if method == "setlevel":
        level = _level_from_event(event)
        if level is None:
            return {
                "method": method, "display": "setLevel(?)",
                "semantics": "unknown-argument",
                "level": None, "compatible": False, "provenEffect": False,
            }
        compatible = (level > 0) if action == "on" else (level == 0)
        return {
            "method": method,
            "display": f"setLevel({level:g})",
            "semantics": "level-switch-command",
            "level": level,
            "compatible": compatible,
            "provenEffect": bool(compatible),
        }
    if method in _DRIVER_DEPENDENT_EFFECTS:
        return {
            "method": method,
            "display": method,
            "semantics": "driver-dependent-command",
            "level": None,
            "compatible": False,
            "provenEffect": False,
        }
    return None


def command_family_description(semantics: dict[str, Any]) -> str:
    if semantics.get("method") == "setlevel":
        level = semantics.get("level")
        if isinstance(level, (int, float)) and level > 0:
            return (
                "A positive dimmer level can switch a light ON without a "
                "separate on() command. This is a verified command and "
                "consistent state transition, not evidence of who originally "
                "triggered the controlling app."
            )
        if level == 0:
            return (
                "A zero dimmer level can switch a light OFF. This is a "
                "verified command and consistent state transition, not "
                "proof of the upstream sensor or person."
            )
    return ""
