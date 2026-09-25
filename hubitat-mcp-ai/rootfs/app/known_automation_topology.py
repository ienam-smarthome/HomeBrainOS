"""Configured external-automation topology for causal investigations.

This module intentionally separates *configuration evidence* from *execution
provenance*. A configured automation can make an external route concrete and can
be compared with live Hubitat timestamps, but it never proves that the external
platform executed that automation for a particular transition.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any


def _normalized_label(value: Any) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split()
    )


def _labels(item: dict[str, Any]) -> set[str]:
    values: list[Any] = [
        item.get("device"),
        item.get("label"),
        item.get("name"),
    ]
    aliases = item.get("aliases")
    if isinstance(aliases, list):
        values.extend(aliases)
    return {
        normalized
        for value in values
        if (normalized := _normalized_label(value))
    }


def _transition(value: Any) -> str:
    normalized = _normalized_label(value)
    if normalized in {"on", "turn on", "switch on"}:
        return "on"
    if normalized in {"off", "turn off", "switch off"}:
        return "off"
    return normalized


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.search(r"[+-]\d{4}$", text):
        text = text[:-5] + text[-5:-2] + ":" + text[-2:]
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def parse_known_automations(value: Any) -> list[dict[str, Any]]:
    """Parse a JSON/list configuration into a conservative normalized topology."""

    raw = value
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            raw = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    if isinstance(raw, dict):
        nested = raw.get("automations")
        raw = nested if isinstance(nested, list) else [raw]
    if not isinstance(raw, list):
        return []

    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        platform = str(item.get("platform") or "").strip()
        trigger_mode = str(
            item.get("triggerMode") or item.get("trigger_mode") or "any"
        ).strip().casefold()
        trigger_mode = "all" if trigger_mode == "all" else "any"

        triggers = [
            dict(row)
            for row in (item.get("triggers") or [])
            if isinstance(row, dict) and _labels(row)
        ]

        raw_derived = item.get("derivedSensors")
        if not isinstance(raw_derived, list):
            raw_derived = item.get("derived_sensors")
        derived_sensors: list[dict[str, Any]] = []
        for row in raw_derived or []:
            if not isinstance(row, dict) or not _labels(row):
                continue
            sources: list[dict[str, Any]] = []
            for source in row.get("sources") or row.get("inputs") or []:
                if isinstance(source, str):
                    source = {"device": source}
                if isinstance(source, dict) and _labels(source):
                    sources.append(dict(source))
            if not sources:
                continue
            normalized = dict(row)
            source_mode = str(
                row.get("sourceMode") or row.get("source_mode") or "combined"
            ).strip().casefold()
            normalized["sourceMode"] = (
                source_mode if source_mode in {"any", "all"} else "combined"
            )
            normalized["sources"] = sources
            derived_sensors.append(normalized)

        actions: list[dict[str, Any]] = []
        for row in item.get("actions") or []:
            if not isinstance(row, dict) or not _labels(row):
                continue
            action_transition = _transition(
                row.get("transition") or row.get("action") or row.get("command")
            )
            if action_transition not in {"on", "off"}:
                continue
            normalized = dict(row)
            normalized["transition"] = action_transition
            actions.append(normalized)

        if not name or not triggers or not actions:
            continue
        result.append({
            "name": name,
            "platform": platform or "External platform",
            "triggerMode": trigger_mode,
            "triggers": triggers,
            "derivedSensors": derived_sensors,
            "actions": actions,
        })
    return result


def _requested_sensor_edges(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    requested = _timestamp(analysis.get("requestedBoundary"))
    if requested is None:
        return []

    result: list[dict[str, Any]] = []
    sensors = [
        row
        for row in (analysis.get("sensors") or [])
        if isinstance(row, dict)
    ]
    if not sensors and isinstance(analysis.get("sensor"), dict):
        sensors = [analysis["sensor"]]

    for sensor in sensors:
        label = str(sensor.get("label") or "").strip()
        if not label or not sensor.get("requestedMatched"):
            continue
        for row in sensor.get("relevantCorrelations") or []:
            if not isinstance(row, dict):
                continue
            subject_time = _timestamp(row.get("subjectTransition"))
            if subject_time is None:
                continue
            if abs((subject_time - requested).total_seconds()) > 0.25:
                continue
            try:
                signed_delta = float(row.get("signedDeltaSeconds"))
            except (TypeError, ValueError):
                continue
            result.append({
                "label": label,
                "normalizedLabel": _normalized_label(label),
                "signedDeltaSeconds": signed_delta,
                "producerLabels": [
                    str(value).strip()
                    for value in (sensor.get("producerLabels") or [])
                    if str(value).strip()
                ],
            })
            break
    return result



def prioritize_known_automation_sensor_candidates(
    candidates: list[dict[str, Any]],
    known_automations: list[dict[str, Any]] | None,
    *,
    subject: Any,
    transition: Any,
    limit: int = 2,
) -> tuple[list[dict[str, Any]], bool]:
    """Prefer configured source sensors over their derived/composite signals.

    Candidate discovery remains capability/attribute-shape grounded elsewhere.
    This helper only reorders already-safe occupancy candidates for a configured
    automation that targets the requested subject transition. If fewer source
    sensors are available, a configured derived sensor can still fill a bounded
    slot before unrelated room sensors.

    Returns (selected_candidates, topology_plan_used).
    """

    rows = [dict(row) for row in candidates if isinstance(row, dict)]
    bounded_limit = max(1, int(limit))
    if not rows or not known_automations:
        return rows[:bounded_limit], False

    subject_key = _normalized_label(subject)
    transition_key = _transition(transition)
    if not subject_key or transition_key not in {"on", "off"}:
        return rows[:bounded_limit], False

    source_labels: set[str] = set()
    derived_labels: set[str] = set()

    for automation in known_automations:
        if not isinstance(automation, dict):
            continue
        action_matches = any(
            isinstance(action, dict)
            and subject_key in _labels(action)
            and _transition(action.get("transition")) == transition_key
            for action in (automation.get("actions") or [])
        )
        if not action_matches:
            continue

        for trigger in automation.get("triggers") or []:
            if isinstance(trigger, dict):
                source_labels.update(_labels(trigger))

        for derived in automation.get("derivedSensors") or []:
            if not isinstance(derived, dict):
                continue
            derived_labels.update(_labels(derived))
            for source in derived.get("sources") or []:
                if isinstance(source, dict):
                    source_labels.update(_labels(source))

    if not source_labels and not derived_labels:
        return rows[:bounded_limit], False

    ranked: list[tuple[int, int, dict[str, Any]]] = []
    topology_candidate_found = False
    for index, row in enumerate(rows):
        candidate = row.get("candidate")
        candidate_data = candidate if isinstance(candidate, dict) else {}
        label = (
            row.get("name")
            or candidate_data.get("label")
            or candidate_data.get("name")
        )
        normalized = _normalized_label(label)
        if normalized in source_labels:
            role_rank = 0
            topology_candidate_found = True
        elif normalized in derived_labels:
            role_rank = 1
            topology_candidate_found = True
        else:
            role_rank = 2
        ranked.append((role_rank, index, row))

    if not topology_candidate_found:
        return rows[:bounded_limit], False

    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked[:bounded_limit]], True

def match_known_automations(
    analysis: dict[str, Any],
    known_automations: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Match live requested-boundary evidence to configured external topology."""

    if not isinstance(analysis, dict) or not known_automations:
        return []

    subject = _normalized_label(analysis.get("subject"))
    transition = _transition(analysis.get("transition"))
    if not subject or transition not in {"on", "off"}:
        return []

    requested_edges = _requested_sensor_edges(analysis)
    matches: list[dict[str, Any]] = []

    for automation in known_automations:
        if not isinstance(automation, dict):
            continue
        action_matches = [
            action
            for action in (automation.get("actions") or [])
            if isinstance(action, dict)
            and subject in _labels(action)
            and _transition(action.get("transition")) == transition
        ]
        if not action_matches:
            continue

        matched_triggers: list[dict[str, Any]] = []
        for trigger in automation.get("triggers") or []:
            if not isinstance(trigger, dict):
                continue
            trigger_labels = _labels(trigger)
            for edge in requested_edges:
                if edge.get("normalizedLabel") not in trigger_labels:
                    continue
                matched_triggers.append({
                    "configuredTrigger": (
                        trigger.get("device")
                        or trigger.get("label")
                        or trigger.get("name")
                    ),
                    "sensorLabel": edge.get("label"),
                    "signedDeltaSeconds": edge.get("signedDeltaSeconds"),
                    "producerLabels": edge.get("producerLabels") or [],
                })

        matched_derived_sensors: list[dict[str, Any]] = []
        for derived in automation.get("derivedSensors") or []:
            if not isinstance(derived, dict):
                continue
            derived_labels = _labels(derived)
            source_names = [
                str(
                    source.get("device")
                    or source.get("label")
                    or source.get("name")
                    or ""
                ).strip()
                for source in (derived.get("sources") or [])
                if isinstance(source, dict)
                and str(
                    source.get("device")
                    or source.get("label")
                    or source.get("name")
                    or ""
                ).strip()
            ]
            if not source_names:
                continue
            for edge in requested_edges:
                if edge.get("normalizedLabel") not in derived_labels:
                    continue
                matched_derived_sensors.append({
                    "derivedSensor": (
                        derived.get("device")
                        or derived.get("label")
                        or derived.get("name")
                    ),
                    "sensorLabel": edge.get("label"),
                    "signedDeltaSeconds": edge.get("signedDeltaSeconds"),
                    "producerLabels": edge.get("producerLabels") or [],
                    "kind": str(derived.get("kind") or "sensor").strip(),
                    "sourceMode": str(
                        derived.get("sourceMode") or "combined"
                    ).strip(),
                    "sourceTriggers": source_names,
                })

        if not matched_triggers and not matched_derived_sensors:
            continue

        trigger_mode = (
            "all"
            if str(automation.get("triggerMode") or "").casefold() == "all"
            else "any"
        )
        if trigger_mode == "all":
            matched_configured = {
                _normalized_label(row.get("configuredTrigger"))
                for row in matched_triggers
            }
            required_configured = {
                _normalized_label(
                    row.get("device") or row.get("label") or row.get("name")
                )
                for row in (automation.get("triggers") or [])
                if isinstance(row, dict)
            }
            if required_configured - matched_configured:
                continue

        direct_deltas = [
            float(row["signedDeltaSeconds"])
            for row in matched_triggers
            if isinstance(row.get("signedDeltaSeconds"), (int, float))
        ]
        derived_deltas = [
            float(row["signedDeltaSeconds"])
            for row in matched_derived_sensors
            if isinstance(row.get("signedDeltaSeconds"), (int, float))
        ]
        if any(delta <= 0.05 for delta in direct_deltas):
            timing_status = "timing-consistent"
        elif any(delta <= 0.05 for delta in derived_deltas):
            timing_status = "derived-signal-consistent"
        else:
            timing_status = "configured-candidate"
        matches.append({
            "name": str(automation.get("name") or "").strip(),
            "platform": str(automation.get("platform") or "External platform").strip(),
            "triggerMode": trigger_mode,
            "subject": analysis.get("subject"),
            "transition": transition,
            "matchedTriggers": matched_triggers,
            "matchedDerivedSensors": matched_derived_sensors,
            "configuredTriggers": [
                str(
                    row.get("device")
                    or row.get("label")
                    or row.get("name")
                    or ""
                ).strip()
                for row in (automation.get("triggers") or [])
                if isinstance(row, dict)
            ],
            "timingStatus": timing_status,
            "evidenceSource": "configured_external_topology",
        })

    return sorted(
        matches,
        key=lambda item: (
            (
                0
                if item.get("timingStatus") == "timing-consistent"
                else 1
                if item.get("timingStatus") == "derived-signal-consistent"
                else 2
            ),
            -len(item.get("matchedTriggers") or []),
            -len(item.get("matchedDerivedSensors") or []),
            str(item.get("name") or ""),
        ),
    )


