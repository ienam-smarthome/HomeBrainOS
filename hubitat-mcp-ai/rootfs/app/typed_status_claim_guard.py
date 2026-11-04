"""General field-attestation boundary for typed read-only device/status reports.

Data provenance, field presence, identity and units are separate. A successful
read never attests a field absent from its typed payload. Keep model-authored
prose; reconcile only checkable claims. No reads, model rounds or mutations.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_NUM = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?![\w.])")
_LINE = re.compile(
    r"^(?P<prefix>\s*(?:[-*•]\s*)?)(?P<bold>\*\*)?"
    r"(?P<label>[\w /()\-]{2,70})(?P<close>\*\*)?"
    r"\s*:\s*(?P<value>.+?)(?P<newline>\r?\n?)$",
    re.I,
)
_HEALTH = re.compile(
    r"(?i)\b(?:the\s+)?(?:hub|system|device|network)\s+"
    r"(?:is|remains|appears)\s+(?:fully\s+|completely\s+)?"
    r"(?:healthy|fine|normal|in\s+perfect\s+health)"
    r"(?:\s+with\s+no\s+(?:active\s+)?alerts?)?\.?"
)
_NO_ALERTS = re.compile(
    r"(?i)\b(?:no\s+(?:active\s+)?(?:alerts?|warnings?)"
    r"|(?:without|has\s+no)\s+(?:any\s+)?(?:active\s+)?alerts?)\b"
)
_FIRMWARE = re.compile(
    r"(?i)\b(?:hub\s+)?firmware(?:\s+(?:version|v))?\s*"
    r"(?:\d+(?:\.\d+){2,}\s+)?(?:is\s+)?"
    r"(?:up[- ]to[- ]date|current|latest)\b"
)
_TEMP_PROSE = re.compile(
    r"(?i)\btemperature\s+(?:is|was)\s+"
    r"[-+]?\d+(?:\.\d+)?\s*(?:°|degrees?\s*)?[CF]\b"
)

# Aliases are semantic field names, not driver-specific device identities.
# No cached device state, expected value, or example measurement is stored.
_FIELDS: dict[str, tuple[tuple[str, ...], str | None]] = {
    "temperature": (("temperature", "temperatureC", "temperatureF"), "temperature_unit"),
    "temp": (("temperature", "temperatureC", "temperatureF"), "temperature_unit"),
    "free memory": (("free_memory", "freeMemory"), "free_memory_unit"),
    "database": (("database_size", "dbSize"), "database_size_unit"),
    "database size": (("database_size", "dbSize"), "database_size_unit"),
    "power": (("power", "powerW", "powerWatts"), "power_unit"),
    "battery": (("battery", "batteryLevel"), "battery_unit"),
    "humidity": (("humidity", "relativeHumidity"), "humidity_unit"),
    "illuminance": (("illuminance", "lux"), "illuminance_unit"),
    "brightness": (("level", "brightness"), "level_unit"),
    "level": (("level", "brightness"), "level_unit"),
    "voltage": (("voltage",), "voltage_unit"),
    "cpu load 5 min": (("cpu_5_min", "cpu5Min", "cpu_percent", "cpuPct"), None),
    "cpu load 15 min": (("cpu_15_min", "cpu15Min", "cpu_15_percent", "cpu15Pct"), None),
    "cpu load": (("cpu_5_min", "cpu5Min", "cpu_percent", "cpuPct"), None),
    "cpu usage": (("cpu_percent", "cpuPct"), None),
}

_STATUS_FIELDS: dict[str, tuple[str, ...]] = {
    "zigbee": ("zigbee_status", "zigbeeStatus"),
    "z wave": ("zwave_status", "zwaveStatus"),
    "matter": ("matter_status", "matterStatus"),
    "switch": ("switch",),
    "contact": ("contact",),
    "motion": ("motion",),
    "presence": ("presence",),
    "internet access": ("internetAccess", "internet_access"),
}
_DEVICE_STATE = re.compile(r"(?i)\b(on|off)\b")
_DEVICE_LEVEL = re.compile(r"(?i)\b(?:level|brightness|at)\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*%")


def _norm(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _nonnull(v: Any) -> bool:
    return v is not None and v != "" and v != "null"


def _typed_sources(evidence: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Only independently typed, successful, nonmutating, scoped snapshots.

    Different real device IDs remain distinct. Repeated receipts for one ID
    are not silently merged: incompatible source times could otherwise
    manufacture a fictitious current state.
    """
    candidates: list[dict[str, Any]] = []
    for row in evidence:
        if not isinstance(row, Mapping):
            continue
        if (row.get("success") is not True or row.get("mutates") is not False
                or row.get("effect") != "read"
                or row.get("supports_live_claim") is not True):
            continue
        details = row.get("details")
        if not isinstance(details, Mapping):
            continue
        general = details.get("reported")
        if (details.get("sourceScopeMatched") is True
                and isinstance(general, Mapping)
                and str(details.get("sourceType") or "").strip()):
            candidates.append({
                "identity": f"source:{details['sourceType']}",
                "label": str(details.get("sourceType") or ""),
                "facts": dict(general),
                "kind": "summary",
            })
        state = details.get("reportedDeviceState")
        if isinstance(state, Mapping):
            attributes = state.get("reportedAttributes")
            device_id = state.get("deviceId")
            if not isinstance(attributes, Mapping) or not _nonnull(device_id):
                continue
            if str(state.get("source") or "") not in {
                "verified-resolved-device-hubitat-state",
                "targeted-hubitat-device-state",
            }:
                continue
            candidates.append({
                "identity": f"device:{device_id}",
                "label": str(state.get("label") or ""),
                "facts": dict(attributes),
                "kind": "device",
            })
    return candidates


