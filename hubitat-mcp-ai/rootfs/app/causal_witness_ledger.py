"""V3 witness and source-coverage ledger (shadow/read-only).

This module is a deterministic projection over the EXISTING independently
scoped MCP evidence. It is not a second reasoner or a tool executor. In
particular:
  * physical/bridge-reported switch != initiating controller
  * event-notified app != command issuer
  * source time != journal collector reception
  * a correlated input != verified command
  * missing rows != proof of absence
Nothing here changes model prompts or terminal publication in Stage B.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


def _when(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        instant = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return instant.astimezone(timezone.utc) if instant.tzinfo else None


def _id(value: Any) -> str:
    text = str(value or "")
    return text if text.isdecimal() and int(text) > 0 else ""


def _witness_id(row: Mapping[str, Any]) -> str:
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"))
    return "w_" + sha256(canonical.encode("utf-8")).hexdigest()[:14]


def _details_args(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    args = receipt.get("arguments")
    if not isinstance(args, Mapping):
        return {}
    inner = args.get("args")
    return inner if isinstance(inner, Mapping) else args


def build_witness_coverage_ledger(
    facts: Mapping[str, Any] | None,
    receipts: Sequence[Mapping[str, Any]],
    *,
    max_witnesses: int = 120,
) -> dict[str, Any] | None:
    """Source-typed, bounded, witnessable source coverage by target.

    Claim authority is intentionally narrow: issuer verification means a
    matching **Hubitat command-on** attributed to an app and followed within
    two seconds by a source-timed ON report for the SAME target. This proves
    the immediate Hubitat app command was recorded, not its upstream reason,
    device physical ACK, or exclusion of an external concurrent command.
    """
    if not facts or not facts.get("source_attested"):
        return None
    ids = [_id(x) for x in facts.get("target_device_ids") or []]
    ids = sorted({x for x in ids if x}, key=int)[:16]
    if not ids:
        return None
    max_witnesses = max(1, min(200, int(max_witnesses)))
    raw = facts.get("incident_ledger") or []
    kinds = {
        "journal_source_switch_on": ("state-report", "source"),
        "journal_source_switch_off": ("state-report", "source"),
        "journal_received_switch_on": ("collector-reception", "collector-received"),
        "journal_received_switch_off": ("collector-reception", "collector-received"),
        "reported_switch_on": ("state-report", "source-reported"),
        "reported_switch_off": ("state-report", "source-reported"),
        "issued_on": ("issued-command", "hubitat-command"),
        "issued_off": ("issued-command", "hubitat-command"),
        "issued_setlevel": ("issued-command", "hubitat-command"),
        "reported_level": ("state-report", "source-reported"),
    }
    seen: dict[str, dict[str, Any]] = {}
    for row in raw[:200]:
        if not isinstance(row, Mapping):
            continue
        device = _id(row.get("device_id"))
        kind = str(row.get("event_class") or "")
        if device not in ids or kind not in kinds:
            continue
        instant = _when(row.get("date"))
        if instant is None:
            continue
        role, clock = kinds[kind]
        app = _id(row.get("app_id")) if role == "issued-command" else ""
        # Exclude malformed command-issuer evidence from claimed attribution,
        # but retain the command row as a witness with unknown actor.
        point = {
            "entity": device, "role": role, "event_class": kind,
            "time": instant.isoformat(), "clock_basis": clock,
            "app_issuer": app if app else None,
            "source_class": ("historical-journal"
                             if kind.startswith("journal_")
                             else "hubitat-device-history"),
        }
        point["witness_id"] = _witness_id(point)
        seen[point["witness_id"]] = point
    # Independent source-timed motion/occupancy reports have their own
    # witnessed role. A journal collector-reception input remains excluded
    # even if it repeatedly coincides with an actuator state.
    for row in (facts.get("independent_input_observations") or [])[:48]:
        if not isinstance(row, Mapping):
            continue
        ident = _id(row.get("device_id"))
        attr = str(row.get("attribute") or "")
        basis = str(row.get("timestamp_basis") or "")
        instant = _when(row.get("time"))
        if (not ident or attr not in ("motion", "occupancy", "presence")
                or basis not in ("source", "source-reported")
                or instant is None):
            continue
        point = {
            "entity": ident, "role": "input-report",
            "event_class": attr,
            "value": str(row.get("value") or "")[:30],
            "time": instant.isoformat(), "clock_basis": basis,
            "app_issuer": None,
            "source_class": str(row.get("source_read") or "verified-input")[:50],
        }
        point["witness_id"] = _witness_id(point)
        seen[point["witness_id"]] = point
    witnesses = sorted(
        seen.values(),
        key=lambda x: (x["time"], int(x["entity"]), x["role"], x["event_class"]),
    )
    total = len(witnesses)
    witnesses = witnesses[:max_witnesses]
    target_coverage = {
        _id(row.get("device_id")): row
        for row in facts.get("target_coverage") or []
        if isinstance(row, Mapping) and _id(row.get("device_id")) in ids
    }
    # Match from the entire bounded source ledger, not the presentation cap.
    verified: list[dict[str, Any]] = []
    for ident in ids:
        commands = [w for w in seen.values()
                    if w["entity"] == ident
                    and w["event_class"] == "issued_on"
                    and w["app_issuer"]]
        reports = [w for w in seen.values()
                   if w["entity"] == ident
                   and w["event_class"] in (
                       "journal_source_switch_on", "reported_switch_on")]
        for state in reports:
            st = _when(state["time"])
            eligible = []
            for command in commands:
                delay = (st - _when(command["time"])).total_seconds()
                if 0 <= delay <= 2:
                    eligible.append((delay, command))
            if eligible:
                delay, cmd = min(eligible, key=lambda x: x[0])
                verified.append({
                    "device_id": ident, "hubitat_app_id": cmd["app_issuer"],
                    "command_witness_id": cmd["witness_id"],
                    "state_witness_id": state["witness_id"],
                    "command_to_state_ms": round(delay * 1000),
                    "verification": "recorded-hubitat-immediate-command",
                    "upstream_reason_verified": False,
                    "physical_ack_verified": False,
                })
    coverage = []
    for ident in ids:
        source_reads = []
        journal_reads = []
        for receipt in receipts[:160]:
            if receipt.get("success") is not True or receipt.get("mutates") is True:
                continue
            args = _details_args(receipt)
            if (receipt.get("sub_tool") == "hub_list_device_events"
                    and _id(args.get("deviceId")) == ident):
                source_reads.append(receipt)
            if (receipt.get("evidence_kind") == "group_archived_switch_history"
                    and _id(args.get("device_id")) == ident):
                journal_reads.append(receipt)
        target = target_coverage.get(ident, {})
        device_w = [w for w in seen.values() if w["entity"] == ident]
        commands = [w for w in device_w if w["role"] == "issued-command"]
        source_states = [w for w in device_w
                         if w["event_class"] in (
                             "journal_source_switch_on", "journal_source_switch_off",
                             "reported_switch_on", "reported_switch_off")]
        archived_received = [w for w in device_w
                             if w["clock_basis"] == "collector-received"]
        issuer_rows = [x for x in verified if x["device_id"] == ident]
        # Source coverage is NOT completeness unless independently proved;
        # successful queries can be truncated or have retention gaps.
        coverage.append({
            "device_id": ident,
            "device_history": ("observed"
                               if any(w["source_class"] == "hubitat-device-history"
                                      for w in device_w)
                               else "queried-partial" if source_reads
                               else "not-queried"),
            "journal_switch": ("observed-source"
                               if any(w["source_class"] == "historical-journal"
                                      and w["clock_basis"] == "source"
                                      for w in device_w)
                               else "queried-partial" if journal_reads
                               else "not-queried"),
            "state_report_witnesses": len(source_states),
            "command_witnesses": len(commands),
            "reception_only_witnesses": len(archived_received),
            "recorded_on_issuer_witnesses": len(issuer_rows),
            "original_upstream_command_source":
                "not-independently-attested",
            "historical_app_execution": "not-independently-attested",
            "complete_historical_coverage": False,
            "journal_gap_count": int(target.get("journal_gaps") or 0),
            "journal_truncated": any(
                (x.get("details") or {}).get("truncated") is True
                for x in journal_reads),
        })
    relationships = []
    for link in (facts.get("input_app_relationships") or [])[:16]:
        if not isinstance(link, Mapping):
            continue
        ident = _id(link.get("input_device_id"))
        if not ident:
            continue
        relationships.append({
            "input_id": ident,
            "observed_notification_app_ids": [
                x for x in (_id(v) for v in link.get("input_notified_app_ids") or []) if x
            ][:12],
            "relationship": str(link.get("relationship") or "unknown")[:90],
            "is_historical_execution_proof": False,
        })
    return {
        "schema": "causal-witness-ledger.v1",
        "shadow_only": True,
        "target_count": len(ids), "witness_total": total,
        "witnesses_omitted": max(0, total - len(witnesses)),
        "witnesses": witnesses,
        "target_source_coverage": coverage,
        "immediate_hubitat_on_command_matches": verified[:24],
        "observed_input_app_relationships": relationships,
        "source_timed_input_witness_count": sum(
            w["role"] == "input-report" for w in seen.values()),
        "reception_only_pattern_count": len(
            facts.get("archived_input_reception_patterns") or []),
        "issuer_verified_target_count": len({
            v["device_id"] for v in verified
        }),
        "root_cause_verified": False,
        "can_prove_absence_from_empty_history": False,
    }


__all__ = ["build_witness_coverage_ledger"]
