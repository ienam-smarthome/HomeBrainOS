"""Coverage proof obligations for focal historical sensor reads.

A returned newest-N page containing only events *after* a requested boundary
cannot be used as negative evidence about activity at that boundary.
The check is source-agnostic and does not infer that data were deleted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _instant(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def assess_local_sensor_history_coverage(
    histories: list[dict[str, Any]], focal_boundary: Any,
) -> dict[str, Any]:
    """Classify returned timestamps, not the real-world continuity of a sensor.

    Having one event before the boundary is *not* sufficient to prove that all
    events were returned. It merely prevents the specific 'all events newer'
    coverage gap from being asserted.
    """
    target = _instant(focal_boundary)
    if target is None:
        return {"status": "unknown-boundary", "preFocalObserved": False}
    observed = []
    counts = {"historiesRead": 0, "historiesWithEvents": 0, "historiesWithPreFocal": 0,
              "historiesWithOnlyLater": 0, "historiesWithoutEvents": 0}
    for history in histories:
        if not isinstance(history, dict):
            continue
        counts["historiesRead"] += 1
        # events/observedEvents is the collected source page. boundaryEvents may
        # be a condensed derivative, so avoid double counting.
        source = history.get("observedEvents")
        if not isinstance(source, list):
            source = history.get("events")
        if not isinstance(source, list):
            source = history.get("boundaryEvents")
        times = [
            t for row in (source or [])
            if isinstance(row, dict)
            if (t := _instant(row.get("date") or row.get("timestamp"))) is not None
        ]
        if not times:
            counts["historiesWithoutEvents"] += 1
            continue
        observed.extend(times)
        counts["historiesWithEvents"] += 1
        if min(times) <= target:
            counts["historiesWithPreFocal"] += 1
        else:
            counts["historiesWithOnlyLater"] += 1
    gap = bool(
        counts["historiesRead"] > 0
        and counts["historiesWithPreFocal"] == 0
    )
    return {
        "status": "pre-focal-not-observed-in-returned-pages" if gap
        else "at-least-one-pre-focal-event-returned" if observed
        else "no-local-sensor-histories",
        **counts,
        "focalBoundary": target.isoformat(),
        "oldestReturnedEvent": min(observed).isoformat() if observed else None,
        "preFocalObserved": counts["historiesWithPreFocal"] > 0,
        "historicalCompletenessVerified": False,
        "unobservedIsNotInactive": True,
        "gapCanBeCausedByNewestNPage": True,
        "upstreamHistoricalWindowAvailable": False,
    }



def guard_history_gap_claims(
    message: str, graph: dict[str, Any],
) -> tuple[str, bool]:
    """Prevent unavailable local history from becoming a negative causal claim.

    When the newest-N local source pages do not reach the focal time, the
    absence of a matching edge cannot be read as absence of earlier motion.
    """
    off = ((graph.get("transitionEvidence") or {}).get("off") or {})
    coverage = off.get("sensorHistoryCoverage") or {}
    if (
        graph.get("scope") != "single-observed-event"
        or not off.get("observed")
        or coverage.get("status") != "pre-focal-not-observed-in-returned-pages"
    ):
        return str(message or ""), False

    import re
    source = str(message or "")
    changed = False
    output = []
    for raw in source.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        ending = raw[len(line):]
        original = line

        # Do not confuse later active rows with an exhaustive pre-OFF search.
        if (
            line.lstrip().startswith("|")
            and re.search(r"(?i)\bsensor\s+events?\b", line)
            and re.search(r"(?i)inconsistent|after\s+the\s+light|negative", line)
        ):
            line = (
                "| Local sensor history | Returned rows do not reach the focal "
                "OFF boundary | Coverage unavailable |"
            )

        # These statements claim causal exclusivity unsupported by a bounded
        # missing command page and truncated, newer-only local sensor pages.
        elif re.search(
            r"(?i)(?:\bbecause\s+no\s+Hubitat[- ]side\s+command\s+exists\b"
            r"|\bHubitat\s+acted\s+only\s+as\s+a\s+listener\b"
            r"|\bno\s+(?:\x60?off\x60?\s+)?command\s+was\s+issued\s+by\s+the\s+hub\b"
            r"|\b(?:as|because)\s+Hubitat\s+(?:did\s+not|could\s+not)\s+initiate\b"
            r"|\breturned\s+No\s+command\s+producer\s+is\s+established\b)",
            line,
        ):
            if re.match(r"(?i)^\s*\*\s*\*\*External", line):
                line = (
                    "* **External control:** Possible but unverified. A state "
                    "report from a bridge does not establish the command issuer."
                )
            elif re.search(r"(?i)\bConclusion\b\*{0,2}\s*:", line):
                line = (
                    "**Conclusion:** The OFF command producer remains "
                    "unidentified. The returned local sensor history does not "
                    "cover the focal time; no Hubitat or external cause is proven."
                )
            else:
                label = re.match(r"^(\s*(?:[-*+]\s+)?\*\*[^*]+\*\*\s*:\s*)", line)
                prefix = label.group(1) if label else ""
                line = prefix + (
                    "No matching command producer was identified in the "
                    "returned history. This does not exclude an unrecorded "
                    "Hubitat action or external control."
                )
        if line != original:
            changed = True
        output.append(line + ending)
    source = "".join(output)

    if "**Historical sensor coverage:**" not in source:
        note = (
            "**Historical sensor coverage:** The returned local sensor-event "
            "pages do not reach the requested OFF timestamp. Their missing "
            "earlier readings cannot be used to confirm or exclude an "
            "inactivity transition, a five-second timer, or another cause.\n\n"
        )
        heading = re.search(
            r"(?im)^(#{1,6}\s+(?:Causal\s+Assessment|Causal\s+Analysis|"
            r"Evidence\s+Analysis))\s*\n", source
        )
        if heading:
            source = source[:heading.end()] + note + source[heading.end():]
        else:
            source = note + source
        changed = True
    return source, changed

__all__ = ["assess_local_sensor_history_coverage", "guard_history_gap_claims"]
