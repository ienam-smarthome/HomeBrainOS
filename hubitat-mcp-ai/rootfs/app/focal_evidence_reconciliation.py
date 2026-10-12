"""Evidence reconciliation contracts for a single historical device transition.

Source-class and time-window distinctions must be resolved before synthesis:
MCP verified bounds do not make history complete; local WebSocket journal
observations cannot prove the initiating actor; app logs are scoped samples.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _instant(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def reconcile_window_coverage(
    coverage: dict[str, Any],
    probes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Independent presence of verified MCP absolute windows, not completeness.

    An original newest-N coverage assessment may say 'no pre-focal rows'.
    A successful later absolute window read must supersede this narrow
    observation without pretending that gaps/omitted events cannot exist.
    """
    updated = dict(coverage or {})
    selected = [
        row for row in probes
        if isinstance(row, dict) and row.get("status") == "verified-window"
    ]
    attempted = [
        row for row in probes
        if isinstance(row, dict) and row.get("status")
    ]
    updated["upstreamHistoricalWindowAvailable"] = bool(selected)
    updated["verifiedAbsoluteWindowCount"] = len(selected)
    updated["attemptedAbsoluteWindowCount"] = len(attempted)
    updated["verifiedAbsoluteWindowDeviceIds"] = sorted({
        str(row.get("deviceId")) for row in selected
        if row.get("deviceId") not in (None, "")
    })
    updated["historicalCompletenessVerified"] = False
    updated["unobservedIsNotInactive"] = True
    updated["absoluteWindowsAreNotExhaustiveProof"] = True
    if selected:
        updated["coverageSources"] = "verified-bounded-MCP-windows"
        # The former status might have represented newer-only local pages.
        # Never retain that as the final statement about ALL returned sources.
        if updated.get("status") == "pre-focal-not-observed-in-returned-pages":
            updated["status"] = "verified-window-available-coverage-incomplete"
    return updated


def summarize_journal_app_logs(
    result: dict[str, Any] | None, *, app_id: str,
    since: str, until: str, native_count: int | None,
) -> dict[str, Any]:
    """Scoped, private-message-free statement about log evidence.

    One source being empty does not prove the app did not execute; even a
    nonempty log is not an OFF command unless its semantics independently
    establish one. Never expose app-log message text in the graph/summary.
    """
    records = result.get("events", []) if isinstance(result, dict) else []
    logs = [
        row for row in records
        if isinstance(row, dict) and row.get("stream") == "logs"
        and str(row.get("app_id") or "") == str(app_id)
    ]
    gaps = result.get("gaps", []) if isinstance(result, dict) else []
    bases = sorted({
        str(row.get("timestamp_basis") or "unknown") for row in logs
    })
    return {
        "appId": str(app_id),
        "scopeSince": str(since),
        "scopeUntil": str(until),
        "journalChecked": isinstance(result, dict),
        "journalCount": len(logs) if isinstance(result, dict) else None,
        "nativeMcpCount": native_count,
        "journalTimestampBases": bases,
        "journalGapCount": len(gaps) if isinstance(gaps, list) else None,
        "coverageComplete": False,
        "zeroRowsDoNotProveNonexecution": True,
        "messagesOmittedFromTrace": True,
        "commandProducerVerifiedByTheseCounts": False,
        "status": (
            "unavailable" if result is None
            else "archived-logs-observed" if logs
            else "no-archived-logs-in-bounded-window"
        ),
    }


