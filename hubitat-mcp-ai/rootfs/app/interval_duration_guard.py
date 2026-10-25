"""Repair event-interval table durations using typed source seconds.

Applies to generated Markdown rows showing ON/OFF start and end. Unlike a
provenance decision, this is deterministic clock arithmetic; no claim about
uninterrupted device operation is inferred from historical event pages.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any


def _intervals(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in receipts:
        if not isinstance(row, dict):
            continue
        if row.get("tool") != "homebrain_device_history" or row.get("success") is not True:
            continue
        details = row.get("details")
        temporal = details.get("temporalAnalysis") if isinstance(details, dict) else None
        intervals = temporal.get("observedIntervals") if isinstance(temporal, dict) else None
        if isinstance(intervals, list) and intervals:
            return [item for item in intervals if isinstance(item, dict)]
    return []


def _reported_seconds(value: str) -> int | None:
    text = str(value or "").casefold()
    hours = re.search(r"(?<!\w)(\d+)\s*(?:h|hrs?|hours?)\b", text)
    minutes = re.search(r"(?<!\w)(\d+)\s*(?:m|mins?|minutes?)\b", text)
    seconds = re.search(r"(?<!\w)(\d+)\s*(?:s|secs?|seconds?)\b", text)
    if not any((hours, minutes, seconds)):
        return None
    return (
        (int(hours.group(1)) * 3600 if hours else 0)
        + (int(minutes.group(1)) * 60 if minutes else 0)
        + (int(seconds.group(1)) if seconds else 0)
    )


def _correct_duration(seconds: int) -> str:
    h, remainder = divmod(max(0, seconds), 3600)
    m, s = divmod(remainder, 60)
    return " ".join(
        part for part in (
            f"{h}h" if h else "",
            f"{m}m" if m else "",
            f"{s}s" if s or not (h or m) else "",
        ) if part
    )


def guard_interval_table_durations(
    message: str, receipts: list[dict[str, Any]]
) -> tuple[str, bool]:
    intervals = _intervals(receipts)
    source = str(message or "")
    if not intervals or "| " not in source:
        return source, False
    changed = False
    lines = []
    for line in source.splitlines(keepends=True):
        cells = line.strip().strip("|").split("|") if line.strip().startswith("|") else []
        if len(cells) < 3 or not re.search(r"\bon\b", cells[0], re.I) or not re.search(r"\boff\b", cells[1], re.I):
            lines.append(line)
            continue
        claimed = _reported_seconds(cells[2])
        if claimed is None:
            lines.append(line)
            continue
        candidates = []
        for item in intervals:
            try:
                start = datetime.fromisoformat(str(item["start"]))
                end = datetime.fromisoformat(str(item["end"]))
                seconds = int(item["durationSeconds"])
            except (ValueError, KeyError, TypeError):
                continue
            start_time, end_time = start.strftime("%H:%M"), end.strftime("%H:%M")
            if start_time not in cells[0] or end_time not in cells[1]:
                continue
            candidates.append(seconds)
        if len(candidates) != 1:
            lines.append(line)
            continue
        # "4h 19m" is a valid rounding of 4h 18m 30s; "3h 18m" is not.
        if abs(candidates[0] - claimed) <= 90:
            lines.append(line)
            continue
        cells[2] = " " + _correct_duration(candidates[0]) + " "
        replacement = "|" + "|".join(cells) + "|"
        if line.endswith("\n"):
            replacement += "\n"
        lines.append(replacement)
        changed = True
    return "".join(lines), changed


__all__ = ["guard_interval_table_durations"]