def render_known_automation_summary(
    matches: list[dict[str, Any]] | None,
    *,
    subject: str,
    role_word: str,
) -> str | None:
    """Render one concise topology-aware candidate without claiming execution."""

    rows = [row for row in (matches or []) if isinstance(row, dict)]
    if not rows:
        return None

    match = rows[0]
    name = str(match.get("name") or "configured automation").strip()
    platform = str(match.get("platform") or "External platform").strip()
    configured = [
        value
        for value in (match.get("configuredTriggers") or [])
        if str(value).strip()
    ]
    trigger_text = ""
    if configured:
        trigger_text = " from " + "/".join(dict.fromkeys(map(str, configured)))

    timing_status = str(match.get("timingStatus") or "")
    matched = [
        row for row in (match.get("matchedTriggers") or [])
        if isinstance(row, dict)
    ]
    direct_before = [
        row
        for row in matched
        if isinstance(row.get("signedDeltaSeconds"), (int, float))
        and float(row["signedDeltaSeconds"]) <= 0.05
    ]
    derived = [
        row for row in (match.get("matchedDerivedSensors") or [])
        if isinstance(row, dict)
    ]
    derived_before = [
        row
        for row in derived
        if isinstance(row.get("signedDeltaSeconds"), (int, float))
        and float(row["signedDeltaSeconds"]) <= 0.05
    ]

    prefix = (
        f"- **Known automation:** {platform} “{name}” is configured to turn "
        f"{subject} {role_word}{trigger_text}."
    )
    if timing_status == "timing-consistent" and direct_before:
        row = min(
            direct_before,
            key=lambda item: abs(float(item.get("signedDeltaSeconds") or 0)),
        )
        delta = float(row.get("signedDeltaSeconds") or 0)
        sensor = str(row.get("sensorLabel") or "the matching trigger").strip()
        if abs(delta) < 0.05:
            timing = f"{sensor} was reported at effectively the same time"
        else:
            number = f"{abs(delta):.2f}".rstrip("0").rstrip(".")
            timing = f"{sensor} was reported {number}s before"
        return (
            prefix
            + f" {timing}, which is consistent with that configured upstream "
            "route; Hubitat cannot prove the external automation executed this run."
        )

    if timing_status == "derived-signal-consistent" and derived_before:
        return (
            prefix
            + " A configured composite sensor aligned with this transition, which "
            "supports the same upstream route but does not identify which source "
            "sensor fired; Hubitat cannot prove the external automation executed "
            "this run."
        )

    return (
        prefix
        + " The matching Hubitat-visible trigger/composite report arrived after "
        "the device transition, so received event order cannot prove this run; "
        "because the automation is upstream, it remains a concrete configured "
        "candidate."
    )


