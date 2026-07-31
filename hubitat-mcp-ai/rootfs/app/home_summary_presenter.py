from __future__ import annotations

from typing import Any


def _joined(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def present_home_summary(snapshot: dict[str, Any], health: dict[str, Any] | None = None) -> str:
    health = health or {}
    lines = ["🏠 Here's what's happening at home:"]

    present = [str(x.get("label")) for x in snapshot.get("presence", []) if isinstance(x, dict) and x.get("label")]
    if present:
        lines.append(f"👨‍👩‍👧 Everyone home: {_joined(present)}")

    rooms = [str(x.get("name")) for x in snapshot.get("active_rooms", []) if isinstance(x, dict) and x.get("name")]
    if rooms:
        lines.append(f"🚶 Active rooms: {_joined(rooms)}")

    lights = [str(x.get("label")) for x in snapshot.get("lights_on", []) if isinstance(x, dict) and x.get("label")]
    if lights:
        lines.append(f"💡 Lights on: {_joined(lights)}")

    switches = snapshot.get("switches_on", [])
    if switches:
        lines.append(f"🔌 Switches currently on: {len(switches)}")

    offline = [str(x.get("name")) for x in health.get("offline_devices", []) if isinstance(x, dict) and x.get("name")]
    if offline:
        lines.append("⚠️ Attention needed - offline devices: " + _joined(offline))

    warnings = [str(x.get("name")) for x in health.get("warnings", []) if isinstance(x, dict) and x.get("name")]
    if warnings:
        lines.append("🔋 Low battery: " + _joined(warnings))

    return "\n\n".join(lines)


__all__ = ["present_home_summary"]
