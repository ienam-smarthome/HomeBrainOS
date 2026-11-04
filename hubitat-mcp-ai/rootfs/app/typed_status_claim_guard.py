"""Field-grounded status claim reconciliation for typed read-only snapshots.

A successful tool call cannot establish fields it did not report. Preserve
model-authored prose and correct only explicit, source-contradicting claims.
No model calls, live reads, device-specific values or physical mutations.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

_STRONG_HEALTH = re.compile(
    r"(?i)\b(?:the\s+)?(?:hub|system)\s+"
    r"(?:is|remains|appears)\s+(?:fully\s+|completely\s+)?"
    r"(?:healthy|fine|normal|in\s+perfect\s+health)"
)
_NO_ALERTS = re.compile(
    r"(?i)\b(?:no\s+(?:active\s+)?(?:alerts?|warnings?|errors?)"
    r"|(?:without|has\s+no)\s+(?:any\s+)?(?:active\s+)?alerts?)\b"
)
_FIRMWARE_SENTENCE = re.compile(
    r"(?i)\b(?:hub\s+)?firmware(?:\s+(?:version|v))?\s*"
    r"(?P<version>\d+(?:\.\d+){2,})?"
    r"\s+(?:is\s+)?(?:up[- ]to[- ]date|current|latest)\b"
)
_TEMPERATURE_PHRASE = re.compile(
    r"(?i)\b(?:hub\s+)?temperature\s*(?:is|was|:)\s*"
    r"[-+]?\d+(?:\.\d+)?\s*(?:°|degrees?\s*)?[CF]\b"
)
_BULLET_LABEL = re.compile(
    r"(?i)^(?P<prefix>\s*(?:[-*•]\s*)?(?:\*\*)?)"
    r"(?P<label>CPU(?:\s+load|\s+usage)?(?:\s*\([^)]*\))?"
    r"|free\s+memory|temperature|temp|database(?:\s+size)?"
    r"|zigbee|z[- ]?wave|matter|hub\s+alerts?|alerts?)"
    r"(?P<sep>(?:\*\*)?\s*:\s*(?:\*\*)?|:\s*(?:\*\*)?)"
    r"(?P<value>.+?)(?P<end>\r?\n?)$"
)
_NUMBER = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?(?![A-Za-z0-9])")
_VERSION = re.compile(r"\b\d+(?:\.\d+){2,}\b")


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _status_snapshot(evidence: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Use only source-typed, successful, nonmutating, scope-matched reads."""
    for row in reversed(evidence):
        if not isinstance(row, Mapping):
            continue
        if (row.get("success") is not True or row.get("mutates") is True
                or row.get("effect") != "read"
                or row.get("evidence_kind") != "authoritative_hub_info_snapshot"):
            continue
        details = row.get("details")
        if not isinstance(details, Mapping) or details.get("sourceScopeMatched") is not True:
            continue
        if details.get("sourceType") != "hub_information_driver":
            continue
        reported = details.get("reported")
        if isinstance(reported, Mapping):
            return dict(reported)
    return None


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _same_numerics(claim: str, expected: list[Any]) -> bool:
    """Values, not prose/units, must derive from the exact reported fields."""
    found = [float(m.group()) for m in _NUMBER.finditer(claim)]
    if not found:
        return False
    actual = []
    for entry in expected:
        if not _has_value(entry):
            return False
        try:
            actual.append(float(entry))
        except (TypeError, ValueError):
            return False
    # Accept a shorter projection (e.g. CPU load without CPU percentage),
    # but never endorse additional unexplained numerical assertions.
    return bool(actual) and len(found) <= len(actual) and all(
        any(abs(value - source) <= 0.02 for source in actual)
        for value in found
    )


