"""Typed, conservative OFF hypotheses; never equate state reporter with actor.

Timing evaluates whether a *new* timer started at an observed sensor event
could have completed before OFF. It cannot disprove an earlier running timer.
Configuration is current unless historical execution evidence establishes it.
"""
from __future__ import annotations

import re
from typing import Any

_DELAY = re.compile(
    r"(?:after|delay(?:ed)?(?:\s+by)?|wait(?:ing)?(?:\s+for)?)\s+"
    r"(\d+(?:\.\d+)?)\s*(milliseconds?|msecs?|ms|seconds?|secs?|s|minutes?|mins?|m)\b",
    re.I,
)
_INACTIVE = re.compile(r"\b(?:inactiv\w*|no\s+(?:active\s+)?motion|motion\s+stops?)\b", re.I)


def _delay_ms(text: str) -> list[float]:
    result = []
    for value, unit in _DELAY.findall(text):
        factor = 1 if unit.lower().startswith(("ms", "millisecond", "msec")) else (
            60000 if unit.lower().startswith(("m", "min")) else 1000
        )
        result.append(float(value) * factor)
    return result


def evaluate_off_hypotheses(graph: dict[str, Any]) -> dict[str, Any]:
    """Return falsifiable, source-scoped conclusions without ranking unknown actors."""
    off = ((graph.get("transitionEvidence") or {}).get("off") or {})
    if graph.get("scope") != "single-observed-event" or not off.get("observed"):
        return {"status": "not-applicable", "hypotheses": []}
    direct = off.get("directCommand")
    report = (off.get("state") or {}).get("producer") or {}
    config = ((off.get("notifiedListenerContext") or {}).get("configuration") or {})
    if not config.get("checked"):
        config = ((off.get("appProducerContext") or {}).get("configuration") or {})
    excerpts = config.get("excerpts") or config.get("configured") or []
    if isinstance(excerpts, str):
        excerpts = [excerpts]
    descriptions = [str(s) for s in excerpts]
    timers = sorted(set(
        ms for s in descriptions for clause in re.split(r"[;\n]", s)
        if _INACTIVE.search(clause) for ms in _delay_ms(clause)
    ))
    # Include only genuinely inactive sensor edges; a later sensor edge cannot
    # initiate a new timer before the recorded OFF boundary.
    sensor_edges = [
        row for row in (off.get("sensorCorrelations") or [])
        if isinstance(row, dict)
        and str(row.get("value") or "").casefold() == "inactive"
        and isinstance(row.get("signedDeltaMs"), (float, int))
    ]
    comparisons = []
    for row in sensor_edges:
        elapsed = -float(row["signedDeltaMs"])
        for delay in timers:
            comparisons.append({
                "sensor": row.get("sensor"),
                "elapsedBeforeOffMs": elapsed,
                "configuredDelayMs": delay,
                "newTimerFromThisEdgeCanExplainOff": elapsed >= delay,
                "assessment": (
                    "edge-after-off" if elapsed < 0 else
                    "too-soon-for-new-timer" if elapsed < delay else
                    "timing-compatible-not-execution-proof"
                ),
            })
    return {
        "status": "direct-producer-recorded" if direct else "producer-unresolved",
        "reporter": dict(report) if isinstance(report, dict) else {},
        "reporterIsNotInitiatingActor": True,
        "directCommand": direct,
        "historicalConfigVerified": False,
        "configuredInactivityDelaysMs": timers,
        "sensorTimerComparisons": comparisons,
        "hypotheses": [
            {
                "id": "hubitat-inactivity-rule",
                "status": "direct-command-recorded" if direct else "not-proven",
                "limitations": [
                    "Current configuration does not establish event-time configuration",
                    "Earlier timer scheduling is not excluded by a nearby sensor event",
                    "An empty app log does not prove non-execution",
                ],
            },
            {
                "id": "external-bridge-or-automation",
                "status": "verified" if off.get("externalAutomationIdentityVerified") else "possible-unverified",
                "limitations": ["The state-reporting bridge is not necessarily the actor"],
            },
            {
                "id": "physical-control",
                "status": "possible-unverified",
                "limitations": ["Missing button records cannot exclude physical control"],
            },
        ],
    }


__all__ = ["evaluate_off_hypotheses"]
