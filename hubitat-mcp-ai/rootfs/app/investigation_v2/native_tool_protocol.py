"""Shared operation validation and source-backed fallback for native READ."""
from __future__ import annotations
from typing import Any, Mapping, Sequence
from .native_source_adapters import safe_string

LOG_LEVELS = frozenset({"trace", "debug", "info", "warn", "error", "all"})
_NON_READ_FLAGS = frozenset({
    "recordSnapshot", "persist", "save", "write", "update",
    "delete", "restart", "reboot", "runCommand", "execute",
})
_HIGH_VALUE = ("lastSeen", "lastActivity", "lastMessage", "healthStatus",
               "deviceHealth", "networkStatus", "mqttStatus", "dataAgeSeconds",
               "lastError", "switch", "power", "temperature")


def operation_problem(gateway: str, arguments: Mapping[str, Any]) -> str | None:
    """Validate the concrete read operation, not natural-language question keywords."""
    inner = arguments.get("args") if gateway.startswith("hub_read_") else arguments
    if not isinstance(inner, Mapping):
        return None
    for field in _NON_READ_FLAGS:
        if field in inner and inner[field] not in (False, None):
            return "write_side_effect_flag_forbidden"
    if arguments.get("tool") == "hub_list_drivers" and "deviceId" in inner:
        # The catalogue is not a per-device driver lookup. Reject the
        # unsupported target filter locally instead of producing multiple
        # avoidable MCP errors and a giant global driver list.
        return "catalog_device_filter_unsupported"
    if arguments.get("tool") == "hub_get_logs":
        level = inner.get("level")
        if level is not None and (
            not isinstance(level, str) or level.lower() not in LOG_LEVELS
        ):
            return "invalid_log_level"
        # The MCP gateway has a flat args object but mode-specific contracts.
        # 'level' applies to historical past logs, not the Logs-page device,
        # app or job tabs. Sending mode=devices with level emits a separate
        # MCP Rule Server ERROR and hides the original diagnostic question.
        # Omitted mode means the server's default 'past'.
        mode = inner.get("mode", "past")
        if level is not None and mode != "past":
            return "log_mode_level_incompatible"
        limit = inner.get("limit")
        if limit is not None and (
            type(limit) is not int or not 1 <= limit <= 500
        ):
            return "invalid_log_limit"
    return None


def guidance_for(code: str) -> str | None:
    """Only fixed reviewed guidance may be returned from failing MCP reads."""
    return {
        "invalid_log_level":
            "Use a single log level: trace, debug, info, warn, error, all; request warn and error separately.",
        "invalid_log_limit": "Use integer limit from 1 to 500.",
        "log_mode_level_incompatible":
            "Log level is a past-history filter, not a device/app/job-tab filter. "
            "For severity-filtered history use mode='past', level='warn' "
            "(or level='error'), optionally deviceId/appId and a bounded limit; "
            "for mode='devices' omit level entirely. Do not repeat the invalid pair.",
        "missing_required_operation_fields":
            "A concrete read operation lacks required input (for example deviceId for hub_get_device). Use homebrain_find_device to resolve a named device against verified live identity, then pass that deviceId.",
        "target_device_history_scope_missing":
            "This history request has no deviceId/appId and would read hub or "
            "location events, not the independently verified target device. "
            "Pass the previously verified deviceId to hub_list_device_events, "
            "or explicitly select a hub/location event mode when that "
            "separate source is genuinely needed. Do not assume these "
            "histories are interchangeable.",
        "repeated_invalid_read_proposal":
            "The same READ operation failed argument/scope checks repeatedly. "
            "Stop proposing that malformed read; choose another independently "
            "authorised source or report the evidence limitation.",
        "catalog_device_filter_unsupported":
            "hub_list_drivers is a global catalogue and cannot identify the "
            "driver of one device via deviceId. Read the verified device "
            "configuration for driver identity, or inspect independently "
            "attested calling apps with hub_get_app_config.",
        "write_side_effect_flag_forbidden":
            "Read-only V2 cannot persist snapshots or change hub state.",
        "operation_prior_timeout":
            "That operation already timed out; use a targeted read instead of retrying broad inventory.",
        "repeated_target_read_error":
            "This READ operation failed twice for the same verified target, even with different arguments. Stop trying variants of the same operation; choose an independently discovered read or finish with the evidence already collected.",
        "operation_not_independently_discovered":
            "This read operation is not attested for the selected gateway. "
            "Use a gateway/operation pair from the live read manifest or "
            "independent tool discovery; device inspection such as "
            "hub_get_device belongs on hub_read_devices, not "
            "hub_read_apps_code. Do not execute or invent a mapping.",
        "duplicate_read": "Choose a different read; exact same arguments were already tried.",
        "mcp_tool_reported_error":
            "Upstream rejected the request. Review valid arguments; do not repeat the same request.",
    }.get(code)


