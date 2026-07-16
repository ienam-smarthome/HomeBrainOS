from __future__ import annotations

import re
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_dashboard import FastFallbackRouter as DashboardFastFallbackRouter
from fast_fallback_live import live_attributes
from presenter import display_payload, safe_debug


_MOTION_QUERY = re.compile(
    r"^(?:(?:which|what|list|show)\s+)?(?:motion\s+)?sensors?\s+(?:are\s+)?active\??$|^(?:where\s+is\s+)?motion\s+active\??$",
    re.IGNORECASE,
)


class FastFallbackRouter(DashboardFastFallbackRouter):
    """Essential exact-state routes that should never wait for a language model."""

    async def answer(self, query: str) -> dict[str, Any]:
        if _MOTION_QUERY.match(_normalise(query)):
            return await self._active_motion_sensors()
        return await super().answer(query)

    async def _active_motion_sensors(self) -> dict[str, Any]:
        result = await self._live_devices("Motion Sensor")
        rows = self._device_rows(result.data)
        motion_rows = [
            item
            for item in rows
            if _normalise(live_attributes(item).get("motion")) in {"active", "inactive"}
        ]

        # Some MCP/driver combinations do not advertise the standard capability
        # even though currentStates includes motion. Retry the full live summary
        # before claiming that no motion sensors exist.
        if not motion_rows:
            result = await self._live_devices()
            rows = self._device_rows(result.data)
            motion_rows = [
                item
                for item in rows
                if _normalise(live_attributes(item).get("motion"))
                in {"active", "inactive"}
            ]

        active = sorted(
            {
                _label(item) or f"Device {_device_id(item)}"
                for item in motion_rows
                if _normalise(live_attributes(item).get("motion")) == "active"
            },
            key=str.lower,
        )
        total = len(motion_rows)

        if active:
            message = (
                f"{len(active)} motion sensor{'' if len(active) == 1 else 's'} active: "
                + ", ".join(active)
                + "."
            )
        elif total:
            message = "No motion sensors are currently reporting active."
        else:
            message = (
                "The MCP device response did not include any live motion states. "
                "Check that motion devices are selected in MCP Rule Server."
            )

        display = display_payload(
            "motion-active",
            "Active motion sensors",
            subtitle=f"{len(active)} active · {total} states read",
            metrics=[
                {"label": "Active", "value": str(len(active)), "icon": "🏃"},
                {"label": "Motion states read", "value": str(total), "icon": "📡"},
            ],
            items=[
                {
                    "icon": "🏃",
                    "title": name,
                    "value": "Active",
                    "tone": "success",
                }
                for name in active
            ],
            note="Live values come from Hubitat MCP currentStates.",
        )
        response = self._response(
            message,
            "fallback-motion-active",
            total > 0,
            result,
        )
        response["display"] = display
        response["technical"] = safe_debug(result.data)
        return response


__all__ = ["FastFallbackRouter"]
