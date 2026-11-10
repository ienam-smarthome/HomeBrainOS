"""Experimental, general source-shape ledger for native MCP read results.

This module does not decide what to read or say. It only describes the
specific collection returned to the model: actual row counts, reported
upstream totals/filters and field coverage in the returned subset.

Opt-in through SourceLedgerExperimentalAgent; NOT enabled by the production
Agent. Original native MCP payload remains intact and authoritative.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

_SECRET_FIELD = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|credential)",
    re.IGNORECASE,
)
_MAX_FIELDS = 48


def _integer(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _payload(result: Any) -> dict | None:
    if not isinstance(result, dict) or result.get("isError") is True:
        return None
    content = result.get("content")
    if isinstance(content, list):
        parsed = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "text":
                continue
            try:
                body = json.loads(part.get("text"))
            except (ValueError, TypeError):
                continue
            if isinstance(body, dict):
                parsed.append(body)
        # Do not consolidate two unrelated source responses into one
        # invented inventory or log window.
        return parsed[0] if len(parsed) == 1 else None
    return result if isinstance(result, dict) else None


def _leaf_args(arguments: Any) -> dict:
    if not isinstance(arguments, dict):
        return {}
    nested = arguments.get("args")
    return nested if isinstance(nested, dict) else arguments


def _observed_current_state_coverage(rows: list) -> dict:
    counts: Counter[str] = Counter()
    total = len(rows)
    for row in rows:
        states = row.get("currentStates") if isinstance(row, dict) else None
        if not isinstance(states, dict):
            continue
        for field in states:
            if (isinstance(field, str) and field and len(field) <= 64
                    and not _SECRET_FIELD.search(field)):
                counts[field] += 1
    # Limit context size: prefer frequently present fields, keep the
    # remaining-field count explicit rather than claiming full coverage.
    selected = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    output = {
        key: {
            "rows_with_field_returned": count,
            "rows_without_field_returned": total - count,
        }
        for key, count in selected[:_MAX_FIELDS]
    }
    return {
        "field_coverage_in_returned_rows": output,
        "additional_distinct_fields_omitted": max(0, len(counts) - len(output)),
        "note": (
            "Missing from currentStates means the field was not returned "
            "in that record, not that the device lacks the capability, has "
            "never reported it, or that its history is complete."
        ),
    }


def source_ledger(result: Any, arguments: Any = None) -> dict | None:
    """Return neutral collection evidence, never inferred completeness."""
    body = _payload(result)
    if body is None:
        return None
    args = _leaf_args(arguments)
    for key in ("devices", "apps", "entries"):
        rows = body.get(key)
        if not isinstance(rows, list):
            continue
        notes = {
            "kind": key,
            "returned_rows": len(rows),
            "reported_matching_rows": (
                _integer(body.get("matched")) if key == "entries"
                else _integer(body.get("count"))
            ),
            "reported_total_rows": (
                _integer(body.get("total")) if key == "entries"
                else _integer(body.get("totalOnHub"))
                if key == "apps" else _integer(body.get("unfilteredTotal"))
            ),
            "requested_filters": {
                field: args[field]
                for field in ("format", "mode", "level", "since", "limit", "offset")
                if field in args and (type(args[field]) is str
                                      or type(args[field]) is int)
                and len(str(args[field])) <= 64
            },
            "returned_rows_less_than_reported_matches": (
                _integer(body.get("matched")) > len(rows)
                if key == "entries" and _integer(body.get("matched")) is not None
                else None
            ),
            "entire_source_or_requested_window_verified": False,
            "note": (
                "Counts refer only to this returned source collection and its "
                "server-reported totals; a filter, limit, partial page, missing "
                "attribute or successful request does not establish coverage of "
                "unreturned source records or prove a causal explanation."
            ),
        }
        if key == "devices":
            notes.update(_observed_current_state_coverage(rows))
        return notes
    return None


def with_source_ledger(result: dict, arguments: Any = None) -> dict:
    """Copy and annotate; preserve the native body and earlier scope notes."""
    metadata = source_ledger(result, arguments)
    if metadata is None:
        return result
    return {**result, "client_collection_source_ledger": metadata}