def source_highlights(witnesses: Sequence[Mapping[str, Any]],
                      *, max_chars: int = 3500) -> list[str]:
    """Bounded typed source observations with read IDs, never causal invention."""
    lines: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        if value not in seen and sum(map(len, lines)) + len(value) < max_chars:
            lines.append(value)
            seen.add(value)

    for w in witnesses[:12]:
        rid = w.get("read")
        op = safe_string(w.get("operation"), 65)
        data = w.get("source_data")
        if not isinstance(data, dict):
            continue
        title = f"Read #{rid} ({op})"
        summary = data.get("log_summary")
        if isinstance(summary, dict):
            add(f"{title}: {summary.get('returned_rows', 0)} log rows returned; "
                "historical completeness unverified; sample levels "
                f"{safe_string(summary.get('level_counts_in_returned_rows', {}), 120)}.")
            for item in summary.get("warning_error_groups", [])[:5]:
                if not isinstance(item, dict):
                    continue
                message = safe_string(item.get("message"), 220)
                if "level must be one of" in message.lower():
                    add(f"{title}: MCP rejected an invalid log-level argument. "
                        "This is a diagnostic-query error, not an independent hub fault.")
                    continue
                source = safe_string(item.get("source_name") or item.get("source_id"), 70)
                level = safe_string(item.get("level"), 15)
                add(f"{title}: {level} from {source} "
                    f"(source ID {safe_string(item.get('source_id'), 25)}): {message}")
            continue
        if op == "hub_get_device":
            attrs = data.get("attributes", [])
            typed = {row.get("name"): row.get("value") for row in attrs
                     if isinstance(row, dict) and isinstance(row.get("name"), str)} \
                    if isinstance(attrs, list) else {}
            selected = [f"{key}={safe_string(typed[key], 90)}"
                        for key in _HIGH_VALUE if key in typed]
            name = safe_string(data.get("label") or data.get("name"), 85)
            entity_id = safe_string(data.get("id"), 20)
            if name or selected:
                add(f"{title}: device {name} (ID {entity_id}) reports "
                    + ("; ".join(selected) if selected else
                       "identity only; detailed status unavailable") + ".")
            continue
        if op == "hub_list_device_events":
            events = data.get("events", [])
            if isinstance(events, list) and events:
                first = next((x for x in events if isinstance(x, dict)), {})
                last = next((x for x in reversed(events) if isinstance(x, dict)), {})
                def event_text(row: Mapping[str, Any]) -> str:
                    return (safe_string(row.get("name"), 45) + "=" +
                            safe_string(row.get("value"), 60) + " at " +
                            safe_string(row.get("date") or row.get("time"), 65))
                add(f"{title}: {len(events)} returned events; newest "
                    f"{event_text(first)}; oldest {event_text(last)}. "
                    "Driver health events are not proof of device heartbeats.")
            continue
        for key in ("healthAlerts", "alerts", "warnings", "errors",
                    "summary", "status", "safeMode", "uptimeSeconds",
                    "freeMemory", "temperature"):
            if key in data:
                add(f"{title}: {key}={safe_string(data[key], 175)}")
        if data.get("projection_empty") is True:
            add(f"{title}: important source fields were discarded by the evidence adapter.")
    return lines[:22]


def evidence_fallback(witnesses: Sequence[Mapping[str, Any]],
                      failures: Sequence[Mapping[str, Any]]) -> str:
    facts = source_highlights(witnesses)
    if not facts:
        return ("No interpretable observations were recovered. The investigation "
                "cannot establish the cause or current hub health.")
    lines = ["**What the hub actually reported**",
             *["- " + fact for fact in facts[:12]], "",
             "**Conclusion:** These are source observations, not a verified "
             "root cause or independent proof of physical device status."]
    if failures:
        codes = sorted({safe_string(f.get("code"), 60) for f in failures})
        lines.append("**Unresolved reads:** " + ", ".join(codes) + ".")
    return "\n".join(lines)

__all__ = ["LOG_LEVELS", "operation_problem", "guidance_for",
           "source_highlights", "evidence_fallback"]
