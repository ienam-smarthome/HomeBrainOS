"""Canonical, privacy-bounded source authority for model-first investigations.

Keep reported state, historical records, independently verified upstream
observations and unobserved causes in different evidence roles. This is a
general source-authority contract: it never generates a cause, trusts a model
claim as a receipt, executes a tool or grants control permissions.

The first adapter is scoped device telemetry, using existing canonical data.
Other investigative domains can provide their own adapters without adding
domain-specific sentence-replacement gates.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

from incident_reasoning_depth import assess_incident_reasoning_depth
from driver_source_identity_guard import _linked_driver_source_ids
from investigation_intelligence import plan_investigation
from typed_device_history_evidence import normalize_target_device_history
from telemetry_completion_policy import single_target_telemetry_scope


def _args(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("arguments")
    for _ in range(3):
        if not isinstance(raw, dict):
            return {}
        inner = raw.get("args")
        if not isinstance(inner, dict):
            return raw
        raw = inner
    return raw if isinstance(raw, dict) else {}


def _leaf(row: Mapping[str, Any]) -> str:
    return str(row.get("sub_tool") or (row.get("arguments") or {}).get("tool") or "")


def _match_request(request: str, normalized: Mapping[str, Any]) -> bool:
    target = str(normalized.get("deviceId") or "")
    label = str(normalized.get("deviceLabel") or "").strip()
    return bool(
        target.isdecimal() and label and
        re.search(r"(?<![\w-])" + re.escape(label) + r"(?![\w-])",
                  str(request or ""), re.I)
    )


def pending_telemetry_configuration_read(
    request: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Plan ONE identified config read when it can discriminate driver facts.

    No speculative code ID, guessed device, sibling-wide scan, second attempt
    or re-read of an already inspected configuration is permitted. The caller
    must still verify the live gateway schema and non-mutating effect.
    """
    plan = plan_investigation(request)
    if (plan is None or plan.domain != "device_telemetry"
            or not single_target_telemetry_scope(request)):
        return None
    normalized = normalize_target_device_history(receipts)
    if not isinstance(normalized, dict) or not _match_request(request, normalized):
        return None
    if (normalized.get("truncated") is True
            or normalized.get("commandCount") != 0
            or type(normalized.get("returnedEvents")) is not int
            or normalized["returnedEvents"] < 1):
        return None
    target = str(normalized["deviceId"])
    targeted_log = False
    for row in receipts:
        if not isinstance(row, dict):
            continue
        leaf, args = _leaf(row), _args(row)
        if leaf == "hub_get_device" and str(args.get("deviceId") or "") == target:
            if str(args.get("mode") or "").lower() in {"configuration", "full"}:
                return None  # prior attempt, success or failure
        if (
            row.get("success") is True
            and leaf == "hub_get_logs"
            and str(args.get("deviceId") or "") == target
        ):
            targeted_log = True
    return {"deviceId": target, "mode": "configuration"} if targeted_log else None



