"""Bounded secondary correlation for externally reported switch transitions."""

from __future__ import annotations

from typing import Any

from causal_evidence_planner import (
    controller_boundary_alignments,
    sensor_transition_correlations,
)


def bridge_boundary_requires_secondary(
    correlations: list[dict[str, Any]],
    transition: str,
) -> bool:
    """Return whether the requested boundary is external device/bridge provenance."""

    action = str(transition or "").strip().casefold()
    role = {"on": "start", "off": "end"}.get(action)
    if role is None:
        return False
    for row in correlations:
        if not isinstance(row, dict):
            continue
        if str(row.get("boundaryRole") or "") != role:
            continue
        if str(row.get("action") or "") != action:
            continue
        producer = row.get("producer")
        if not isinstance(producer, dict):
            continue
        producer_type = str(producer.get("type") or "").strip().casefold()
        producer_label = str(producer.get("label") or "").strip()
        subject = str(row.get("subject") or "").strip()
        if (
            producer_type == "device"
            and producer_label
            and producer_label.casefold() != subject.casefold()
        ):
            return True
    return False


def build_bridge_secondary_summary(
    subject_history: dict[str, Any],
    *,
    transition: str,
    controller_history: dict[str, Any] | None = None,
    sensor_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a bounded deterministic correlation summary.

    This is corroborating evidence only. It never promotes timing correlation to
    proof of a specific automation.
    """

    controller_history = (
        controller_history if isinstance(controller_history, dict) else {}
    )
    sensor_history = sensor_history if isinstance(sensor_history, dict) else {}

    controller_rows = controller_boundary_alignments(
        subject_history,
        controller_history,
        max_delta_seconds=2.0,
    ) if controller_history else []

    sensor_rows = sensor_transition_correlations(
        subject_history,
        sensor_history,
        start_delta_seconds=5.0,
        end_delay_seconds=5.0,
    ) if sensor_history else []

    start_sensor = [
        row for row in sensor_rows
        if str(row.get("boundaryRole") or "") == "start"
    ]
    end_sensor = [
        row for row in sensor_rows
        if str(row.get("boundaryRole") or "") == "end"
    ]
    start_after = sum(
        1 for row in start_sensor
        if float(row.get("signedDeltaSeconds") or 0.0) > 0
    )

    start_controller = [
        row for row in controller_rows
        if str(row.get("boundaryRole") or "") == "start"
    ]
    end_controller = [
        row for row in controller_rows
        if str(row.get("boundaryRole") or "") == "end"
    ]

    temporal = subject_history.get("temporalAnalysis")
    intervals = (
        temporal.get("observedIntervals")
        if isinstance(temporal, dict)
        and isinstance(temporal.get("observedIntervals"), list)
        else []
    )

    return {
        "subject": str(subject_history.get("label") or "").strip(),
        "transition": str(transition or "").strip().casefold(),
        "intervalCount": len(intervals),
        "controller": {
            "label": str(controller_history.get("label") or "").strip() or None,
            "attribute": (
                str(controller_history.get("attribute") or "").strip() or None
            ),
            "alignments": controller_rows[:12],
            "startAlignments": len(start_controller),
            "endAlignments": len(end_controller),
        },
        "sensor": {
            "label": str(sensor_history.get("label") or "").strip() or None,
            "attribute": str(sensor_history.get("attribute") or "").strip() or None,
            "correlations": sensor_rows[:16],
            "startAlignments": len(start_sensor),
            "endAlignments": len(end_sensor),
            "startAfterSubject": start_after,
            "repeatedStartPattern": len(start_sensor) >= 2,
        },
    }


def render_bridge_secondary_summary(
    summary: dict[str, Any],
) -> str | None:
    """Render a cautious deterministic supplement for bridge provenance."""

    if not isinstance(summary, dict):
        return None

    paragraphs: list[str] = []
    controller = summary.get("controller")
    if isinstance(controller, dict) and controller.get("label"):
        label = str(controller.get("label"))
        starts = int(controller.get("startAlignments") or 0)
        ends = int(controller.get("endAlignments") or 0)
        if starts or ends:
            parts: list[str] = []
            if starts:
                parts.append(f"{starts} ON/start alignment(s)")
            if ends:
                parts.append(f"{ends} OFF/end alignment(s)")
            paragraphs.append(
                f"Same-room controller check: {label} had "
                + " and ".join(parts)
                + " within 2 seconds of the compared light boundaries. "
                "This is timing evidence only; it does not by itself prove that "
                "controller initiated those transitions."
            )
        else:
            paragraphs.append(
                f"Same-room controller check: no {label} event aligned within "
                "2 seconds of the compared switch boundaries. That weighs against "
                "this controller for those specific transitions, but does not rule "
                "out other controllers or events outside the checked window."
            )

    sensor = summary.get("sensor")
    if isinstance(sensor, dict) and sensor.get("label"):
        label = str(sensor.get("label"))
        attribute = str(sensor.get("attribute") or "sensor")
        starts = int(sensor.get("startAlignments") or 0)
        ends = int(sensor.get("endAlignments") or 0)
        after = int(sensor.get("startAfterSubject") or 0)
        correlations = [
            row for row in sensor.get("correlations", [])
            if isinstance(row, dict)
        ]

        if starts or ends:
            details: list[str] = []
            for row in correlations[:5]:
                role = str(row.get("boundaryRole") or "").upper()
                signed = float(row.get("signedDeltaSeconds") or 0.0)
                direction = (
                    f"{abs(signed):g}s after"
                    if signed > 0
                    else f"{abs(signed):g}s before"
                    if signed < 0
                    else "at the same time as"
                )
                details.append(
                    f"{role}: {label} "
                    f"{row.get('eventValue')} was recorded {direction} "
                    "the switch boundary"
                )
            paragraphs.append(
                f"Same-room {attribute} correlation: {label} aligned with "
                f"{starts} ON/start and {ends} OFF/end boundary event(s) within "
                "the bounded timing windows. "
                + ("; ".join(details) + "." if details else "")
            )

            if starts >= 2:
                if after >= 2:
                    paragraphs.append(
                        f"Across {starts} recent ON boundaries, {label} repeatedly "
                        f"changed within 5 seconds, and in {after} cases the light "
                        "changed before Hubitat recorded the sensor active edge. "
                        "That repeated ordering is consistent with a shared "
                        "upstream/outside-Hubitat automation path, but it is not "
                        "proof that the sensor directly caused the light or that a "
                        "particular external platform performed the action."
                    )
                else:
                    paragraphs.append(
                        f"The repeated {label} timing is materially stronger than "
                        "a single coincidence, but remains correlation rather than "
                        "proof of a configured automation."
                    )
        else:
            paragraphs.append(
                f"Same-room {attribute} check: {label} had no transition meeting "
                "the bounded correlation windows around the compared switch events."
            )

    if not paragraphs:
        return None
    return "\n\n".join(paragraphs)


__all__ = [
    "bridge_boundary_requires_secondary",
    "build_bridge_secondary_summary",
    "render_bridge_secondary_summary",
]
