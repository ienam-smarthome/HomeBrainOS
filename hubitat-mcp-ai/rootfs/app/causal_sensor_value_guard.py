"""Keep observed focal sensor values exact in read-only causal prose.

A source-typed motion=inactive event is not generic "sensor activity".
Only repair when a host-correlated focal clock and an independent successful
bounded native event window agree on attribute, value and event timestamp.
Do not infer sensor state from journal reception time, empty history or a
different historical switch transition.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


_VAGUE_SENSOR_REPORT = re.compile(
    r"\b(?P<verb>reported|recorded|detected|observed)\s+"
    r"(?:(?:some|nearby)\s+)?(?:activity|motion|presence)\b",
    re.I,
)
_TERMS = frozenset({"motion", "sensor", "presence", "occupancy", "activity"})
_EXPLICIT = re.compile(r"\b(?:active|inactive|present|not[_ -]present)\b", re.I)


def _clock(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(timezone.utc) if result.tzinfo is not None else None


def _focal_facts(evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    focal: set[tuple[str, datetime]] = set()
    correlations: list[dict[str, str]] = []
    native: set[tuple[str, str, str, datetime]] = set()
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        if (receipt.get("tool") == "homebrain_causal_secondary_correlation"
                and (boundary := _clock(details.get("requestedBoundary"))) is not None):
            focal.add((str(details.get("subject") or "").casefold(), boundary))
            for sensor in details.get("sensors") or []:
                if not isinstance(sensor, dict):
                    continue
                label = str(sensor.get("label") or "").strip()
                for correlation in sensor.get("relevantCorrelations") or []:
                    if not isinstance(correlation, dict):
                        continue
                    at = _clock(correlation.get("sensorEvent"))
                    transition = _clock(correlation.get("subjectTransition"))
                    name = str(correlation.get("attribute") or sensor.get("attribute") or "").strip()
                    value = str(correlation.get("eventValue") or "").strip()
                    if at and transition == boundary and label and name and value:
                        correlations.append({
                            "label": label, "attribute": name, "value": value,
                            "eventUtc": at.isoformat(), "subject": str(details.get("subject") or ""),
                        })
        elif (receipt.get("sub_tool") == "hub_list_device_events"
              and details.get("windowVerified") is True):
            label = str(details.get("label") or "").strip().casefold()
            for row in details.get("events") or []:
                if not isinstance(row, dict):
                    continue
                at = _clock(row.get("date"))
                if at:
                    native.add((
                        label,
                        str(row.get("name") or "").casefold(),
                        str(row.get("value") or "").casefold(),
                        at,
                    ))
    if len(focal) != 1:
        return []
    return [
        fact for fact in correlations
        if (
            fact["label"].casefold(), fact["attribute"].casefold(),
            fact["value"].casefold(), _clock(fact["eventUtc"])
        ) in native
    ]


def guard_focal_sensor_value_precision(
    message: str, evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Replace ambiguous reported activity only with uniquely verified values.

    Require an unambiguous sensor label token in the answer line. Do not
    rewrite references to different sensors, previously completed intervals,
    tables, code blocks or explicit active/inactive observations.
    """
    original = str(message or "")
    facts = _focal_facts(evidence)
    if not facts:
        return original, False
    changed = False
    lines = []
    in_fence = False
    for raw in original.splitlines(keepends=True):
        stripped = raw.strip()
        if stripped.startswith((chr(96) * 3, "~" * 3)):
            in_fence = not in_fence
        if (in_fence or stripped.startswith("|")
                or not _VAGUE_SENSOR_REPORT.search(raw)
                or _EXPLICIT.search(raw)):
            lines.append(raw)
            continue
        words = set(re.findall(r"[a-zA-Z]{4,}", raw.casefold()))
        matched = []
        for fact in facts:
            label_terms = set(re.findall(r"[a-zA-Z]{4,}", fact["label"].casefold()))
            # Distinctive tokens only: the role word 'motion' alone cannot
            # match every motion sensor in a room.
            distinct = label_terms - _TERMS - {"room", "living", "computer", "example"}
            if words & distinct:
                matched.append(fact)
        unique = {(fact["attribute"], fact["value"]) for fact in matched}
        if len(matched) == 1 and len(unique) == 1:
            fact = matched[0]
            patched = _VAGUE_SENSOR_REPORT.sub(
                lambda m: f'{m.group("verb")} {fact["attribute"]}={fact["value"]}',
                raw,
            )
            if patched != raw:
                changed = True
                raw = patched
        lines.append(raw)
    return "".join(lines), changed


__all__ = ["guard_focal_sensor_value_precision"]