def guard_unproven_on_button_initiation(
    message: str, graph: dict[str, Any],
) -> tuple[str, bool]:
    """Do not elevate near-synchronous button events into direct ON causation.

    A verified direct initiating ON command is handled elsewhere; otherwise
    phrases asserting a physical push as the initiator overstate provenance,
    particularly when the button event was *reported after* the ON state.
    """
    import re
    original = str(message or "")
    if (
        (graph.get("transitionEvidence") or {}).get("on", {})
        .get("directCommand")
    ):
        return original, False
    pattern = re.compile(
        r"(?:was\s+)?initiated\s+by\s+(?:a\s+)?(?:physical\s+)?"
        r"(?:button\s+)?push\s+(?:of|on)\s+"
        r"(?:\*\*)?([^,.;\n|]{3,100})",
        re.I,
    )
    changed = False

    def sub(match: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        label = str(match.group(1) or "").strip()
        return (
            "was closely associated with a physical button push"
            + (f" of {label}" if label else "")
            + " (the reporting order does not prove it initiated ON)"
        )

    return pattern.sub(sub, original), changed



def reconcile_focal_archived_sensor_evidence(
    receipts: list[dict[str, Any]], *, subject: str, off_time: str,
) -> dict[str, Any]:
    """Keep partial archived observations separate from bounded MCP history.

    A verified since/until request guarantees applied bounds, not event rows.
    Collector reception timestamps must not be treated as initiating events.
    """
    focus = _instant(off_time)
    if focus is None:
        return {}
    for receipt in reversed(receipts):
        if receipt.get("tool") != "homebrain_causal_secondary_correlation":
            continue
        data = receipt.get("details") or {}
        if not isinstance(data, dict) or data.get("subject") != subject:
            continue
        boundary = _instant(data.get("requestedBoundary"))
        if boundary is None or abs((focus - boundary).total_seconds()) > 0.01:
            continue
        archive = data.get("historicalJournal") or {}
        if not isinstance(archive, dict):
            continue
        observations, sources = [], []
        for sensor in (archive.get("sensors") or [])[:2]:
            if not isinstance(sensor, dict):
                continue
            device_id = str(sensor.get("deviceId") or "")
            sources.append({
                "deviceId": device_id,
                "label": str(sensor.get("label") or ""),
                "recordedCount": int(sensor.get("eventCount") or 0),
                "gapCount": int(sensor.get("gapCount") or 0),
                "coverageComplete": False,
            })
            for item in (sensor.get("events") or [])[:10]:
                if not isinstance(item, dict):
                    continue
                when = _instant(item.get("observedAt"))
                if when is None:
                    continue
                basis = str(item.get("timestampBasis") or "unknown")
                observations.append({
                    "deviceId": device_id, "label": str(sensor.get("label") or ""),
                    "attribute": str(sensor.get("attribute") or ""),
                    "value": str(item.get("value") or ""),
                    "observedAt": when.isoformat(),
                    "timestampBasis": basis,
                    "receptionDeltaFromOffMs": round(
                        (when - focus).total_seconds() * 1000, 1
                    ),
                    "deltaRepresentsOriginalEventOrdering": basis == "source",
                    "offCommandProducerEstablished": False,
                })
        if not sources:
            return {}
        verified = [
            row for row in (data.get("focalWindowRetrieval") or [])
            if isinstance(row, dict) and row.get("status") == "verified-window"
        ]
        observations.sort(key=lambda row: row["observedAt"])
        return {
            "status": "partial-archived-observations" if observations
                      else "archive-observations-not-retained",
            "sources": sources,
            "observations": observations[:20],
            "archivedObservationCount": len(observations),
            "verifiedMcpWindowCount": len(verified),
            "verifiedMcpReturnedEventCount": sum(
                int(row.get("eventCount") or 0) for row in verified
            ),
            "mcpEmptyDoesNotNegateArchivedObservations": True,
            "archiveCoverageComplete": False,
            "collectorReceptionNotOriginalEventTime": True,
            "notProofOfTimerOrOffCommand": True,
        }
    return {}


def guard_sensor_history_source_contradiction(
    message: str, graph: dict[str, Any],
) -> tuple[str, bool]:
    """Correct global absence claims when MCP is empty but archive has rows."""
    import re
    off = (graph.get("transitionEvidence") or {}).get("off") or {}
    count = (off.get("archivedSensorEvidence") or {}).get(
        "archivedObservationCount", 0
    )
    if not isinstance(count, int) or count <= 0:
        return str(message or ""), False
    changed, lines = False, []
    for line in str(message or "").splitlines(keepends=True):
        lower = line.casefold()
        if (
            "sensor" in lower and ("history" in lower or "mcp" in lower)
            and "journal" not in lower
            and re.search(
                r"\b(?:no|zero)\s+(?:(?:recorded|motion|sensor)\s+){0,2}events?\b",
                lower,
            )
        ):
            prefix = re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?", line)
            marker = prefix.group(0) if prefix else ""
            line = (
                marker + "Sensor history: verified MCP windows returned "
                "no sensor event rows, but the Historical Journal retained "
                + str(count) + " partial sensor observations. Collector "
                "reception time is not the original event time; neither an "
                "OFF producer nor a timer execution is proven. Historical "
                "coverage remains incomplete."
                + ("\n" if line.endswith("\n") else "")
            )
            changed = True
        lines.append(line)
    return "".join(lines), changed


__all__ = [
    "reconcile_window_coverage",
    "reconcile_focal_archived_sensor_evidence",
    "guard_sensor_history_source_contradiction",
    "summarize_journal_app_logs",
    "guard_unproven_on_button_initiation",
]
