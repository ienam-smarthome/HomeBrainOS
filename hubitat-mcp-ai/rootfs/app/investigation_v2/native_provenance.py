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
        "issuer_apps": sorted(issuers.values(),
                              key=lambda r: (-r["count"], r["appId"]))[:12],
        "count": len(events),
        "events": rows,
        "provenance_basis": "device-scoped event source producedBy.appId",
        "source_complete": False}


def dependent_summary(data: Any) -> dict[str, Any] | None:
    raw = unwrapped(data)
    apps = raw.get("appsUsing")
    if not isinstance(apps, list):
        return None
    records = []
    for item in apps[:150]:
        if not isinstance(item, dict):
            continue
        ident = numeric_id(item.get("appId") or item.get("id"))
        if ident:
            records.append({
                "appId": ident,
                "name": safe_string(item.get("name") or item.get("label")
                                    or item.get("appName"), 95)})
    return {"apps_using": records[:80], "count": len(apps),
            "deviceId": numeric_id(raw.get("deviceId")),
            "source_complete": False}


def driver_summary(data: Any) -> dict[str, Any] | None:
    raw = unwrapped(data)
    drivers = raw.get("drivers")
    if not isinstance(drivers, list):
        return None
    records = []
    for item in drivers[:300]:
        if not isinstance(item, dict):
            continue
        ident = numeric_id(item.get("driverId") or item.get("id"))
        if ident:
            records.append({
                "driverId": ident,
                "name": safe_string(item.get("name") or item.get("label"), 95),
                "namespace": safe_string(item.get("namespace"), 50)})
    return {"drivers": records[:80], "count": len(drivers),
            "source_complete": False}


def app_config_summary(data: Any) -> dict[str, Any]:
    raw = unwrapped(data)
    result = {}
    for key in ("id", "appId", "name", "label", "type",
                "enabled", "paused", "status"):
        value = raw.get(key)
        if type(value) in (bool, str, int):
            result[key] = value if isinstance(value, bool) else safe_string(value, 100)
    for key in ("settings", "preferences", "inputs"):
        value = raw.get(key)
        if isinstance(value, dict):
            result[key + "_field_names"] = [
                safe_string(name, 75) for name in list(value)[:50]
                if isinstance(name, str) and
                not any(private in name.casefold() for private in (
                    "password", "token", "secret", "credential", "key", "url"))]
    return result


def source_metadata(data: Any) -> dict[str, Any]:
    """A source read without projected content is metadata, not code analysis."""
    raw = unwrapped(data)
    result = {}
    for key in ("id", "name", "namespace", "type", "status",
                "driverId", "appId", "version"):
        value = raw.get(key)
        if type(value) in (str, int, bool):
            result[key] = safe_string(value, 95)
    result["source_content_available"] = any(
        isinstance(raw.get(k), str) and bool(raw.get(k))
        for k in ("source", "code", "text", "content"))
    result["source_content_projected"] = False
    return result


def correlated_command_warnings(witnesses: list[dict[str, Any]],
                                focus_ids: set[str]) -> list[dict[str, Any]]:
    """Source timestamp coincidences, explicitly NOT proven causal links.

    Uses printed same-date local clock values only; event timestamps may
    include offsets while Hubitat log timestamps have no verified zone.
    Correlates general 'method X' warnings to command-X events, regardless
    of device, app, or method naming.
    """
    import re
    def millis(value: Any) -> tuple[str, int] | None:
        match = re.search(
            r"(\d{4}-\d{2}-\d{2})[T ](\\d{2}): (\d{2}): (\d{2})[.](\\d{1,3})",
            str(value or ""))
        if not match:
            return None
        day, hh, mm, ss, ms = match.groups()
        return day, ((int(hh)*60+int(mm))*60+int(ss))*1000 + int(ms.ljust(3,"0"))
    commands=[]
    warnings=[]
    for witness in witnesses[:16]:
        data=witness.get("source_data")
        if not isinstance(data,dict):
            continue
        op=witness.get("operation")
        if op=="hub_list_device_events" and str(witness.get("read_filters",{}).get("deviceId")) in focus_ids:
            for event in data.get("events",[])[:100]:
                if not isinstance(event,dict):
                    continue
                name=event.get("name")
                producer=event.get("producedBy")
                if isinstance(name,str) and name.startswith("command-") and isinstance(producer,dict) and producer.get("appId"):
                    parsed=millis(event.get("date"))
                    if parsed:
                        commands.append((name[8:].casefold(),str(producer["appId"]),
                                         safe_string(producer.get("name"),80),
                                         event.get("date"),parsed,witness["read"]))
        if op=="hub_get_logs":
            summary=data.get("log_summary",{})
            if not isinstance(summary,dict):
                continue
            for group in summary.get("warning_error_groups",[]):
                if not isinstance(group,dict) or str(group.get("source_id")) not in focus_ids:
                    continue
                method=re.search(r"\\bmethod\\s+([A-Za-z_][A-Za-z0-9_]*)\\b",
                                 str(group.get("message") or ""),re.I)
                if not method:
                    continue
                for field in ("oldest_returned","newest_returned"):
                    parsed=millis(group.get(field))
                    if parsed:
                        warnings.append((method.group(1).casefold(),
                                         group[field],parsed,witness["read"]))
    found=[]
    seen=set()
    for method,app_id,app_name,when,(day,number),event_read in commands:
        for warn_method,warn_when,(warn_day,warn_number),log_read in warnings:
            difference=abs(number-warn_number)
            ident=(app_id,method,when,warn_when)
            if (method==warn_method and day==warn_day and difference<=1000
                    and ident not in seen):
                seen.add(ident)
                found.append({
                    "appId":app_id,"app":app_name,"command":method,
                    "command_time":safe_string(when,65),
                    "warning_time":safe_string(warn_when,65),
                    "wall_clock_delta_ms":difference,
                    "event_read":event_read,"log_read":log_read,
                    "causal_proof":False,
                    "time_zone_alignment_verified":False})
    return sorted(found,key=lambda row:row["wall_clock_delta_ms"])[:6]