def _claimed_value(label: str, value: str, reported: Mapping[str, Any]
                   ) -> tuple[str | None, str | None]:
    """Return a replacement value only for demonstrably invalid assertions."""
    norm = label.casefold().replace("-", "").replace(" ", "")
    if norm in {"temperature", "temp"}:
        measured = reported.get("temperature")
        if not _has_value(measured):
            return "not reported in the checked Hub Info snapshot", "temperature_missing"
        unit = reported.get("temperature_unit") or "unit not reported"
        if not _same_numerics(value, [measured]) or str(unit) not in value:
            return f"{_scalar(measured)} {unit} (driver-reported)", "temperature_mismatch"
        return None, None
    if norm == "freememory":
        measured = reported.get("free_memory")
        unit = reported.get("free_memory_unit")
        if not _has_value(measured):
            return "not reported in the checked Hub Info snapshot", "free_memory_missing"
        if not _same_numerics(value, [measured]) or (
            _has_value(unit) and str(unit).casefold() not in value.casefold()
        ):
            return f"{_scalar(measured)} {unit or '(unit unverified)'} (driver-reported)", "free_memory_mismatch"
        return None, None
    if norm.startswith("cpu"):
        is_15 = "15" in label
        load_key, pct_key = (
            ("cpu_15_min", "cpu_15_percent") if is_15 else
            ("cpu_5_min", "cpu_percent")
        )
        load, percent = reported.get(load_key), reported.get(pct_key)
        if not _has_value(load) and not _has_value(percent):
            return "not reported in the checked Hub Info snapshot", "cpu_missing"
        values = [v for v in (load, percent) if _has_value(v)]
        if not _same_numerics(value, values):
            body = " / ".join(
                [str(load)] if _has_value(load) else []
            )
            if _has_value(percent):
                body += (" / " if body else "") + str(percent) + "%"
            return body + " (driver-reported)", "cpu_mismatch"
        return None, None
    if norm in {"database", "databasesize"}:
        measured = reported.get("database_size")
        unit = reported.get("database_size_unit")
        if not _has_value(measured):
            return "not reported in the checked Hub Info snapshot", "database_missing"
        if not _same_numerics(value, [measured]) or (
            _has_value(unit) and str(unit).casefold() not in value.casefold()
        ):
            return f"{_scalar(measured)} {unit or '(unit unverified)'} (driver-reported)", "database_mismatch"
        return None, None
    if norm in {"zigbee", "zwave", "matter"}:
        key = {
            "zigbee": "zigbee_status",
            "zwave": "zwave_status",
            "matter": "matter_status",
        }[norm]
        source = reported.get(key)
        if not _has_value(source):
            return "status not reported in the checked Hub Info snapshot", f"{norm}_missing"
        raw = str(source).casefold()
        claim = value.casefold()
        # healthy=true does NOT mean independent physical online proof.
        if norm == "zigbee" and raw == "enabled":
            healthy = str(reported.get("zigbee_healthy") or "").casefold()
            valid = "enabled" in claim and "online" not in claim
            if not valid:
                status = "enabled"
                if healthy in {"true", "false"}:
                    status += f" (driver-reported healthy={healthy})"
                return status, "zigbee_online_overclaim"
            return None, None
        if raw not in claim or ("online" in claim and raw != "online"):
            return str(source) + " (driver-reported)", f"{norm}_status_mismatch"
        return None, None
    if norm in {"alerts", "hubalerts"}:
        source = reported.get("hub_alerts")
        if not _has_value(source):
            return "not reported in the checked Hub Info snapshot", "alerts_missing"
        if _NO_ALERTS.search(value):
            return f"{source} (driver-reported; completeness unverified)", "alert_absence_scope"
    return None, None


def guard_typed_status_claims(
    message: str,
    evidence: Sequence[Mapping[str, Any]],
) -> tuple[str, list[str]]:
    """Retain model wording, calibrating only claims contradicted by typed fields.

    Neither a successful source read nor a refresh command proves full hub
    health, alert absence, firmware freshness or physical connectivity.
    """
    original = str(message or "")
    reported = _status_snapshot(evidence)
    if reported is None or not original.strip():
        return original, []
    corrections: list[str] = []
    parts = []
    for line in original.splitlines(keepends=True):
        match = _BULLET_LABEL.match(line)
        if not match:
            parts.append(line)
            continue
        replacement, issue = _claimed_value(
            match.group("label"), match.group("value"), reported
        )
        if issue and replacement is not None:
            # Preserve the model's formatting and surrounding answer, never
            # fabricate an entire report from a partially observed source.
            parts.append(
                f"{match.group('prefix')}{match.group('label')}"
                f"{match.group('sep')}{replacement}{match.group('end')}"
            )
            corrections.append(issue)
        else:
            parts.append(line)
    corrected = "".join(parts)

    # A complete, independent absence-of-alerts check was not performed by
    # this driver, including when it reports an empty saved alert string.
    if _STRONG_HEALTH.search(corrected) or _NO_ALERTS.search(corrected):
        pattern = re.compile(
            r"(?im)(?:^|(?<=\s))(?:(?:The|This)\s+)?"
            r"(?:hub|system)\s+(?:is|remains|appears)\s+"
            r"(?:fully\s+|completely\s+)?"
            r"(?:healthy|fine|normal|in\s+perfect\s+health)"
            r"(?:\s+with\s+no\s+(?:active\s+)?alerts?)?\.?"
        )
        revised, num = pattern.subn(
            "Hub Info provides reported resource and subsystem states, "
            "not an independent full-health or alert audit.",
            corrected,
        )
        if num:
            corrected = revised
            corrections.append("hub_health_absence_overclaim")
        def qualified_alert(m: re.Match[str]) -> str:
            if _has_value(reported.get("hub_alerts")):
                return "the driver reports no alerts (completeness unverified)"
            return "alert absence was not verified"
        corrected, changed = _NO_ALERTS.subn(qualified_alert, corrected)
        if changed:
            corrections.append("alert_absence_unverified")

    if _FIRMWARE_SENTENCE.search(corrected):
        installed = reported.get("installed_firmware")
        available = reported.get("available_firmware")
        def qualified_firmware(m: re.Match[str]) -> str:
            if not _has_value(installed):
                return "Firmware version was not reported in the checked snapshot"
            if _has_value(available):
                relation = (
                    "matches" if str(installed) == str(available) else
                    "differs from"
                )
                return (
                    f"Hub firmware {_scalar(installed)} {relation} the "
                    f"driver-reported available version {_scalar(available)}; "
                    "external update freshness is unverified"
                )
            return (
                f"Hub firmware {_scalar(installed)} (driver-reported); "
                "available update version not verified"
            )
        corrected, changed = _FIRMWARE_SENTENCE.subn(qualified_firmware, corrected)
        if changed:
            corrections.append("firmware_external_freshness_unverified")

    if not _has_value(reported.get("temperature")):
        corrected, changed = _TEMPERATURE_PHRASE.subn(
            "temperature was not reported in the checked Hub Info snapshot",
            corrected,
        )
        if changed:
            corrections.append("temperature_missing")
    # Only issue labels leave this boundary; never publish the raw snapshot,
    # device IDs, private tool arguments, or an inferred physical health state.
    return corrected, list(dict.fromkeys(corrections))


__all__ = ["guard_typed_status_claims"]
