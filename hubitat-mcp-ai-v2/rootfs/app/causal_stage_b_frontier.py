"""V2 Stage B: source-attested, model-selectable causal read frontier.

Offline projection over ORIGINAL successful current-request MCP receipts and
the currently OFFERED native read-only tool schemas.  Reuses V3 Stage 3A's
source-scope, deduplication and advisory-only principles.  No native tool
dispatch, deterministic cause, log-retention inference, or new permission.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from causal_read_opportunity import _field_schema, _source_clock, _id
from investigation_review import is_read_only_review_tool
from investigation_source_ledger import _response, _SAFE_ID
from native_device_event_receipt import original_device_event_history

_MAX_RECEIPTS = 40
_MAX_EVENTS = 250
_MAX_INVENTORY = 700
_MAX_SCOPE_CHOICES = 10
_MAX_LISTENERS = 8
_MAX_PROPOSALS = 8
_SAFE_LABEL = re.compile(r"[A-Za-z0-9 _().,:+/'&-]{1,66}\Z")
_STATE_FIELDS = frozenset({
    "switch", "thermostatOperatingState", "operatingState", "fanOperatingState",
    "contact", "lock", "valve", "motion", "presence", "water", "windowShade",
})
_CATEGORICAL = frozenset({
    "on", "off", "heating", "idle", "cooling", "open", "closed",
    "active", "inactive", "locked", "unlocked", "running", "stopped",
    "wet", "dry", "present", "not present", "alarm", "clear",
})


def _safe_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _SAFE_LABEL.fullmatch(value) else None


def _tool_specs(catalog: list[dict]) -> dict[str, dict]:
    offered: dict[str, dict] = {}
    for item in catalog[:100]:
        fun = item.get("function") if isinstance(item, dict) else None
        if not isinstance(fun, dict):
            continue
        name = fun.get("name")
        if (name not in ("hub_list_device_events", "hub_get_logs")
                or not is_read_only_review_tool(name)
                or name in offered):
            continue
        fields, gateway = _field_schema(fun)
        if gateway or not fields:
            continue
        offered[name] = {
            "fields": {f["name"]: f for f in fields},
            "name": name,
        }
    return offered


def _typed_id(value: str, field: dict) -> str | int | None:
    if field.get("type") == "integer":
        if value.isdecimal():
            return int(value)
        return None
    if field.get("type") in ("string", "unspecified"):
        return value
    return None


def _args(spec: dict, ident: str, begin: datetime, end: datetime,
          *, logs: bool) -> dict | None:
    fields = spec["fields"]
    key = "appId" if logs else "deviceId"
    if key not in fields:
        return None
    identity = _typed_id(ident, fields[key])
    if identity is None:
        return None
    arguments = {key: identity}
    if logs:
        mode = fields.get("mode")
        if not mode or mode.get("type") not in ("string", "unspecified"):
            return None
        if (mode.get("advertised_enum") is not None
                and "past" not in mode["advertised_enum"]):
            return None
        arguments["mode"] = "past"
    for key2, value in (("since", begin.isoformat()), ("until", end.isoformat())):
        if fields.get(key2, {}).get("type") in ("string", "unspecified"):
            arguments[key2] = value
    if fields.get("limit", {}).get("type") == "integer":
        arguments["limit"] = 30 if not logs else 60
    if (not logs and "since" not in arguments
            and fields.get("hoursBack", {}).get("type") in ("integer", "number")):
        arguments["hoursBack"] = 24
    # Never silently omit required arguments not derivable from original
    # identity, mode, source clock or the actual advertised field schema.
    if any(row["required"] and key2 not in arguments
           for key2, row in fields.items()):
        return None
    return arguments


def _source_rows(receipts: list[dict]) -> tuple[list[dict], list[dict], set[str]]:
    reports: list[dict] = []
    commands: list[dict] = []
    unfiltered_targets: set[str] = set()
    for receipt in receipts[:_MAX_RECEIPTS]:
        validated = original_device_event_history(receipt)
        if validated is None:
            continue
        ident, label, events = validated
        args = receipt.get("arguments")
        attr = args.get("attribute") if isinstance(args, dict) else None
        if not attr:
            unfiltered_targets.add(ident)
        for event in events[:_MAX_EVENTS]:
            if not isinstance(event, dict):
                continue
            inline = event.get("deviceId")
            if inline is not None and str(inline) != ident:
                continue
            date = event.get("date")
            dt = _source_clock(date)
            if dt is None:
                continue
            name = event.get("name")
            if not isinstance(name, str):
                continue
            if name.startswith("command-"):
                origin = event.get("producedBy")
                appid = _id(origin.get("appId")) if isinstance(origin, dict) else None
                if appid:
                    commands.append({"time": dt, "date": date, "device": ident,
                                     "issuer": appid, "command": name})
                continue
            if name not in _STATE_FIELDS or event.get("type") not in (None, "event"):
                continue
            value = event.get("value")
            if not isinstance(value, str) or value.casefold() not in _CATEGORICAL:
                continue
            listeners: list[dict] = []
            notified = event.get("triggered")
            if isinstance(notified, list):
                for listener in notified[:_MAX_LISTENERS]:
                    if not isinstance(listener, dict):
                        continue
                    appid = _id(listener.get("appId"))
                    if appid and appid not in {x["id"] for x in listeners}:
                        listeners.append({"id": appid,
                                          "label": _safe_label(listener.get("name")),
                                          "only_notified_not_an_issuer": True})
            reports.append({"time": dt, "date": date, "device": ident,
                            "device_label": _safe_label(label),
                            "attribute": name, "value": value.casefold(),
                            "listeners": listeners})
    return reports, commands, unfiltered_targets


def _log_coverage(receipts: list[dict], anchor: datetime | None) -> dict:
    """An empty native query is scope-limited, never absence/retention proof."""
    attempted: list[dict] = []
    explicit_boundaries: list[datetime] = []
    for receipt in receipts[:_MAX_RECEIPTS]:
        if (not isinstance(receipt, dict) or receipt.get("name") != "hub_get_logs"
                or receipt.get("success") is not True):
            continue
        args = receipt.get("arguments")
        if not isinstance(args, dict) or args.get("mode") != "past":
            continue
        _, native = _response(receipt)
        if not isinstance(native, dict) or native.get("mode") != "past":
            continue
        date = native.get("oldestRetainedTimestamp")
        boundary = _source_clock(date)
        if boundary is not None:
            explicit_boundaries.append(boundary)
        if (not isinstance(native.get("entries"), list)
                or len(native["entries"]) != 0
                or type(native.get("matched")) is not int
                or native["matched"] != 0):
            continue
        appid = _id(args.get("appId"))
        attempted.append({
            "app_id": appid,
            "unscoped": appid is None,
            "since": args.get("since") if _source_clock(args.get("since")) else None,
            "until": args.get("until") if _source_clock(args.get("until")) else None,
            "returned_matches": 0,
        })
    # A source must explicitly name the oldest retained timestamp. The
    # oldest row returned by a limited query is NOT a retention boundary.
    oldest = max(explicit_boundaries) if explicit_boundaries else None
    outside = bool(anchor and oldest and anchor < oldest)
    return {
        "classification": (
            "outside_retention_source_explicit" if outside
            else "empty_result_scope_or_retention_unknown" if attempted
            else "not_established"
        ),
        "explicit_oldest_retained_timestamp": oldest.isoformat() if oldest else None,
        "empty_past_log_reads": attempted[:4],
        "empty_general_log_query_seen": any(x["unscoped"] for x in attempted),
        "matched_zero_not_evidence_of_absent_controller_execution": True,
        "total_global_log_count_not_a_retention_boundary": True,
    }


def _scope_candidates(receipts: list[dict], attribute: str,
                      history_ids: set[str]) -> dict:
    """Full original inventory, NEVER the compacted model excerpt or room."""
    matching: dict[str, dict] = {}
    inspected = 0
    for receipt in receipts[:_MAX_RECEIPTS]:
        if (not isinstance(receipt, dict) or receipt.get("success") is not True
                or receipt.get("name") != "hub_list_devices"):
            continue
        _, native = _response(receipt)
        if not isinstance(native, dict) or not isinstance(native.get("devices"), list):
            continue
        devices = native["devices"]
        if len(devices) > _MAX_INVENTORY:
            continue
        inspected += 1
        for device in devices:
            if not isinstance(device, dict):
                continue
            ident = device.get("id")
            ident = str(ident) if type(ident) in (str, int) else ""
            states = device.get("currentStates")
            if (not _SAFE_ID.fullmatch(ident)
                    or not isinstance(states, dict)
                    or attribute not in states):
                continue
            matching[ident] = {
                "device_id": ident,
                "label": _safe_label(device.get("label")),
                "historical_state_not_proven_by_current_inventory": True,
                "history_already_queried": ident in history_ids,
            }
    return {
        "role": "scope_coverage_not_causal_inputs",
        "matched_capability": attribute,
        "full_original_inventory_reads_inspected": inspected,
        "eligible_capability_device_count": len(matching),
        "candidates": list(matching.values())[:_MAX_SCOPE_CHOICES],
        "omitted": max(0, len(matching) - _MAX_SCOPE_CHOICES),
        "room_label_not_used_as_causal_identity": True,
    }


def stage_b_read_frontier(receipts: list[dict], read_catalog: list[dict],
                          *, max_choices: int = 8) -> dict:
    """Rank *advisory* next-read proposals. The model owns tool choice.

    Candidates are SOURCE-scope claims, never event-time decision proofs.
    Per-request read caps are advertised here and enforced only by the
    optional bounded Stage B recovery runtime.
    """
    if not isinstance(receipts, list) or not isinstance(read_catalog, list):
        return {"status": "unavailable", "ranked_reads": []}
    offered = _tool_specs(read_catalog)
    reports, commands, unfiltered_targets = _source_rows(receipts)
    reports.sort(key=lambda x: x["time"], reverse=True)
    commands.sort(key=lambda x: x["time"], reverse=True)
    if not reports and not commands:
        return {"status": "no_source_attested_transition", "ranked_reads": []}
    anchor = reports[0] if reports else None
    anchor_time = anchor["time"] if anchor else commands[0]["time"]
    # Latest paired state report on that SAME target, not another device.
    related = [x for x in reports
               if anchor and x["device"] == anchor["device"]
               and x["attribute"] == anchor["attribute"]][:8]
    pair = next((x for x in related[1:] if x["value"] != anchor["value"]), None) if anchor else None
    begin = min([anchor_time, pair["time"]] if pair else [anchor_time]) - timedelta(minutes=10)
    end = max([anchor_time, pair["time"]] if pair else [anchor_time]) + timedelta(minutes=2)
    if end - begin > timedelta(hours=2):
        begin = anchor_time - timedelta(minutes=12)
        end = anchor_time + timedelta(minutes=2)
    focal_id = anchor["device"] if anchor else commands[0]["device"]
    focal_attribute = anchor["attribute"] if anchor else "switch"
    history_ids = {x["device"] for x in reports} | {x["device"] for x in commands}
    scope = _scope_candidates(receipts, focal_attribute, history_ids)
    coverage = _log_coverage(receipts, anchor_time)
    listener_map: dict[str, dict] = {}
    for row in related:
        for app in row["listeners"]:
            listener_map.setdefault(app["id"], app)
    issuer_ids = list(dict.fromkeys(
        c["issuer"] for c in commands if c["device"] == focal_id
    ))[:4]
    candidates = list(listener_map.values())[:_MAX_LISTENERS]
    tried_scoped = {
        _id(r.get("arguments", {}).get("appId"))
        for r in receipts if isinstance(r, dict)
        and r.get("name") == "hub_get_logs"
        and isinstance(r.get("arguments"), dict)
        and r["arguments"].get("appId") is not None
    } - {None}
    proposals = []
    history_spec = offered.get("hub_list_device_events")
    if history_spec and focal_id not in unfiltered_targets:
        args = _args(history_spec, focal_id, begin, end, logs=False)
        if args is not None and "attribute" not in args:
            proposals.append({
                "rank": 1, "priority": 100,
                "category": "same_output_unfiltered_command_and_state_history",
                "leaf": history_spec["name"], "arguments": args,
                "grounded_in": "original_focal_state_history",
                "reason": "An attribute-filtered state history cannot show other attributes or command-issuer rows",
                "not_a_claim_that_commands_exist": True,
            })
    app_spec = offered.get("hub_get_logs")
    if app_spec and coverage["classification"] != "outside_retention_source_explicit":
        for ident in issuer_ids:
            if ident in tried_scoped:
                continue
            args = _args(app_spec, ident, begin, end, logs=True)
            if args is not None:
                proposals.append({
                    "priority": 80, "category": "recorded_command_issuer_app_log",
                    "leaf": app_spec["name"], "arguments": args,
                    "app_role": "command_issuer_not_upstream_trigger",
                    "grounded_in": "original_device_command_row",
                })
        for listener in candidates:
            ident = listener["id"]
            if ident in tried_scoped or ident in issuer_ids:
                continue
            args = _args(app_spec, ident, begin, end, logs=True)
            if args is not None:
                proposals.append({
                    "priority": 60, "category": "notified_listener_app_log",
                    "leaf": app_spec["name"], "arguments": args,
                    "app_role": "notified_only_not_command_issuer",
                    "grounded_in": "original_device_state_triggered_list",
                })
    proposals.sort(key=lambda x: -x["priority"])
    for n, candidate in enumerate(proposals):
        candidate["rank"] = n + 1
    unscoped_empty = coverage["empty_general_log_query_seen"]
    return {
        "schema": "v2-stage-b-evidence-frontier.v1",
        "status": "ranked_original_source_candidates",
        "advisory_only": True,
        "source_window_start": begin.isoformat(),
        "source_window_end": end.isoformat(),
        "focal": {
            "device_id": focal_id,
            "observed_attribute": focal_attribute,
            "latest_report_time": anchor["date"] if anchor else None,
            "other_value_report_time": pair["date"] if pair else None,
            "not_a_physical_outcome_confirmation": True,
        },
        "scope_candidates": scope,
        "causal_app_candidates": {
            "recorded_command_issuers": issuer_ids,
            "notified_listener_candidates_not_issuers": candidates,
            "source_not_current_room_grouping": True,
        },
        "log_retention": coverage,
        "ranked_reads": proposals[:max(1, min(_MAX_PROPOSALS, max_choices))],
        "ranked_choices_omitted": max(0, len(proposals)-max(1,min(_MAX_PROPOSALS,max_choices))),
        "empty_broad_log_scoped_recovery_eligible": bool(
            unscoped_empty and candidates and app_spec is not None
            and coverage["classification"] != "outside_retention_source_explicit"
            and any(x["category"] == "notified_listener_app_log" for x in proposals)
        ),
        "read_limits": {"max_stage_b_recovery_reads": 2,
                        "max_stage_b_recovery_app_scoped_reads": 2},
        "native_tool_issued_by_this_index": False,
        "model_must_select_or_decline": True,
        "candidate_not_proof_of_actual_trigger_or_physical_effect": True,
    }



def stage_b_source_allowed(frontier: dict, name: str, args: dict) -> bool:
    """Validate a model CHOSEN Stage B recovery against original source IDs.

    Additional native MCP schema validation still applies. This check only
    stops an ungrounded source target, accidental broad retry or write.
    The ranker never dispatches a request.
    """
    if (not isinstance(frontier, dict) or not isinstance(name, str)
            or not isinstance(args, dict)
            or name not in ("hub_list_device_events", "hub_get_logs")):
        return False
    for proposal in frontier.get("ranked_reads", []):
        if not isinstance(proposal, dict) or proposal.get("leaf") != name:
            continue
        expected = proposal.get("arguments")
        if not isinstance(expected, dict):
            continue
        id_field = "appId" if name == "hub_get_logs" else "deviceId"
        actual = args.get(id_field)
        required = expected.get(id_field)
        if str(actual) != str(required) or actual is None:
            continue
        if name == "hub_get_logs":
            if args.get("mode") != "past":
                continue
        elif args.get("attribute") not in (None, ""):
            # This Stage B specific recovery seeks unfiltered output commands,
            # not an arbitrarily selected sibling or numeric input query.
            continue
        if "limit" in args and (type(args["limit"]) is not int
                                or not 1 <= args["limit"] <= 100):
            continue
        # Never silently expand a sourced bounded incident window.
        valid = True
        for field in ("since", "until"):
            if field in args:
                stamp = _source_clock(args[field])
                floor = _source_clock(frontier.get("source_window_start"))
                ceil = _source_clock(frontier.get("source_window_end"))
                if stamp is None or floor is None or ceil is None:
                    valid = False
                    break
                if field == "since" and stamp < floor:
                    valid = False
                    break
                if field == "until" and stamp > ceil:
                    valid = False
                    break
        if valid and ("since" not in args or "until" not in args
                      or _source_clock(args["since"]) <= _source_clock(args["until"])):
            return True
    return False
