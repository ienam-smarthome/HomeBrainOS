"""Compact in-request native evidence ledger for V2 model-led source review.

Navigation ONLY: every fact comes from an ORIGINAL successful MCP receipt;
no tool selection, new calls, inference of continuous coverage, cause or absence.
Original receipts remain untouched and available to the model and Technical JSON.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import re

_SAFE_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_SAFE_NUMBER = re.compile(r"^-?\d{1,10}(?:\.\d{1,6})?$")
_COMMON_STATES = frozenset({
    "on", "off", "idle", "heating", "cooling", "active", "inactive",
    "open", "closed", "present", "not present", "online", "offline",
    "heat", "auto", "dry", "wet", "locked", "unlocked", "running",
    "stopped", "standby", "unknown",
})
_SAFE_ARGS = frozenset({
    "deviceId", "appId", "hoursBack", "limit", "since", "until",
    "attribute", "format", "mode",
})
_MAX_RECEIPTS = 14
_MAX_EVENTS = 250
_MAX_ATTRIBUTES = 8
_MAX_VALUES = 5


def _utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def _safe_arg(value: object) -> bool:
    return (
        type(value) in (int, float) and 0 <= value <= 1000000000
        or isinstance(value, str) and bool(_SAFE_ID.fullmatch(value))
    )


def _safe_value(value: object) -> str | None:
    if type(value) in (int, float) and abs(value) < 1e10:
        return str(value)
    if not isinstance(value, str) or len(value) > 32:
        return None
    lowered = value.strip().lower()
    return value if (lowered in _COMMON_STATES
                     or _SAFE_NUMBER.fullmatch(value)) else None


def _response(receipt: dict) -> tuple[dict | None, dict | None]:
    try:
        outer = json.loads(receipt.get("response", ""))
    except (TypeError, ValueError):
        return None, None
    if not isinstance(outer, dict):
        return None, None
    if isinstance(outer.get("content"), list):
        parts = [
            p for p in outer["content"]
            if isinstance(p, dict) and p.get("type") == "text"
            and isinstance(p.get("text"), str)
        ]
        if len(parts) != 1:
            return outer, None
        try:
            native = json.loads(parts[0]["text"])
        except (TypeError, ValueError):
            return outer, None
        return outer, native if isinstance(native, dict) else None
    return outer, outer


def _event_scope(outer: dict, native: dict, args: dict) -> dict:
    events = native.get("events")
    if not isinstance(events, list):
        return {}
    counts = Counter()
    values: dict[str, Counter] = {}
    stamps = []
    for event in events[:_MAX_EVENTS]:
        if not isinstance(event, dict):
            continue
        name = event.get("name")
        if not isinstance(name, str) or not _SAFE_FIELD.fullmatch(name):
            continue
        counts[name] += 1
        safe = _safe_value(event.get("value"))
        if safe is not None:
            values.setdefault(name, Counter())[safe] += 1
        when = _utc(event.get("date"))
        if when is not None:
            stamps.append(when)
    count = len(events)
    explicit_limit = args.get("limit")
    limit = explicit_limit if type(explicit_limit) is int and explicit_limit > 0 else None
    meta = outer.get("client_claim_evidence_headline")
    meta = meta if isinstance(meta, dict) else {}
    capped = meta.get("row_limit_reached")
    if type(capped) is not bool:
        capped = bool(limit is not None and count >= limit)
    groups = []
    for name, n in counts.most_common(_MAX_ATTRIBUTES):
        samples = values.get(name, Counter())
        groups.append({
            "attribute": name,
            "returned_rows": n,
            "short_observed_values": [
                {"value": value, "returned_rows": amount}
                for value, amount in samples.most_common(_MAX_VALUES)
            ],
            "rows_with_values_not_indexed": n - sum(
                amount for _, amount in samples.most_common(_MAX_VALUES)
            ),
        })
    return {
        "returned_event_rows": count,
        "events_scanned_for_ledger": min(count, _MAX_EVENTS),
        "unscanned_rows": max(0, count - _MAX_EVENTS),
        "returned_limit_reached": capped,
        "oldest_indexed_event": min(stamps).isoformat() if stamps else None,
        "newest_indexed_event": max(stamps).isoformat() if stamps else None,
        "native_reported_query_start": (
            native.get("sinceTimestamp")
            if _utc(native.get("sinceTimestamp")) is not None else None
        ),
        "returned_attributes": groups,
        "attributes_not_indexed": max(0, len(counts) - _MAX_ATTRIBUTES),
        "returned_rows_are_discrete_not_continuous": True,
        "no_unseen_commands_or_earlier_events_proven_absent": True,
        "full_requested_window_proven_covered": False,
    }


def source_review_ledger(receipts: list[dict], *, monitor_offered: bool = False) -> str:
    """Small private model-facing source-scope map. Never an independent source."""
    items = []
    for index, row in enumerate(receipts[:_MAX_RECEIPTS], 1):
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not isinstance(name, str) or len(name) > 110:
            continue
        args = row.get("arguments")
        args = args if isinstance(args, dict) else {}
        recorded = {
            "receipt": index,
            "tool": name,
            "request": {
                key: value for key, value in args.items()
                if key in _SAFE_ARGS and _safe_arg(value)
            },
            "original_success": row.get("success") is True,
        }
        if row.get("success") is not True:
            recorded["failed_read_is_not_empty_history"] = True
            recorded["operation_executed"] = row.get("operation_executed") is not False
        else:
            outer, native = _response(row)
            if isinstance(outer, dict) and isinstance(native, dict):
                scope = _event_scope(outer, native, args)
                if scope:
                    recorded["original_event_scope"] = scope
                elif isinstance(native.get("devices"), list):
                    devices = native["devices"]
                    recorded["returned_inventory_rows"] = len(devices)
                    recorded["inventory_is_historical_proof"] = False
                elif isinstance(native.get("entries"), list):
                    recorded["returned_log_rows"] = len(native["entries"])
                    recorded["log_count_is_execution_proof"] = False
                else:
                    recorded["native_document_parsed"] = True
        items.append(recorded)
    return json.dumps({
        "type": "original_current_request_source_navigation_only",
        "source_map_is_not_an_independent_receipt": True,
        "receipt_rows": items,
        "receipts_omitted_due_to_cap": max(0, len(receipts) - _MAX_RECEIPTS),
        "monitor_configured_and_offered_not_proven_connected": bool(monitor_offered),
        "review_contract": (
            "Compare requested time bounds with returned oldest/newest per exact "
            "attribute. Repeated identical state values do not prove a transition "
            "or continuous state, even if isStateChange is true. A source reporter "
            "and triggered listeners are not command initiators. A failed read "
            "is not an empty result. If another proportionate read-only source "
            "can distinguish unresolved facts, the MODEL chooses it; otherwise "
            "finish with bounded facts and precise unknowns. Do not claim other "
            "tools lack records without inspecting them."
        ),
    }, separators=(",", ":"), ensure_ascii=False)


def may_skip_unchanged_final_audit(
    receipts: list[dict], *, review_kind: str | None,
    receipt_count_at_review: int | None,
) -> bool:
    """Avoid another *model-only* polishing pass for simple unchanged evidence.

    Only historical measurement review with successful, uncapped original
    event rows and zero failed receipts qualifies. The prior source review
    already saw the originals and could elect a new read. This does NOT
    establish source sufficiency or answer correctness.
    """
    if (review_kind != "historical_measurement"
            or receipt_count_at_review is None
            or len(receipts) != receipt_count_at_review
            or not receipts):
        return False
    event_reads = 0
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            return False
        if row.get("name") != "hub_list_device_events":
            continue
        outer, native = _response(row)
        if not isinstance(outer, dict) or not isinstance(native, dict):
            return False
        scope = _event_scope(outer, native, row.get("arguments") or {})
        if not scope or not scope["returned_event_rows"] or scope["returned_limit_reached"]:
            return False
        event_reads += 1
    return event_reads > 0
