"""Compact in-request native evidence ledger for V2 model-led source review.

Navigation ONLY: every fact comes from an ORIGINAL successful MCP receipt;
no tool selection, new calls, inference of continuous coverage, cause or absence.
Original receipts remain untouched and available to the model and Technical JSON.
"""
from __future__ import annotations

from collections import Counter
from native_past_log_receipt import original_past_log_source
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
    "attribute", "format", "mode", "device_id", "metric", "range",
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



def historical_source_frontier(
    receipts: list[dict], *, monitor_offered: bool = False,
) -> dict:
    """Source-TYPE coverage, not a verdict on historical availability.

    A successful monitor status response is a latest-value inventory, NEVER
    a saved-bin history query. Count an archive read only if its original
    successful response contains history data. Original device IDs are
    included only when they match focused native history requests; no labels,
    passwords, full inventories, or raw monitor payloads are reproduced.
    The model remains responsible for deciding whether to read further.
    """
    targets: set[str] = set()
    attributes: set[str] = set()
    native_event_reads = 0
    native_event_rows = 0
    native_failed_event_reads = 0
    monitor_status_reads = 0
    monitor_history_reads = 0
    monitor_history_attempts = 0
    selected_targets: set[str] = set()
    history_targets: set[str] = set()
    attempted_history_targets: set[str] = set()
    for row in receipts:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        args = row.get("arguments")
        args = args if isinstance(args, dict) else {}
        if name == "hub_list_device_events":
            if row.get("success") is not True:
                native_failed_event_reads += 1
                continue
            outer, native = _response(row)
            if not isinstance(native, dict) or not isinstance(native.get("events"), list):
                continue
            native_event_reads += 1
            native_event_rows += len(native["events"])
            device_id = str(args.get("deviceId") or "")
            if _SAFE_ID.fullmatch(device_id):
                targets.add(device_id)
            attribute = args.get("attribute")
            if isinstance(attribute, str) and _SAFE_FIELD.fullmatch(attribute):
                attributes.add(attribute)
            continue
        if name != "homebrain_read_device_monitor":
            continue
        mode = args.get("mode")
        if mode in ("history", "compare"):
            monitor_history_attempts += 1
            requested_ids = ([args.get("device_id")] if mode == "history"
                             else args.get("device_ids"))
            if isinstance(requested_ids, list):
                for ident in requested_ids[:5]:
                    ident = str(ident or "")
                    if ident in targets:
                        attempted_history_targets.add(ident)
        if row.get("success") is not True:
            continue
        outer, native = _response(row)
        if not isinstance(native, dict):
            continue
        payload = native.get("local_device_monitor")
        if not isinstance(payload, dict) or payload.get("read_only") is not True:
            continue
        if mode == "status" and isinstance(payload.get("selected_devices"), list):
            monitor_status_reads += 1
            for selected in payload["selected_devices"][:500]:
                if not isinstance(selected, dict):
                    continue
                ident = str(selected.get("id") or "")
                if ident in targets:
                    selected_targets.add(ident)
        elif mode == "history" and isinstance(payload.get("summary"), dict) and isinstance(payload.get("samples"), list):
            monitor_history_reads += 1
            ident = str(payload.get("device_id") or "")
            if ident in targets and ident == str(args.get("device_id") or ""):
                history_targets.add(ident)
        elif mode == "compare" and isinstance(payload.get("devices"), list):
            monitor_history_reads += 1
            for device in payload["devices"][:5]:
                if not isinstance(device, dict) or not isinstance(device.get("summary"), dict):
                    continue
                ident = str(device.get("device_id") or "")
                if ident in targets:
                    history_targets.add(ident)

    # Match monitor history requests even if those reads preceded the native
    # target lookup. Different-device history cannot close this target's gap.
    if targets and monitor_history_attempts and not attempted_history_targets:
        for row in receipts:
            if (not isinstance(row, dict)
                    or row.get("name") != "homebrain_read_device_monitor"
                    or not isinstance(row.get("arguments"), dict)):
                continue
            args = row["arguments"]
            requested_ids = ([args.get("device_id")]
                             if args.get("mode") == "history"
                             else args.get("device_ids")
                             if args.get("mode") == "compare" else None)
            if isinstance(requested_ids, list):
                for ident in requested_ids[:5]:
                    ident = str(ident or "")
                    if ident in targets:
                        attempted_history_targets.add(ident)

    # A status-first inventory can precede the targeted event query; inspect
    # its original selected IDs again so receipt order cannot erase a match.
    if targets and monitor_status_reads and not selected_targets:
        for row in receipts:
            if (not isinstance(row, dict)
                    or row.get("name") != "homebrain_read_device_monitor"
                    or row.get("success") is not True
                    or not isinstance(row.get("arguments"), dict)
                    or row["arguments"].get("mode") != "status"):
                continue
            _, native = _response(row)
            payload = native.get("local_device_monitor") if isinstance(native, dict) else None
            if not isinstance(payload, dict) or payload.get("read_only") is not True:
                continue
            selected = payload.get("selected_devices")
            if isinstance(selected, list):
                for item in selected[:500]:
                    if isinstance(item, dict):
                        ident = str(item.get("id") or "")
                        if ident in targets:
                            selected_targets.add(ident)

    # No source here attests a complete requested window, even when the query
    # returned fewer rows than its limit; an archive history is not continuous
    # physical measurement either.
    status_only_gap = (
        monitor_offered and native_event_reads > 0
        and native_event_rows == 0 and monitor_status_reads > 0
        and bool(selected_targets - history_targets)
        and bool(selected_targets - attempted_history_targets)
    )
    return {
        "source_type_scope": "current_request_successful_original_receipts_only",
        "native_event_history_reads": native_event_reads,
        "native_returned_event_rows": native_event_rows,
        "native_failed_event_reads": native_failed_event_reads,
        "native_filtered_attributes": sorted(attributes)[:_MAX_ATTRIBUTES],
        "target_device_ids_from_native_event_reads": sorted(targets)[:5],
        "monitor_offered_not_proven_connected": bool(monitor_offered),
        "monitor_latest_value_status_reads": monitor_status_reads,
        "monitor_saved_history_attempts": monitor_history_attempts,
        "monitor_saved_history_successful_reads": monitor_history_reads,
        "native_history_targets_with_monitor_history_attempts": sorted(attempted_history_targets)[:5],
        "native_history_targets_selected_in_monitor_status": sorted(selected_targets)[:5],
        "native_history_targets_with_monitor_history_receipts": sorted(history_targets)[:5],
        "status_is_not_saved_historical_measurements": True,
        "no_monitor_history_read_does_not_prove_archive_empty": True,
        "zero_native_event_rows_do_not_prove_no_activity": True,
        "full_requested_window_or_continuous_state_verified": False,
        "status_only_historical_gap_for_model_review": status_only_gap,
    }


