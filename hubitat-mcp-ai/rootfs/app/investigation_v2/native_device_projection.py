"""Typed, bounded device configuration and details evidence for native V2.

Generic device modes contain configuration, driver identity and section-read
status not represented by the original state-only projection. Preserve useful
structural facts without returning arbitrary preference values, source code,
addresses, secrets, or free-form instructions from MCP data.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from .native_source_adapters import safe_string, unwrapped

_PRIVATE = re.compile(
    r"(?i)(?:token|secret|password|credential|key|authorization|cookie|"
    r"bearer|ipaddress|macaddress|url|endpoint|pin|passphrase)"
)
_DRIVER_FIELDS = frozenset({
    "name", "label", "type", "driverName", "driverType", "namespace",
    "driverId", "manufacturer", "model", "version", "sourceName",
    "class", "platform", "id", "driver", "driverNamespace",
})
_READ_FIELDS = frozenset({
    "status", "count", "total", "complete", "available",
    "source", "reason", "truncated", "nextCursor",
})
_SECTION_FIELDS = frozenset({"status", "source", "available", "count"})
_PREF_METADATA = frozenset({"name", "label", "title", "type", "description", "required"})


def _safe_keys(data: Mapping[str, Any], allowed: frozenset[str],
               *, count: int = 30) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in list(data.items())[:80]:
        if key not in allowed or _PRIVATE.search(key):
            continue
        if isinstance(value, bool):
            safe[key] = value
        elif type(value) in (int, float):
            safe[key] = value
        elif isinstance(value, str):
            # Do not expose network endpoints or path-like source fields.
            if key == "source" or _PRIVATE.search(value):
                continue
            safe[key] = safe_string(value, 110)
        if len(safe) >= count:
            break
    return safe


def device_mode_evidence(data: Any) -> dict[str, Any]:
    """Safe structural projection of one hub_get_device source response."""
    raw = unwrapped(data)
    if not raw:
        return {}
    mode = raw.get("mode")
    if mode not in ("configuration", "details"):
        return {}
    result: dict[str, Any] = {"device_mode": mode}
    info = raw.get("deviceInfo")
    if isinstance(info, dict):
        fields = _safe_keys(info, _DRIVER_FIELDS)
        if fields:
            result["device_identity"] = fields
    for field in ("deviceInfoRead", "preferenceRead", "sourceCoverage"):
        value = raw.get(field)
        if isinstance(value, dict):
            result[field] = _safe_keys(value, _READ_FIELDS)
    editable = raw.get("editableFields")
    if isinstance(editable, list):
        result["editable_field_names"] = [
            safe_string(x, 75) for x in editable[:24]
            if isinstance(x, str) and not _PRIVATE.search(x)
        ]
    elif isinstance(editable, dict):
        result["editable_field_names"] = [
            safe_string(key, 75) for key in list(editable)[:30]
            if isinstance(key, str) and not _PRIVATE.search(key)
        ]
    preferences = raw.get("preferences")
    if isinstance(preferences, dict):
        result["preference_names"] = [
            safe_string(key, 75) for key in list(preferences)[:30]
            if isinstance(key, str) and not _PRIVATE.search(key)
        ]
    elif isinstance(preferences, list):
        result["preference_metadata"] = [
            _safe_keys(row, _PREF_METADATA)
            for row in preferences[:20] if isinstance(row, dict)
            and isinstance(row.get("name"), str)
            and not _PRIVATE.search(row["name"])
        ]
    source = raw.get("driverSource")
    if isinstance(source, dict):
        result["driver_source_metadata"] = _safe_keys(
            source, frozenset({"status", "available", "count", "lineCount",
                               "truncated", "reason", "driverName", "namespace"}))
        result["driver_source_content_omitted"] = (
            any(k in source for k in ("source", "code", "text", "body"))
        )
    elif isinstance(source, str):
        result["driver_source_content_omitted"] = True
    sections = raw.get("sections")
    if isinstance(sections, dict):
        result["sections_present"] = [
            safe_string(k, 55) for k in list(sections)[:24]
            if isinstance(k, str) and not _PRIVATE.search(k)
        ]
        result["sections_status"] = {
            k: _safe_keys(value, _SECTION_FIELDS)
            for k, value in list(sections.items())[:16]
            if isinstance(k, str) and isinstance(value, dict)
            and not _PRIVATE.search(k)
        }
    section_read = raw.get("sectionRead")
    if isinstance(section_read, dict):
        result["section_read_status"] = {
            k: _safe_keys(v, _SECTION_FIELDS) for k,v in
            list(section_read.items())[:16]
            if isinstance(k,str) and isinstance(v,dict)
            and not _PRIVATE.search(k)
        }
    return result


__all__ = ["device_mode_evidence"]
