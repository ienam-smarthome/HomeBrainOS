"""Validate model-authored hypothesis clock references against linked events.

A record-ID reference is not sufficient to validate free-form prose: the
model may silently render a 00:41 BST command as 23:41 *without* saying UTC.
Reject ambiguous/unlinked clock strings before admitting a model hypothesis
to the user-facing report. This never changes canonical evidence or claims.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Iterable
from .evidence import CaseFile
from .temporal_scope import IncidentWindow

_CLOCK = re.compile(
    r"(?<![\dT])(?P<clock>(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?)(?!\d)"
)


def hypothesis_clock_issues(
    explanation: str,
    case: CaseFile,
    record_ids: Iterable[str],
    incident_window: IncidentWindow | None,
) -> tuple[str, ...]:
    """Return opaque error codes; no model-authored text is emitted as truth."""
    if not isinstance(explanation, str):
        return ("invalid_hypothesis_text",)
    matched=list(_CLOCK.finditer(explanation))
    if not matched:
        return ()
    try:
        zone=ZoneInfo(incident_window.zone_name) if incident_window else None
    except Exception:
        zone=None
    evidence={r.record_id:r for r in case.records}
    allowed=set()
    for rid in record_ids:
        row=evidence.get(rid)
        if row is None:
            continue
        try:
            stamp=datetime.fromisoformat(row.timestamp_utc)
            if stamp.tzinfo is None:
                continue
            utc=stamp.astimezone(timezone.utc)
            allowed.add((utc.strftime("%H:%M"),"UTC"))
            allowed.add((utc.strftime("%H:%M:%S"),"UTC"))
            if zone:
                local=stamp.astimezone(zone)
                tag=local.tzname()
                if tag:
                    allowed.add((local.strftime("%H:%M"),tag))
                    allowed.add((local.strftime("%H:%M:%S"),tag))
        except (ValueError, TypeError, OverflowError):
            continue
    for hit in matched:
        after=explanation[hit.end():hit.end()+14]
        unit=re.match(r"\s+(BST|GMT|UTC)\b",after,re.IGNORECASE)
        if unit is None:
            return ("unqualified_hypothesis_clock",)
        if (hit.group("clock"),unit.group(1).upper()) not in allowed:
            return ("hypothesis_clock_not_linked_to_record",)
    return ()


__all__=["hypothesis_clock_issues"]
