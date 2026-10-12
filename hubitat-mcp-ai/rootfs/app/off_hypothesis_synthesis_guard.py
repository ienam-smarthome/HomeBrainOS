"""Evidence-based final OFF answer checks, independent of room names and models."""
from __future__ import annotations
import re
from typing import Any


def guard_off_hypothesis_summary(message: str, graph: dict[str, Any]) -> tuple[str, bool]:
    """Ensure material timing contradictions survive model synthesis and local repairs.

    This reports a new timer's infeasibility only; it never excludes earlier
    timers, historical alternative settings, or commands absent from logs.
    """
    source = str(message or "")
    hypotheses = graph.get("offHypotheses") or {}
    if hypotheses.get("status") != "producer-unresolved":
        return source, False
    changed = False
    # The absence of a matching recorded command is a bounded observation.
    unsafe = re.compile(
        r"(?i)This indicates the command did not originate from a "
        r"Hubitat-managed device or app that logs standard commands\."
    )
    source, count = unsafe.subn(
        "The returned command records do not identify an OFF producer; "
        "they cannot exclude unrecorded Hubitat or external commands.", source
    )
    changed |= bool(count)
    # Use normalized lines rather than phrase-specific repairs to remove
    # repeated uncertainty claims that have identical meaning after validation.
    result = []
    seen = set()
    for line in source.splitlines(keepends=True):
        normalized = re.sub(r"[^a-z0-9]+", " ", line.casefold()).strip()
        repeatable = (
            len(normalized) >= 55
            and ("off transition occurred near sensor inactivity" in normalized
                 or "off event was observed but its command producer" in normalized)
        )
        if repeatable and normalized in seen:
            changed = True
            continue
        if repeatable:
            seen.add(normalized)
        result.append(line)
    source = "".join(result)
    comparisons = [
        row for row in hypotheses.get("sensorTimerComparisons") or []
        if row.get("assessment") == "too-soon-for-new-timer"
        and isinstance(row.get("elapsedBeforeOffMs"), (int, float))
        and isinstance(row.get("configuredDelayMs"), (int, float))
    ]
    if comparisons and not re.search(
        r"(?i)(?:too\s+soon|cannot\s+have\s+(?:completed|expired)|"
        r"not\s+enough\s+time|incompatible\s+with\s+(?:a\s+)?new|"
        r"could\s+not\s+have\s+(?:expired|completed))", source
    ):
        row = min(comparisons, key=lambda r: (r["configuredDelayMs"], r["elapsedBeforeOffMs"]))
        sensor = str(row.get("sensor") or "Sensor")
        delta = float(row["elapsedBeforeOffMs"])
        duration = float(row["configuredDelayMs"])
        delta_str = f"{delta:g} ms"
        duration_str = f"{duration / 1000:g} seconds" if duration >= 1000 else f"{duration:g} ms"
        note = (
            f"\n**Timer feasibility:** {sensor} reported inactive {delta_str} before OFF. "
            f"A newly started {duration_str} inactivity timer could not have expired "
            "within that interval. This does not exclude an earlier pending timer, "
            "a different automation or historical configuration.\n"
        )
        source = source.rstrip() + "\n" + note
        changed = True
    return source, changed


__all__ = ["guard_off_hypothesis_summary"]