def pending_verified_driver_source_read(
    request: str, receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Plan one bounded read-only driver-source chunk with verified identity.

    Requires successful, uniquely linked target configuration evidence. Never
    use model-supplied IDs, driver labels, a guessed instance ID, or infer a
    positive source link from a successful configuration call alone.
    """
    plan = plan_investigation(request)
    if (plan is None or plan.domain != "device_telemetry"
            or not single_target_telemetry_scope(request)):
        return None
    normalized = normalize_target_device_history(receipts)
    if not isinstance(normalized, dict) or not _match_request(request, normalized):
        return None
    if (normalized.get("truncated") is True
            or normalized.get("commandCount") != 0):
        return None
    target = str(normalized["deviceId"])
    valid_config = any(
        isinstance(row, dict) and row.get("success") is True
        and _leaf(row) == "hub_get_device"
        and str(_args(row).get("deviceId") or "") == target
        and str(_args(row).get("mode") or "").lower() == "configuration"
        for row in receipts
    )
    if not valid_config:
        return None
    ids = _linked_driver_source_ids(receipts, target)
    if len(ids) != 1:
        return None
    code_id = next(iter(ids))
    for row in receipts:
        if isinstance(row, dict) and _leaf(row) == "hub_get_source":
            args = _args(row)
            if (str(args.get("type") or "").lower() == "driver"
                    and str(args.get("id") or "") == code_id):
                return None  # success OR failure: no repeated source read
    return {"type": "driver", "id": code_id, "offset": 0, "length": 8000}


def telemetry_source_authority(
    request: str, receipts: list[dict[str, Any]],
    *,
    clock: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Construct an attested source-role map, never an interpreted verdict."""
    normalized = normalize_target_device_history(receipts)
    if not isinstance(normalized, dict) or not _match_request(request, normalized):
        return None
    target = str(normalized["deviceId"])
    state = normalized.get("reportedDeviceState")
    if not isinstance(state, Mapping) or str(state.get("deviceId") or "") != target:
        return None
    attrs = state.get("reportedAttributes")
    if not isinstance(attrs, Mapping):
        return None
    history_count = normalized.get("returnedEvents")
    if type(history_count) is not int:
        return None
    scoped_logs = any(
        isinstance(r, dict) and r.get("success") is True
        and _leaf(r) == "hub_get_logs"
        and str(_args(r).get("deviceId") or "") == target
        for r in receipts
    )
    depth = assess_incident_reasoning_depth(receipts, target)
    current = {}
    for key in ("healthStatus", "mqttStatus", "lastSeen", "dataAgeSeconds", "switch"):
        value = attrs.get(key)
        if isinstance(value, (int, str)) and not isinstance(value, bool):
            current[key] = str(value)[:125]
    temporal = {"sourcesAgree": None, "physicalTelemetryProven": False}
    if isinstance(clock, Mapping) and str(clock.get("deviceId") or "") == target:
        temporal["sourcesAgree"] = clock.get("sourcesAgree")
        temporal["physicalTelemetryProven"] = clock.get("physicalTelemetryProven") is True
        for key in ("metadataAgeHoursAtRead", "reportedDataAgeHours"):
            value = clock.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                temporal[key] = round(value, 1)
    verified_driver_ids = _linked_driver_source_ids(receipts, target)
    linked_driver_chunks = sum(
        1 for r in receipts
        if isinstance(r, dict) and r.get("success") is True
        and _leaf(r) == "hub_get_source"
        and str(_args(r).get("type") or "").lower() == "driver"
        and str(_args(r).get("id") or "") in verified_driver_ids
        and isinstance(r.get("details"), dict)
        and r["details"].get("sourceRetrieved") is True
    )
    independent_broker_packets = any(
        isinstance(r, dict) and r.get("success") is True
        and r.get("evidence_kind") == "mqtt_broker_packet_evidence"
        and isinstance(r.get("details"), dict)
        and r["details"].get("independentObservationVerified") is True
        and str(r["details"].get("verifiedForDeviceId") or "") == target
        for r in receipts
    )
    return {
        "schema": "homebrain-source-authority.v1",
        "targetDeviceId": target,
        "source": "scoped-hubitat-receipts",
        "reportedAttributes": current,
        "historicalRowsReturned": history_count,
        "historicalRowTypes": "device-reported-and-hub-generated-mixed",
        "historicalWindowComplete": normalized.get("eventHistoryComplete") is True,
        "commandRowsReturned": normalized.get("commandCount"),
        "scopedHubitatLogsChecked": scoped_logs,
        "temporalClocks": temporal,
        "linkedDriverSourceChunkRetrieved": linked_driver_chunks > 0,
        "verifiedInstalledDriverBehaviour": depth.get("driverMethodBehaviourVerified") is True,
        "independentBrokerPacketsVerified": independent_broker_packets,
        "independentUpstreamObservationRetained": depth.get("independentUpstreamObservationRetained") is True,
        "physicalActuationAcknowledged": normalized.get("acknowledgementVerified") is True,
        "physicalCauseEstablished": False,
    }


def render_telemetry_authority(authority: Mapping[str, Any] | None) -> str | None:
    if not isinstance(authority, Mapping) or authority.get("schema") != "homebrain-source-authority.v1":
        return None
    attrs = authority.get("reportedAttributes")
    if not isinstance(attrs, Mapping):
        return None
    lines = [
        "HOST VERIFIED SOURCE AUTHORITY (facts versus missing sources)",
        "The following is derived from current-turn typed receipts, not previous "
        "model conclusions. Preserve distinct observation layers. Only "
        "describe a source's internal mechanisms when actual code/log/broker "
        "evidence was returned; a reported status attribute does not verify "
        "a physical or network cause.",
        "HUBITAT-SAVED ATTRIBUTES (not independent physical telemetry): "
        + ", ".join(f"{key}={value}" for key, value in attrs.items()),
        "BOUNDED HISTORY: "
        + str(authority.get("historicalRowsReturned"))
        + " returned mixed Hubitat event records; these can include internally "
        "generated watchdog/status reports. This does not certify a complete "
        "history or an endpoint packet.",
        "SCOPED HUBITAT LOGS QUERIED: "
        + str(authority.get("scopedHubitatLogsChecked"))
        + ". A successful log request alone is not proof of the contents "
        "of an unseen driver method, broker or physical endpoint.",
    ]
    clock = authority.get("temporalClocks")
    if isinstance(clock, Mapping) and clock.get("sourcesAgree") is False:
        lines.append(
            "CONFLICTING METADATA CLOCKS: stored lastSeen age "
            + str(clock.get("metadataAgeHoursAtRead", "unknown"))
            + " hours versus reported dataAgeSeconds age "
            + str(clock.get("reportedDataAgeHours", "unknown"))
            + " hours. Do not combine these into one proven duration of "
            "endpoint silence. Watchdog counters may track a driver timer "
            "rather than actual last physical contact."
        )
    verified = (
        ("driver source chunk linked to this device", authority.get("linkedDriverSourceChunkRetrieved")),
        ("driver implementation methods", authority.get("verifiedInstalledDriverBehaviour")),
        ("broker device-originated packets/session", authority.get("independentBrokerPacketsVerified")),
        ("independent upstream observation", authority.get("independentUpstreamObservationRetained")),
        ("physical actuation acknowledgement", authority.get("physicalActuationAcknowledged")),
        ("physical cause", authority.get("physicalCauseEstablished")),
    )
    lines.append(
        "INDEPENDENT VERIFICATION STATUS: "
        + "; ".join(name + "=" + ("verified" if found else "not verified")
                    for name, found in verified)
        + ". Do not upgrade an unchecked source into an asserted fact."
    )
    lines.append(
        "REASONING RULE: Lead with the strongest observed distinction, then "
        "explain what it does AND does not establish; explicitly separate "
        "plausible hypotheses from confirmed causes. Do not assert that "
        "a broker did/did not receive a disconnect, maintained a live session, "
        "or that a specific endpoint packet ceased at an exact timestamp "
        "unless corresponding source evidence verifies it. Recommend the "
        "highest-information next read-only discriminator."
    )
    return "\n".join(lines)


__all__ = [
    "pending_telemetry_configuration_read", "pending_verified_driver_source_read", "telemetry_source_authority",
    "render_telemetry_authority",
]
