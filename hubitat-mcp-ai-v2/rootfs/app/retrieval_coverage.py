"""Conservative source-coverage metadata for raw file chunks and event rows.

This module never fetches, infers a physical state, rewrites a source result,
or declares a history store complete based on a filtered response. It describes
only exactly returned character ranges and returned, parseable event rows.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any


def _body(result: Any) -> dict | None:
    if not isinstance(result, dict) or result.get("isError"):
        return None
    # Hubitat MCP wraps its actual tool reply as JSON text in a content item.
    for item in result.get("content", []):
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            try:
                obj = json.loads(item["text"])
                if isinstance(obj, dict):
                    return obj
            except (ValueError, TypeError):
                continue
    return result


def file_chunk_scope(result: Any) -> dict | None:
    """Observe one native file-read chunk without inspecting its private text."""
    data = _body(result)
    if not isinstance(data, dict) or not isinstance(data.get("content"), str):
        return None
    name = data.get("fileName")
    size, offset, claimed = (data.get(k) for k in ("totalLength", "offset", "chunkLength"))
    if (not isinstance(name, str) or not name or len(name) > 240
            or type(size) is not int or type(offset) is not int
            or type(claimed) is not int
            or size < 0 or offset < 0 or claimed < 0 or offset > size):
        return None
    actual_length = min(claimed, len(data["content"]), size - offset)
    if actual_length < 0:
        return None
    return {
        "source_scope": "returned file character chunk only",
        "file_name": name,
        "total_file_characters_reported": size,
        "returned_offset": offset,
        "returned_end_exclusive": offset + actual_length,
        "returned_characters_verified": actual_length,
        "upstream_has_more": data.get("hasMore") is True,
        "file_fully_read_by_this_chunk": offset == 0 and actual_length == size,
        "can_infer_unread_file_contents_absent": False,
        "note": (
            "A matching filename and partial file contents do not establish "
            "that a target device/attribute is present or absent. Missing "
            "character offsets remain unread. For historical measurements, "
            "prefer an available structured source-specific history query "
            "and verify its returned time window and sample provenance."
        ),
    }


class FileReadCoverage:
    """Track only in-request successful file ranges, with safe bounded metadata."""
    def __init__(self):
        self._read: dict[str, dict] = {}

    def add(self, scope: dict) -> dict:
        name = scope["file_name"]
        size = scope["total_file_characters_reported"]
        state = self._read.get(name)
        if state is None or state["total"] != size:
            state = {"total": size, "ranges": [], "reads": 0}
            self._read[name] = state
        state["reads"] += 1
        start, end = scope["returned_offset"], scope["returned_end_exclusive"]
        if end > start:
            state["ranges"].append((start, end))
        merged = []
        for a, b in sorted(state["ranges"]):
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        state["ranges"] = merged
        covered = sum(b - a for a, b in merged)
        missing = []
        previous = 0
        for a, b in merged:
            if a > previous:
                missing.append((previous, a))
            previous = b
        if previous < size:
            missing.append((previous, size))
        return {
            "source_scope": "character coverage of this file in this Ask request",
            "file_name": name,
            "file_size_characters": size,
            "retrieved_characters_unique": covered,
            "retrieved_percent": round(100 * covered / size, 2) if size else 100,
            "read_requests": state["reads"],
            "unread_range_count": len(missing),
            "first_unread_ranges": [
                {"start": a, "end_exclusive": b} for a, b in missing[:6]
            ],
            "file_completely_retrieved": len(missing) == 0,
            "can_claim_matching_records_absent_in_unread_ranges": False,
            "note": (
                "Only these character ranges have been read in this request. "
                "Presence/absence claims about a file require covering relevant "
                "records, or an indexed read-only query that establishes them."
            ),
        }

    def snapshot(self) -> list[dict]:
        result = []
        # Private file names remain in the request's private receipt only.
        for name in sorted(self._read):
            s = self._read[name]
            merged = s["ranges"]
            covered = sum(b-a for a,b in merged)
            result.append({
                "file_name": name, "total_characters": s["total"],
                "retrieved_characters_unique": covered,
                "retrieved_percent": round(100 * covered/s["total"], 2) if s["total"] else 100,
                "file_completely_retrieved": (
                    s["total"] == 0 or
                    len(merged) == 1 and merged[0] == (0, s["total"])
                ),
                "read_requests": s["reads"],
            })
        return result


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except (ValueError, OverflowError):
        return None


def event_attribute_scope(result: Any) -> dict | None:
    """Index only returned event attribute names and time bounds, not inferred states."""
    data = _body(result)
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        return None
    rows = data["events"]
    if len(rows) > 10000:
        return None
    groups: dict[str, dict] = {}
    invalid = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not isinstance(name, str) or len(name) > 90:
            name = "(unknown)"
        at = _utc(row.get("date"))
        if at is None:
            invalid += 1
        group = groups.setdefault(name, {"returned_count": 0, "times": []})
        group["returned_count"] += 1
        if at is not None:
            group["times"].append(at)
    by_attribute = []
    for name in sorted(groups):
        row = groups[name]
        times = row["times"]
        by_attribute.append({
            "event_name": name, "returned_count": row["returned_count"],
            "first_returned_event_utc": min(times).isoformat() if times else None,
            "last_returned_event_utc": max(times).isoformat() if times else None,
        })
    return {
        "source_scope": "returned event rows grouped by their exact event name",
        "events_returned": len(rows),
        "event_names": by_attribute[:80],
        "event_name_categories_truncated": len(by_attribute) > 80,
        "rows_without_parseable_offset": invalid,
        "requested_attribute_filter": data.get("attributeFilter"),
        "can_infer_continuous_history_coverage": False,
        "can_infer_absent_events_not_in_result": False,
        "note": (
            "Times belong ONLY to their named returned attribute/event type. "
            "Never reuse amperage/energy timestamps as power readings. "
            "Event gaps between different attributes are not outages. "
            "Oldest/latest here describe returned rows, not retained history."
        ),
    }
