from __future__ import annotations

import json
from typing import Any

import hybrid_assistant_mode as hybrid_mode
from control_focus_mode import ControlFocusMode
from power_accounting import PowerAccountingService
from presenter import display_payload, safe_debug
from semantic_metric_comparison import _SPECS, format_measurement


def _technical_mapping(value: Any) -> dict[str, Any]:
    """Return accounting diagnostics whether supplied as a mapping or safe-debug JSON."""

    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dict(decoded) if isinstance(decoded, dict) else {}
    return {}


async def shared_power_summary(self: ControlFocusMode, query: str) -> dict[str, Any]:
    """Build the current-device power summary from the accounting discovery path."""

    accounting = PowerAccountingService(self.application)
    source = dict(await accounting.answer(query))
    active = [
        dict(item)
        for item in list(source.get("active_power_readings") or [])
        if isinstance(item, dict)
    ]
    technical = _technical_mapping(source.get("technical"))
    idle = [
        dict(item)
        for item in list(technical.get("idle_readings") or [])
        if isinstance(item, dict)
    ]
    readings = sorted(
        active + idle,
        key=lambda item: (-float(item.get("value") or 0.0), str(item.get("label") or "").lower()),
    )
    total = sum(float(item.get("value") or 0.0) for item in active)
    spec = _SPECS["power"]

    if active:
        lines = [
            f"{index}. {item.get('label')}: {format_measurement(spec, float(item.get('value') or 0.0))}"
            for index, item in enumerate(active[:20], start=1)
        ]
        message = "Current measured power consumption:\n" + "\n".join(lines)
        message += (
            f"\n\nTotal across {len(active)} active individual reading"
            f"{'s' if len(active) != 1 else ''}: {format_measurement(spec, total)}."
        )
        if idle:
            idle_names = ", ".join(str(item.get("label") or "Unknown") for item in idle[:20])
            message += f"\n0 W / idle readings: {idle_names}."
    elif readings:
        message = (
            f"{len(readings)} monitored devices returned power readings, but all are currently "
            "0 W or effectively idle."
        )
    else:
        message = (
            "No monitored device returned a current numeric power reading after bounded detail checks."
        )

    items = [
        {
            "icon": "⚡",
            "title": str(item.get("label") or "Unknown device"),
            "value": format_measurement(spec, float(item.get("value") or 0.0)),
            "subtitle": str(item.get("room") or "No room assigned"),
            "tone": "warning" if index == 0 and active else None,
        }
        for index, item in enumerate(readings[:20])
    ]
    display = display_payload(
        "verified-power-summary",
        "Current power consumption",
        subtitle=f"{len(readings)} live numeric readings",
        metrics=[
            {"label": "Active draw", "value": format_measurement(spec, total), "icon": "⚡"},
            {"label": "Active readings", "value": str(len(active)), "icon": "📡"},
            {"label": "0 W / idle", "value": str(len(idle)), "icon": "💤"},
        ],
        items=items,
        note=(
            "Power devices were discovered through the same bounded inventory and detail fallback "
            "used by whole-house accounting. Missing power attributes are not counted as 0 W."
        ),
    )
    display["summary"] = message

    return {
        "success": bool(readings),
        "route": "mcp-power-summary",
        "intent": "verified-power-summary",
        "message": message,
        "display": display,
        "active_power_readings": active,
        "idle_power_readings": idle,
        "active_power_total_w": total,
        "numeric_reading_count": len(readings),
        "active_reading_count": len(active),
        "idle_reading_count": len(idle),
        "answered_by": "Deterministic shared Hubitat power discovery",
        "model": None,
        "technical": safe_debug(
            {
                "query": query,
                "shared_power_discovery": True,
                "targeted_fallback_used": technical.get("targeted_fallback_used"),
                "targeted_detail": technical.get("targeted_detail"),
                "active_readings": active,
                "idle_readings": idle,
                "active_total_w": total,
            }
        ),
        "version": getattr(self.application, "VERSION", None),
    }


def install_shared_power_summary_bridge() -> None:
    """Patch the existing service class without adding another ask wrapper."""

    ControlFocusMode.power_summary = shared_power_summary
    # Preserve the historical public export while pointing it at the real class.
    hybrid_mode.OctopusEnergySummary = hybrid_mode.OctopusLiveMeterSummary


__all__ = ["install_shared_power_summary_bridge", "shared_power_summary"]
