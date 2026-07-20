from __future__ import annotations

from typing import Any

from control_focus_mode import ControlFocusMode
from presenter import display_payload, safe_debug
from routing_policy import normalise
from semantic_metric_comparison import _SPECS, format_measurement
from semantic_read_intent import SemanticReadIntent


def install_control_focus_power_summary_safe() -> None:
    """Replace the 0.7.1 formatter with a structured-evidence-safe version.

    Semantic metric responses intentionally pass their diagnostic payload through
    ``safe_debug``. Depending on response size that field can therefore be a JSON
    string rather than a dictionary. Power rows themselves remain available in
    ``measurement_readings`` and are the authoritative structured source.
    """

    async def power_summary(self: ControlFocusMode, query: str) -> dict[str, Any]:
        intent = SemanticReadIntent(
            intent="metric_comparison",
            metric="power",
            operation="rank",
            group_by="device",
            scope_kind="all",
            scope_name="",
            entity_names=(),
            top_n=10,
            confidence=1.0,
        )
        answer = dict(await self.metric_executor.execute(intent, query=query))
        all_readings = [
            item
            for item in list(answer.get("measurement_readings") or [])
            if isinstance(item, dict)
        ]
        raw_readings = [item for item in all_readings if not bool(item.get("aggregate"))]
        aggregate = [item for item in all_readings if bool(item.get("aggregate"))]

        # Backward-compatible fallback for test doubles or an older metric executor.
        # Never assume the diagnostic field is a mapping: safe_debug may serialize it.
        if not aggregate:
            technical = answer.get("technical")
            if isinstance(technical, dict):
                aggregate = [
                    item
                    for item in list(technical.get("aggregate_readings") or [])
                    if isinstance(item, dict)
                ]

        # A merged live read should already be unique, but custom drivers can expose
        # the same source through aliases. Keep one current value per device/label.
        unique: dict[str, dict[str, Any]] = {}
        for item in raw_readings:
            key = str(item.get("id") or "").strip() or normalise(str(item.get("label") or ""))
            if not key:
                continue
            unique[key] = item
        readings = sorted(
            unique.values(),
            key=lambda item: (
                -float(item.get("value") or 0.0),
                str(item.get("label") or "").lower(),
            ),
        )
        active = [item for item in readings if float(item.get("value") or 0.0) > 0.05]
        idle = [item for item in readings if float(item.get("value") or 0.0) <= 0.05]
        total = sum(float(item.get("value") or 0.0) for item in active)
        spec = _SPECS["power"]

        if active:
            lines = [
                f"{index}. {item.get('label')}: "
                f"{format_measurement(spec, float(item.get('value') or 0.0))}"
                for index, item in enumerate(active[:20], start=1)
            ]
            message = "Current measured power consumption:\n" + "\n".join(lines)
            message += (
                f"\n\nTotal across {len(active)} active individual reading"
                f"{'s' if len(active) != 1 else ''}: {format_measurement(spec, total)}."
            )
            if idle:
                idle_names = ", ".join(
                    str(item.get("label") or "Unknown") for item in idle[:20]
                )
                message += f"\n0 W / idle readings: {idle_names}."
        elif readings:
            message = (
                f"{len(readings)} selected devices returned power readings, but all are "
                "currently 0 W or effectively idle."
            )
        else:
            message = "No selected device returned a current numeric power reading."

        if aggregate:
            meter = max(aggregate, key=lambda item: float(item.get("value") or 0.0))
            message += (
                f" Whole-home meter: "
                f"{format_measurement(spec, float(meter.get('value') or 0.0))} "
                "(shown separately, not added to the individual-device total)."
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
                "Fresh Hubitat Power Meter values were read and totalled deterministically. "
                "No AI model selected devices or calculated the total."
            ),
        )
        display["summary"] = message
        answer.update(
            {
                "success": bool(readings),
                "route": "mcp-power-summary",
                "intent": "verified-power-summary",
                "message": message,
                "display": display,
                "active_power_readings": active,
                "idle_power_readings": idle,
                "active_power_total_w": total,
                "aggregate_power_readings": aggregate,
                "answered_by": "Deterministic live Hubitat power summary",
                "model": None,
                "technical": safe_debug(
                    {
                        "query": query,
                        "normalised_readings": readings,
                        "active_readings": active,
                        "idle_readings": idle,
                        "active_total_w": total,
                        "aggregate_readings": aggregate,
                    }
                ),
            }
        )
        answer.pop("ai_provider", None)
        return answer

    ControlFocusMode.power_summary = power_summary


__all__ = ["install_control_focus_power_summary_safe"]
