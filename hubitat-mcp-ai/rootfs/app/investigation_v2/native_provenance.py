"""Typed source provenance for model-chosen cross-domain READ investigations.

Only the already-approved, device-scoped event history can attest that a
named app issued a command. Event descriptions and speech/media arguments
are never passed through to the language model.
"""
from __future__ import annotations
from typing import Any
from .native_source_adapters import safe_string, unwrapped


def numeric_id(value: Any) -> str | None:
    if type(value) not in (str, int):
        return None
    ident = str(value)
    return ident if ident.isdecimal() and 0 < len(ident) <= 16 and int(ident) > 0 else None


def source_identities(operation: str, data: Any, *,
                      scoped_device_id: str | None = None) -> dict[str, set[str]]:
    """Attest IDs in their original app, driver or device namespace."""
    raw = unwrapped(data)
    known = {"device": set(), "app": set(), "driver": set()}
    def admit(kind: str, candidate: Any) -> None:
        found = numeric_id(candidate)
        if found:
            known[kind].add(found)
    if operation == "hub_list_device_events" and scoped_device_id:
        for event in raw.get("events", [])[:150]:
            if not isinstance(event, dict):
                continue
            issuer = event.get("producedBy")
            if isinstance(issuer, dict):
                admit("app", issuer.get("appId"))
                if str(issuer.get("deviceId") or "") == scoped_device_id:
                    admit("device", issuer.get("deviceId"))
    elif operation == "hub_list_device_dependents" and scoped_device_id:
        for row in raw.get("appsUsing", [])[:150]:
            if isinstance(row, dict):
                admit("app", row.get("appId") or row.get("id"))
        parent = raw.get("parentApp")
        if isinstance(parent, dict):
            admit("app", parent.get("appId") or parent.get("id"))
    elif operation == "hub_list_drivers":
        for row in raw.get("drivers", [])[:300]:
            if isinstance(row, dict):
                admit("driver", row.get("driverId") or row.get("id"))
    elif operation == "hub_get_device":
        info = raw.get("deviceInfo")
        if isinstance(info, dict):
            admit("driver", info.get("driverId"))
    elif operation in ("hub_list_apps", "hub_list_rules"):
        collection = "apps" if operation == "hub_list_apps" else "rules"
        for row in raw.get(collection, [])[:500]:
            if isinstance(row, dict):
                admit("app", row.get("appId") or row.get("id"))
    elif operation in ("hub_list_devices", "hub_get_device_health"):
        for row in raw.get("devices", [])[:500]:
            if isinstance(row, dict):
                admit("device", row.get("deviceId") or row.get("id"))
    elif operation == "hub_get_logs":
        from .native_source_adapters import log_source, log_rows
        for row in log_rows(raw) or []:
            kind, identity, _ = log_source(row)
            if kind in ("device", "dev"):
                admit("device", identity)
            elif kind == "app":
                admit("app", identity)
    return known


def event_summary(data: Any) -> dict[str, Any] | None:
    """Keep command issuer, command name and time; omit private text."""
    raw = unwrapped(data)
    events = raw.get("events")
    if not isinstance(events, list):
        return None
    rows: list[dict[str, Any]] = []
    issuers: dict[str, dict[str, Any]] = {}
    for event in events[:130]:
        if not isinstance(event, dict) or not isinstance(event.get("name"), str):
            continue
        name = safe_string(event["name"], 55)
        stamp = safe_string(event.get("date") or event.get("time"), 60)
        producer = event.get("producedBy")
        producer = producer if isinstance(producer, dict) else {}
        app_id = numeric_id(producer.get("appId"))
        device_id = numeric_id(producer.get("deviceId"))
        sanitized: dict[str, Any] = {"name": name, "date": stamp}
        if app_id:
            sanitized["producedBy"] = {
                "appId": app_id, "name": safe_string(producer.get("name"), 95)}
        elif device_id:
            sanitized["producedBy"] = {
                "deviceId": device_id, "name": safe_string(producer.get("name"), 95)}
        # Never include descriptions or textual speech arguments.
        if not name.startswith("command-"):
            value = event.get("value")
            if type(value) in (bool, int, float):
                sanitized["value"] = value
            elif isinstance(value, str) and len(value) <= 40:
                sanitized["value"] = safe_string(value, 40)
        elif app_id:
            command = name[len("command-"):]
            rec = issuers.setdefault(app_id, {
                "appId": app_id, "name": safe_string(producer.get("name"), 95),
                "count": 0, "commands": {}, "newest": None,
                "oldest": None, "samples": []})
            rec["count"] += 1
            rec["commands"][command] = rec["commands"].get(command, 0) + 1
            if stamp:
                rec["newest"] = max(stamp, rec["newest"]) if rec["newest"] else stamp
                rec["oldest"] = min(stamp, rec["oldest"]) if rec["oldest"] else stamp
            if len(rec["samples"]) < 5:
                rec["samples"].append({"command": command, "date": stamp})
        if len(rows) < 80:
            rows.append(sanitized)
    return {
        "events": rows, "count": len(events),
        "issuer_apps": sorted(issuers.values(),
                              key=lambda r: (-r["count"], r["appId"]))[:12],
        "provenance_basis": "device-scoped event source producedBy.appId",
        "source_complete": False}
