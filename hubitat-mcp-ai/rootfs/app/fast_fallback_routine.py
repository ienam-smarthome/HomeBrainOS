from __future__ import annotations

from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_device_health import FastFallbackRouter as DeviceHealthFastFallbackRouter
from fast_fallback_live import live_attributes
from presenter import display_payload


class FastFallbackRouter(DeviceHealthFastFallbackRouter):
    """Authoritative routine evidence provider for the natural Ollama agent."""

    async def answer(self, query: str) -> dict[str, Any]:
        q = _normalise(query)
        if "motion" in q and any(
            term in q
            for term in (
                "active",
                "detected",
                "which",
                "what",
                "show",
                "list",
                "where",
            )
        ):
            return await self._active_motion()
        return await super().answer(query)

    async def _active_motion(self) -> dict[str, Any]:
        result = await self._live_devices("Motion Sensor")
        active: list[str] = []
        for item in self._device_rows(result.data):
            if _normalise(live_attributes(item).get("motion")) == "active":
                active.append(_label(item) or str(_device_id(item)))
        active = sorted(dict.fromkeys(active), key=str.lower)

        if active:
            message = (
                f"{len(active)} motion sensor{'' if len(active) == 1 else 's'} currently "
                "reporting active: " + ", ".join(active) + "."
            )
        else:
            message = "No motion sensors are currently reporting active."

        display = display_payload(
            "active-motion",
            "Active motion",
            subtitle=(
                f"{len(active)} sensor{'' if len(active) == 1 else 's'} reporting active"
                if active
                else "No active motion"
            ),
            metrics=[
                {"label": "Active", "value": str(len(active)), "icon": "🏃"},
            ],
            items=[
                {
                    "icon": "🏃",
                    "title": name,
                    "value": "Active",
                    "tone": "warning",
                }
                for name in active
            ],
            note="States are read directly from Hubitat MCP currentStates.",
        )
        return self._decorate(
            self._response(message, "fallback-active-motion", True, result),
            display,
            result,
        )


__all__ = ["FastFallbackRouter"]
