"""Bound direct device-status claims to same-turn reported Hubitat attributes.

This is a narrow read-contract audit, NOT a generic replacement for causal
investigations. When the *only* successful sources are one targeted device
lookup and its resolver, the final status answer cannot supply measurements
the lookup receipt did not report. Another successful source disables this
guard rather than hiding potentially legitimate history or sensor evidence.
"""
from __future__ import annotations

import re
from typing import Any


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


_ATTRIBUTE_ALIASES = {
    "temperature": ("temperature", "temperaturec"),
    "setpoint": ("heatingsetpoint", "thermostatsetpoint", "setpoint", "targettemperature"),
    "power": ("power", "activepower", "powermeter"),
    "humidity": ("humidity", "relativehumidity"),
    "mode": ("thermostatmode", "mode"),
    "level": ("level", "brightness", "dimmerlevel"),
    "switch": ("switch",),
    "operatingstate": ("thermostatoperatingstate", "operatingstate", "heatingstate"),
}
_LABEL_VALUE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
    r"(temperature|setpoint|power|humidity|mode|operating\s+state)"
    r"\s*:?\s*(?:\*\*)?\s*:?\s*(?:\*\*)?\s*([^\n]{1,80})$"
)
_WATTS = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:W|watts)\b", re.I)
_CELSIUS = re.compile(r"(?<!\w)(-?\d+(?:\.\d+)?)\s*°\s*C\b", re.I)
# Natural-language inline brightness is still a CURRENT measurement claim.
# E.g. "currently on with a brightness level of 30%" previously escaped
# the heading-only numeric guard when the only source reported switch=on.
_INLINE_LEVEL = re.compile(
    r"(?i)\\b(?:brightness(?:\\s+level)?|dimmer\\s+level)\\s+"
    r"(?:of\\s+|is\\s+|at\\s+|to\\s+)?(?:\\*\\*)?"
    r"(\\d{1,3}(?:\\.\\d+)?)\\s*%?"
)



def _recorded_value(attributes: dict[str, Any], name: str) -> Any:
    wanted = _ATTRIBUTE_ALIASES.get(_norm(name), ())
    for key, value in attributes.items():
        if _norm(key) in wanted and value not in (None, ""):
            return value
    return None


def _same_measurement(claim: str, measured: Any) -> bool:
    """Compare scalar readings conservatively, never fabricate conversions."""
    if measured is None:
        return False
    raw_claim = str(claim).replace("**", "").strip().strip(".")
    raw_source = str(measured).strip()
    number = re.search(r"[-+]?\d+(?:\.\d+)?", raw_claim)
    source_number = re.search(r"[-+]?\d+(?:\.\d+)?", raw_source)
    if number is not None and source_number is not None:
        return abs(float(number.group()) - float(source_number.group())) < 0.00001
    return _norm(raw_claim) == _norm(raw_source)


def _targeted_snapshot(
    evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    snapshots: list[dict[str, Any]] = []
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("evidence_kind") == "targeted_device_lookup":
            details = row.get("details")
            state = details.get("reportedDeviceState") if isinstance(details, dict) else None
            if isinstance(state, dict) and isinstance(state.get("reportedAttributes"), dict):
                snapshots.append(state)
        elif row.get("evidence_kind") != "deterministic_targeted_device_resolution":
            # Non-lookup reads can independently support other measurements.
            return None
    if len(snapshots) != 1:
        return None
    snap = snapshots[0]
    if not str(snap.get("deviceId") or "").isdigit() or not str(snap.get("label") or "").strip():
        return None
    return snap


def _unsupported_current_claims(message: str, attrs: dict[str, Any]) -> list[str]:
    unknown: list[str] = []
    for match in _LABEL_VALUE.finditer(message):
        field, claim = match.group(1), match.group(2)
        # Strip markdown value formatting, not units.
        claim = claim.replace("**", "").strip()
        reference = _recorded_value(attrs, field)
        if not _same_measurement(claim, reference):
            unknown.append(_norm(field))
    for match in _INLINE_LEVEL.finditer(message):
        if not _same_measurement(match.group(1), _recorded_value(attrs, "level")):
            unknown.append("level")
    for match in _WATTS.finditer(message):
        if not _same_measurement(match.group(1), _recorded_value(attrs, "power")):
            unknown.append("power")
    for match in _CELSIUS.finditer(message):
        if not any(_same_measurement(match.group(1), _recorded_value(attrs, name))
                   for name in ("temperature", "setpoint")):
            unknown.append("temperature")
    return list(dict.fromkeys(unknown))


def ground_current_device_status(
    message: str,
    evidence: list[dict[str, Any]],
    request_class: str,
) -> tuple[str, list[str]]:
    """Keep unsubstantiated numeric/status details out of simple live snapshots.

    The evidence's typed source values replace an unsupported draft; do not
    change evidence, outcomes, Hubitat devices or any model/tool permissions.
    """
    if request_class != "live-read":
        return message, []
    snap = _targeted_snapshot(evidence)
    if snap is None:
        return message, []
    label = str(snap["label"])
    if not re.search(r"(?<![\w-])" + re.escape(label) + r"(?![\w-])",
                     message, re.I):
        return message, []
    # These are status summaries, never historical cause/execution questions.
    if not re.search(r"(?i)\b(?:currently|current status|last reported|status was|reports?)\b", message):
        return message, []
    attrs = snap["reportedAttributes"]
    unknown = _unsupported_current_claims(message, attrs)
    if not unknown:
        return message, []

    selected = []
    for source_key, label_key in (
        ("healthStatus", "Health"), ("switch", "Switch"),
        ("mqttStatus", "MQTT"), ("lastSeen", "Last seen"),
        ("temperature", "Temperature"), ("heatingSetpoint", "Setpoint"),
        ("thermostatSetpoint", "Setpoint"), ("thermostatMode", "Mode"),
        ("thermostatOperatingState", "Operating state"), ("power", "Power"),
        ("level", "Brightness"),
    ):
        value = attrs.get(source_key)
        if value not in (None, ""):
            if label_key in {x[0] for x in selected}:
                continue
            selected.append((label_key, str(value).strip()[:110]))
    lines = [
        f"**{label} (device {snap['deviceId']}) — recorded Hubitat state:**",
        *(f"- **{key}:** {value}" for key, value in selected),
        "Measurements not present in the successful current device read "
        "have been omitted; a retained reading or 'connected' attribute "
        "is not independent proof that an offline device is physically online.",
    ]
    return "\n".join(lines), unknown


__all__ = ["ground_current_device_status"]