HISTORICAL_SOURCE_TYPE_GAP_PROMPT = """Historical measurement source-type checkpoint (read-only).
A successful monitor mode=status only shows latest or cached values and
monitoring configuration. It does NOT query saved historical bins for the
requested period. An earlier monitor power-event timestamp is NOT proof the
event was non-zero. A native filtered query returning zero rows is NOT proof
the separate monitor archive has no saved bins or that a device stayed idle.
The read-only monitor history tool is offered, and the returned status
identifies a target already checked in native history. Independently decide
whether a proportionate, schema-valid saved-history read could materially
answer the original requested quantity/window. You may select it through
the existing live offered tool, but there is NO mandatory call, automatic
source choice, target/metric routing, or added authorisation. If you decide
not to read history, state that its coverage and latest non-zero value
remain UNVERIFIED, not absent. A current switch/zero-watt snapshot is
not a six-hour continuous state. No writes; keep the answer concise."""



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
                elif name == "hub_get_logs":
                    parsed = original_past_log_source(row)
                    if parsed is not None:
                        _, past, variant = parsed
                        recorded["returned_log_rows"] = len(past["entries"])
                        recorded["source_envelope_variant"] = variant
                        recorded["source_total_scope_unverified"] = True
                        recorded["log_count_is_execution_proof"] = False
                elif isinstance(native.get("entries"), list):
                    recorded["native_document_parsed"] = True
                else:
                    recorded["native_document_parsed"] = True
        items.append(recorded)
    return json.dumps({
        "type": "original_current_request_source_navigation_only",
        "source_map_is_not_an_independent_receipt": True,
        "receipt_rows": items,
        "receipts_omitted_due_to_cap": max(0, len(receipts) - _MAX_RECEIPTS),
        "monitor_configured_and_offered_not_proven_connected": bool(monitor_offered),
        "historical_measurement_source_type_frontier": historical_source_frontier(
            receipts, monitor_offered=monitor_offered,
        ),
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

    Only historical measurement review with successful, uncapped, explicitly
    attribute-filtered original event rows and zero failed receipts qualifies. The prior source review
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
        args = row.get("arguments")
        args = args if isinstance(args, dict) else {}
        # An unfiltered or mismatched event query can contain interleaved
        # attributes, recorded commands and cross-field chronology. The
        # existing full original-row final audit is important for those.
        if (not isinstance(args.get("attribute"), str)
                or native.get("attributeFilter") != args["attribute"]):
            return False
        events = native.get("events")
        if not isinstance(events, list) or any(
            isinstance(event, dict) and (
                event.get("type") == "command"
                or str(event.get("name") or "").startswith("command-")
            ) for event in events
        ):
            return False
        scope = _event_scope(outer, native, args)
        if not scope or not scope["returned_event_rows"] or scope["returned_limit_reached"]:
            return False
        event_reads += 1
    return event_reads > 0
