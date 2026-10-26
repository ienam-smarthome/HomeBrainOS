"""Explicit user-date incident boundaries for read-only V2 investigations.

This is a calendar scope contract, not a keyword router or an assertion that
Hubitat event history is complete. Only explicit numeric dates are parsed.
Local midnight boundaries are converted to UTC using the verified hub IANA
timezone, retaining the extra autumn DST hour.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_MONTHS = {
    "january":1, "february":2, "march":3, "april":4,
    "may":5, "june":6, "july":7, "august":8,
    "september":9, "october":10, "november":11, "december":12,
}
_MONTHS_TEXT = "|".join(_MONTHS)
_RANGE = re.compile(
    rf"\b(\d{{1,2}})\s*(?:-|–|—|to)\s*(\d{{1,2}})\s+({_MONTHS_TEXT})\s+(\d{{4}})\b",
    re.IGNORECASE
)
_SINGLE = re.compile(rf"\b(\d{{1,2}})\s+({_MONTHS_TEXT})\s+(\d{{4}})\b", re.IGNORECASE)
_ISO_RANGE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\s*(?:to|/|–|—)\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)


@dataclass(frozen=True)
class IncidentWindow:
    start_utc: str
    end_utc: str
    zone_name: str
    interpretation: str

    def to_dict(self) -> dict[str, str]:
        return dict(start_utc=self.start_utc, end_utc=self.end_utc,
                    zone_name=self.zone_name, interpretation=self.interpretation)

    def contains(self, timestamp: str) -> bool:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z","+00:00"))
            if dt.tzinfo is None or dt.utcoffset() is None:
                return False
            return self.start_utc <= dt.astimezone(timezone.utc).isoformat() < self.end_utc
        except (ValueError, TypeError, OverflowError):
            return False

    def minimum_hours_back(self, *, now: datetime) -> int:
        if now.tzinfo is None:
            raise ValueError("now must be timezone aware")
        start = datetime.fromisoformat(self.start_utc)
        return max(1, int(math.ceil((now.astimezone(timezone.utc)-start).total_seconds()/3600)) + 1)


def explicit_incident_window(question: str, *, zone_name: str) -> IncidentWindow | None:
    if not isinstance(question, str):
        return None
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        return None
    match = _RANGE.search(question)
    single = _SINGLE.search(question) if not match else None
    iso = _ISO_RANGE.search(question) if not match and not single else None
    try:
        if match:
            first, last = date(int(match[4]), _MONTHS[match[3].lower()], int(match[1])), date(
                int(match[4]), _MONTHS[match[3].lower()], int(match[2]))
        elif iso:
            first, last = date.fromisoformat(iso[1]), date.fromisoformat(iso[2])
        elif single:
            first = last = date(int(single[3]), _MONTHS[single[2].lower()], int(single[1]))
        else:
            return None
        if last < first or (last-first).days > 7:
            return None
    except ValueError:
        return None
    overnight = bool(re.search(r"\bovernight\b|\bnight\b",question,re.I))
    if overnight and last > first:
        first_local=datetime.combine(first,time(18),tzinfo=zone)
        last_local=datetime.combine(last,time(12),tzinfo=zone)
        interpretation="overnight range: first day 18:00 to final day 12:00 local"
    else:
        first_local=datetime.combine(first,time.min,tzinfo=zone)
        last_local=datetime.combine(last+timedelta(days=1),time.min,tzinfo=zone)
        interpretation="inclusive calendar date range: local midnights"
    return IncidentWindow(
        start_utc=first_local.astimezone(timezone.utc).isoformat(),
        end_utc=last_local.astimezone(timezone.utc).isoformat(),
        zone_name=zone_name, interpretation=interpretation
    )


__all__=["IncidentWindow", "explicit_incident_window"]