def _field(facts: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        name_norm = _norm(name).replace(" ", "")
        for actual, value in facts.items():
            if _norm(actual).replace(" ", "") == name_norm and _nonnull(value):
                return value
    return None


def _numeric_claim(raw: str, source: Sequence[Any]) -> bool:
    """Only exact numeric attributes, never a remembered or computed value."""
    found = []
    for match in _NUM.finditer(raw):
        try:
            found.append(float(match.group()))
        except ValueError:
            return False
    if not found:
        return False
    expected = []
    for value in source:
        if value is None or isinstance(value, bool):
            continue
        try:
            expected.append(float(value))
        except (TypeError, ValueError):
            continue
    return bool(expected) and len(found) <= len(expected) and all(
        any(abs(n - s) <= 0.02 for s in expected) for n in found
    )


def _specific_source(label: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    norm = _norm(label)
    devices = [r for r in candidates if r["kind"] == "device" and _norm(r["label"]) == norm]
    if devices:
        ids = {r["identity"] for r in devices}
        if len(ids) != 1:
            return None
        # Prefer the full verified resolution receipt over a thin lookup.
        return max(devices, key=lambda r: len(r["facts"]))
    identities = {r["identity"] for r in candidates}
    if len(identities) == 1:
        return max(candidates, key=lambda r: len(r["facts"]))
    return None


def _metric_claim(label: str, raw: str, facts: Mapping[str, Any]) -> tuple[str | None, str | None]:
    key = _norm(label)
    if key not in _FIELDS:
        return None, None
    aliases, unit_key = _FIELDS[key]
    # Explicit unit fields are metadata. A unit never attests a measurement.
    aliases = tuple(x for x in aliases if not x.endswith("_unit"))
    values = [_field(facts, (name,)) for name in aliases]
    observed = [x for x in values if _nonnull(x)]
    issue = key.replace(" ", "_").replace("(", "").replace(")", "")
    if not observed:
        return "not reported in the checked source", f"{issue}_not_reported"
    # Duplicate alias projection of a single measure is not a second source.
    distinct: list[Any] = []
    for v in observed:
        if str(v) not in [str(x) for x in distinct]:
            distinct.append(v)
    units = _field(facts, (unit_key,)) if unit_key else None
    # CPU is a paired load/percentage, whose source includes typed percent.
    if key.startswith("cpu"):
        is_15 = "15 min" in key
        if key == "cpu usage":
            load, pct = None, _field(facts, ("cpu_percent", "cpuPct"))
        else:
            load = _field(facts, ("cpu_15_min", "cpu15Min") if is_15 else ("cpu_5_min", "cpu5Min"))
            pct = _field(facts, ("cpu_15_percent", "cpu15Pct") if is_15 else ("cpu_percent", "cpuPct"))
        available = [v for v in (load, pct) if _nonnull(v)]
        if _numeric_claim(raw, available):
            return None, None
        if load is not None and pct is not None:
            return f"{load} / {pct}% (source-reported)", f"{issue}_source_mismatch"
        return " / ".join(str(x) for x in available) + " (source-reported)", f"{issue}_source_mismatch"
    if _numeric_claim(raw, distinct) and (
        not _nonnull(units) or str(units).casefold() in raw.casefold()
    ):
        return None, None
    return f"{distinct[0]} {units or '(unit unverified)'} (source-reported)", f"{issue}_source_mismatch"


def _status_claim(label: str, raw: str, facts: Mapping[str, Any]) -> tuple[str | None, str | None]:
    key = _norm(label)
    if key not in _STATUS_FIELDS:
        return None, None
    reported = _field(facts, _STATUS_FIELDS[key])
    if not _nonnull(reported):
        return "not reported in the checked source", f"{key.replace(' ', '_')}_not_reported"
    actual, claim = str(reported).casefold(), raw.casefold()
    if key == "zigbee" and actual == "enabled" and "online" in claim:
        healthy = _field(facts, ("zigbee_healthy", "zbHealthy"))
        extra = f" (source-reported healthy={healthy})" if _nonnull(healthy) else ""
        return f"enabled{extra}", "radio_enabled_not_online"
    if actual not in claim or ("online" in claim and actual != "online"):
        return f"{reported} (source-reported)", f"{key.replace(' ', '_')}_source_mismatch"
    return None, None


def _device_status_claim(raw: str, facts: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Handle identity-labelled one-line device state/brightness summaries."""
    switch = _field(facts, ("switch",))
    level = _field(facts, ("level", "brightness"))
    claimed_switch = _DEVICE_STATE.search(raw)
    claimed_level = _DEVICE_LEVEL.search(raw)
    if claimed_switch is None and claimed_level is None:
        return None, None
    invalid = (
        claimed_switch is not None and (
            not _nonnull(switch) or claimed_switch.group(1).casefold() != str(switch).casefold()
        )
        or claimed_level is not None and (
            not _nonnull(level) or not _numeric_claim(claimed_level.group(1), [level])
        )
    )
    if not invalid:
        return None, None
    supported: list[str] = []
    if _nonnull(switch):
        supported.append(f"switch {switch}")
    else:
        supported.append("switch not reported")
    if _nonnull(level):
        supported.append(f"saved level {level}%")
    else:
        supported.append("level not reported")
    return ", ".join(supported) + " (source-reported)", "device_state_source_mismatch"


def _global_claims(message: str, candidates: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Qualify whole-system completeness claims without assuming no alerts."""
    if not candidates:
        return message, []
    issues: list[str] = []
    # Completeness cannot be inferred from one driver snapshot or a status
    # boolean. This rule applies to ANY typed report, not only Hub Info.
    out, changed = _HEALTH.subn(
        "Reported source fields do not establish complete system health "
        "or the absence of alerts.",
        message,
    )
    if changed:
        issues.append("unverified_global_health")
    def alert_rewrite(match: re.Match[str]) -> str:
        return "complete alert absence is unverified"
    out, changed = _NO_ALERTS.subn(alert_rewrite, out)
    if changed:
        issues.append("unverified_alert_absence")
    # A version match is not an independently fresh update-server check.
    if _FIRMWARE.search(out):
        if len({r["identity"] for r in candidates}) == 1:
            facts = max(candidates, key=lambda r: len(r["facts"]))["facts"]
            installed = _field(facts, ("installed_firmware", "firmwareVersionString", "firmwareVersion"))
            available = _field(facts, ("available_firmware", "hubUpdateVersion"))
            if _nonnull(installed) and _nonnull(available):
                relationship = "matches" if str(installed) == str(available) else "differs from"
                replacement = (
                    f"Firmware {installed} {relationship} source-reported available "
                    f"version {available}; external update freshness unverified"
                )
            elif _nonnull(installed):
                replacement = f"Firmware {installed} (source-reported); latest version unverified"
            else:
                replacement = "Firmware freshness not established by the checked source"
            out, changed = _FIRMWARE.subn(replacement, out)
            if changed:
                issues.append("firmware_external_freshness_unverified")
    return out, issues


def guard_typed_status_claims(
    message: str, evidence: Sequence[Mapping[str, Any]],
) -> tuple[str, list[str]]:
    """Compare checkable final prose claims to CURRENT-TURN typed source fields.

    Multiple source identities are never merged for one unlabeled measurement.
    Without a usable typed read, this guard abstains rather than inferring
    unknown fields, changing unrelated answers, or asking for more tools.
    """
    original = str(message or "")
    sources = _typed_sources(evidence)
    if not sources or not original.strip():
        return original, []
    issues: list[str] = []
    lines = []
    for line in original.splitlines(keepends=True):
        match = _LINE.match(line)
        if not match:
            lines.append(line)
            continue
        label, value = match.group("label"), match.group("value")
        selected = _specific_source(label, sources)
        if selected is None:
            lines.append(line)
            continue
        if selected["kind"] == "device" and _norm(label) == _norm(selected["label"]):
            replacement, reason = _device_status_claim(value, selected["facts"])
        else:
            replacement, reason = _metric_claim(label, value, selected["facts"])
            if reason is None:
                replacement, reason = _status_claim(label, value, selected["facts"])
        if replacement is not None and reason is not None:
            # Preserve the natural answer and the source's existing Markdown
            # structure, including **bold label** and original line breaks.
            lines.append(
                match.group("prefix") + (match.group("bold") or "")
                + label + (match.group("close") or "") + ": "
                + replacement + match.group("newline")
            )
            issues.append(reason)
        else:
            lines.append(line)
    output, global_issues = _global_claims("".join(lines), sources)
    issues.extend(global_issues)
    if _TEMP_PROSE.search(output) and len({s["identity"] for s in sources}) == 1:
        facts = max(sources, key=lambda r: len(r["facts"]))["facts"]
        if not _nonnull(_field(facts, ("temperature", "temperatureC", "temperatureF"))):
            output, n = _TEMP_PROSE.subn(
                "temperature not reported in the checked source", output
            )
            if n:
                issues.append("temperature_not_reported")
    return output, list(dict.fromkeys(issues))


__all__ = ["guard_typed_status_claims"]
