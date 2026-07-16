from __future__ import annotations

from typing import Any

from fallback_router import (
    HomeBrainFallbackRouter,
    _attributes,
    _device_id,
    _label,
    _normalise,
)


class FastFallbackRouter(HomeBrainFallbackRouter):
    """Optimised deterministic routes for common dashboard shortcuts."""

    async def _home_status(self) -> dict[str, Any]:
        result = await self._list_devices(detailed=True)
        rows = self._device_rows(result.data)

        lights_on: list[str] = []
        switches_on: list[str] = []
        motion_active: list[str] = []
        low_batteries: list[tuple[str, float]] = []

        for item in rows:
            attrs = _attributes(item)
            label = _label(item) or str(_device_id(item))
            text = _normalise(
                " ".join(
                    str(item.get(key) or "")
                    for key in ("category", "type", "deviceType", "label", "name")
                )
            )
            switch = _normalise(item.get("switch", attrs.get("switch")))
            if switch == "on":
                if "light" in text or "bulb" in text or "lamp" in text:
                    lights_on.append(label)
                else:
                    switches_on.append(label)

            motion = _normalise(item.get("motion", attrs.get("motion")))
            if motion == "active":
                motion_active.append(label)

            battery = item.get("battery", attrs.get("battery"))
            try:
                battery_number = float(str(battery).replace("%", "").strip())
            except Exception:
                battery_number = None
            if battery_number is not None and battery_number <= 20:
                low_batteries.append((label, battery_number))

        lines = []
        if lights_on:
            lines.append(
                f"{len(lights_on)} light{'' if len(lights_on) == 1 else 's'} on: "
                + ", ".join(lights_on)
                + "."
            )
        else:
            lines.append("No lights are currently reporting as on.")

        if switches_on:
            lines.append(
                f"{len(switches_on)} other switch{'' if len(switches_on) == 1 else 'es'} on: "
                + ", ".join(switches_on)
                + "."
            )

        if motion_active:
            lines.append(
                f"Motion active on {len(motion_active)} device"
                f"{'' if len(motion_active) == 1 else 's'}: "
                + ", ".join(motion_active)
                + "."
            )
        else:
            lines.append("No motion sensors are currently active.")

        low_batteries.sort(key=lambda row: (row[1], row[0].lower()))
        if low_batteries:
            lines.append(
                "Low batteries: "
                + ", ".join(f"{name} {value:g}%" for name, value in low_batteries)
                + "."
            )
        else:
            lines.append("No devices at or below 20% were found.")

        return self._response(
            "\n".join(lines),
            "fallback-fast-home-status",
            True,
            result,
        )