def render_composite_sensor_summary(
    matches: list[dict[str, Any]] | None,
) -> str | None:
    """Explain configured derived sensors without counting them independently."""

    rows = [row for row in (matches or []) if isinstance(row, dict)]
    for match in rows:
        platform = str(match.get("platform") or "External platform").strip()
        for derived in match.get("matchedDerivedSensors") or []:
            if not isinstance(derived, dict):
                continue
            sensor = str(
                derived.get("derivedSensor")
                or derived.get("sensorLabel")
                or "derived sensor"
            ).strip()
            sources = [
                str(value).strip()
                for value in (derived.get("sourceTriggers") or [])
                if str(value).strip()
            ]
            if not sources:
                continue
            kind = str(derived.get("kind") or "sensor").strip().casefold()
            descriptor = (
                "occupancy signal"
                if kind in {"occupancy", "presence"}
                else "sensor signal"
            )
            source_text = "/".join(dict.fromkeys(sources))
            return (
                f"- **Composite signal:** {sensor} is configured on {platform} as "
                f"a derived {descriptor} from {source_text}. Its nearby report is "
                "part of the same upstream topology, not an independent "
                "confirmation, and it does not identify which source sensor fired."
            )
    return None


def render_known_automation_conclusion(
    matches: list[dict[str, Any]] | None,
) -> str | None:
    rows = [row for row in (matches or []) if isinstance(row, dict)]
    if not rows:
        return None
    match = rows[0]
    name = str(match.get("name") or "configured automation").strip()
    platform = str(match.get("platform") or "External platform").strip()
    if match.get("timingStatus") == "timing-consistent":
        return (
            f"- **Conclusion:** {platform} “{name}” is the configured external "
            "route that matches this light and trigger timing, but Hubitat cannot "
            "prove it executed this exact transition."
        )
    if match.get("timingStatus") == "derived-signal-consistent":
        return (
            f"- **Conclusion:** {platform} “{name}” is the configured external "
            "route consistent with this light and composite-sensor timing, but "
            "Hubitat cannot prove it executed this exact transition or which "
            "source sensor fired."
        )
    return (
        f"- **Conclusion:** {platform} “{name}” is a configured external route "
        "for this light, but Hubitat cannot prove it executed this exact "
        "transition from the received event order."
    )
