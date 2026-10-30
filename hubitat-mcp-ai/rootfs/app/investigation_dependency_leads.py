"""Source-attested dependency leads for the original unified investigation agent.

This deliberately produces *leads*, not attribution. A link between an app
and a device is never sufficient proof that the app caused a transition.
Only successful read-only receipts with an independently verified identity
are admitted. This module performs no tools or Hubitat writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _id(value: Any) -> str | None:
    text = str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) else ""
    return text if text.isdecimal() and int(text) > 0 else None


def _event_kind(value: Any) -> str | None:
    key = str(value or "").casefold().replace("_", "-")
    return {
        "on": "on", "off": "off", "switch-on": "on", "switch-off": "off",
        "setlevel": "brightness", "brightness": "brightness",
        "active": "active", "inactive": "inactive",
        "motion": "motion", "mode": "mode",
    }.get(key)


def build_dependency_leads(
    receipts: Sequence[Mapping[str, Any]], *,
    since: str, until: str, target_ids: Sequence[str],
    max_records: int = 400,
) -> dict[str, Any]:
    """Build a bounded causal lead graph solely from source-attested receipts.

    Consumers may use verified association edges to decide what to READ next.
    Temporal proximity is described as correlation only, never causation.
    """
    start, end = _stamp(since), _stamp(until)
    targets = {_id(i) for i in target_ids}
    targets.discard(None)
    if start is None or end is None or start >= end or not targets:
        return {"status": "invalid-scope", "nodes": [], "edges": [], "observations": []}
    nodes: dict[str, dict[str, str]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    observations: list[dict[str, Any]] = []
    scanned = 0
    truncated = False

    def node(kind: str, ident: str) -> str:
        key = kind + ":" + ident
        nodes[key] = {"id": key, "kind": kind}
        return key

    def edge(source: str, dest: str, relationship: str, receipt_index: int) -> None:
        key = (source, dest, relationship)
        if key not in edges:
            edges[key] = {"source": source, "target": dest,
                          "relationship": relationship, "receipt_indices": []}
        if receipt_index not in edges[key]["receipt_indices"]:
            edges[key]["receipt_indices"].append(receipt_index)

    for index, receipt in enumerate(receipts):
        if receipt.get("success") is not True or receipt.get("mutates") is True:
            continue
        details = receipt.get("details")
        if not isinstance(details, Mapping):
            continue

        # Association metadata must explicitly attest both endpoint IDs.
        # Never regex arbitrary log text or infer from a similar app name.
        if receipt.get("evidence_kind") == "verified_automation_dependency":
            app_id = _id(details.get("appId"))
            device_id = _id(details.get("deviceId"))
            role = details.get("role")
            if app_id and device_id and device_id in targets and role in (
                "controls", "observes", "trigger", "input"
            ):
                edge(node("app", app_id), node("device", device_id),
                     "verified-" + role, index)

        # Explicit source-timestamped events; app command and device report
        # remain separate observations even if their timestamps match.
        if receipt.get("evidence_kind") not in (
            "group_archived_switch_history", "recent_edge_switch_context",
            "verified_device_event", "verified_app_execution"
        ):
            continue
        rows = details.get("observations")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if scanned >= max_records:
                truncated = True
                break
            scanned += 1
            if not isinstance(row, Mapping):
                continue
            device_id = _id(row.get("device_id") or row.get("deviceId"))
            app_id = _id(row.get("app_id") or row.get("appId"))
            stamp = _stamp(row.get("date") or row.get("observed_at"))
            kind = _event_kind(row.get("value") or row.get("action"))
            basis = row.get("timestamp_basis")
            if stamp is None or not start <= stamp <= end or kind is None:
                continue
            if basis != "source":
                continue
            if device_id not in targets:
                continue
            # Do not create an app command from a device report's app label.
            origin = row.get("record_type")
            if origin not in ("device-report", "app-command", "app-decision"):
                continue
            if origin != "device-report" and not app_id:
                continue
            subject = node("device", device_id)
            actor = node("app", app_id) if app_id and origin != "device-report" else subject
            observations.append({
                "timestamp": stamp.isoformat(), "device_id": device_id,
                "app_id": app_id if origin != "device-report" else None,
                "kind": kind, "record_type": origin,
                "receipt_index": index, "timestamp_basis": "source",
            })
            if origin == "app-command":
                edge(actor, subject, "command-issued-not-confirmed-transition", index)
        if truncated:
            break

    observations.sort(key=lambda item: (item["timestamp"], item["receipt_index"]))
    unresolved = [id for id in sorted(targets)
                  if not any(row["device_id"] == id for row in observations)]
    return {
        "status": "bounded" if truncated else "complete-read-of-provided-receipts",
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "edges": sorted(edges.values(), key=lambda e: (e["source"], e["target"], e["relationship"])),
        "observations": observations,
        "unobserved_target_ids": unresolved,
        "max_records": max_records,
        "coverage_complete": False,
        "causal_attribution_verified": False,
        "note": "An association or chronological match cannot establish an upstream initiator.",
    }


__all__ = ["build_dependency_leads"]
