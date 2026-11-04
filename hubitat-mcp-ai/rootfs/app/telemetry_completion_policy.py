"""Evidence-saturation stop for single-target read-only status investigations.

The loop has several independent retry subsystems. When a verified target
has status, bounded history and target-scoped logs, and either a relevant
additional source has been inspected or one high-information checkpoint
was offered, another generic retry is unlikely to resolve an unobserved
physical cause. Stop tool discovery and use existing no-tools synthesis.

The policy does not certify device liveness, completeness, or causal
attribution, and does not run for lighting, heating, multi-target questions,
source-code review or write requests. Explicit whole-home comparisons are
preserved. Missing source classes still permit investigation.
"""
from __future__ import annotations

import re
from typing import Any

from typed_device_history_evidence import normalize_target_device_history
from telemetry_clock_consistency import assess_telemetry_clock_consistency

_WIDE = re.compile(
    r"(?i)\b(?:compare|comparison|across|whole[- ]home|whole[- ]hub|"
    r"all\s+devices|every\s+device|several\s+devices|"
    r"multiple\s+devices|system[- ]wide|hub[- ]wide)\b"
)


def single_target_telemetry_scope(request: str) -> bool:
    """Shared request-scope test for evidence-saturation and source reads."""
    return _WIDE.search(str(request or "")) is None


def _leaf(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    raw = row.get("arguments")
    if not isinstance(raw, dict):
        return "", {}
    args = raw.get("args") if isinstance(raw.get("args"), dict) else raw
    return str(raw.get("tool") or row.get("sub_tool") or ""), args


def ready_for_bounded_telemetry_answer(
    request: str,
    evidence: list[dict[str, Any]],
    *,
    domain: str | None,
    high_information_checkpoint_offered: bool = False,
) -> bool:
    """Positive proof of a bounded *answer opportunity*, never a root cause."""
    if domain != "device_telemetry" or not single_target_telemetry_scope(request):
        return False
    summary = normalize_target_device_history(evidence)
    if not isinstance(summary, dict):
        return False
    target_id = str(summary.get("deviceId") or "")
    state = summary.get("reportedDeviceState")
    if not target_id.isdecimal() or not isinstance(state, dict):
        return False
    if (
        str(state.get("deviceId") or "") != target_id
        or state.get("source") != "targeted-hubitat-device-state"
    ):
        return False
    if summary.get("truncated") is True:
        # An explicitly source-count-matched, partially retained history
        # remains sufficient to *publish a bounded, unresolved answer* after
        # status, history, scoped logs and one discriminator opportunity.
        # The unobserved rows are not proof of absence or physical contact.
        # Reject all other truncated/unmatched histories rather than
        # turning a missing evidence packet into an early stop.
        retained = summary.get("returnedEvents")
        unshown = summary.get("unshownEventCount")
        total = summary.get("sourceReportedEventCount")
        if not (
            summary.get("joinedDerivedHistory") is True
            and summary.get("eventSource") == "verified-direct-derived-receipt-pair"
            and type(retained) is int and retained > 0
            and type(unshown) is int and unshown > 0
            and type(total) is int and total == retained + unshown
            and summary.get("sourceIntegrityVerified") is False
        ):
            return False
    label = str(summary.get("deviceLabel") or "").strip()
    if not label or label.casefold() not in str(request or "").casefold():
        return False
    history = summary.get("returnedEvents")
    if type(history) is not int or history < 1:
        return False

    has_scoped_log = False
    has_discriminator = False
    dependant_ids: set[str] = set()
    scoped_configs: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict) or item.get("success") is not True:
            continue
        if item.get("mutates") is True or item.get("effect") == "write":
            continue
        tool, args = _leaf(item)
        if tool == "hub_get_logs" and str(args.get("deviceId") or "") == target_id:
            has_scoped_log = True
        if tool == "hub_get_device" and str(args.get("deviceId") or "") == target_id:
            if str(args.get("mode") or "").lower() in {"configuration", "full"}:
                has_discriminator = True
        if tool == "hub_get_source" and str(args.get("type") or "").lower() == "driver":
            has_discriminator = True
        if tool == "hub_list_device_dependents" and str(args.get("deviceId") or "") == target_id:
            details = item.get("details")
            if isinstance(details, dict):
                for app in details.get("appsUsing") or []:
                    if isinstance(app, dict) and str(app.get("appId") or "").isdigit():
                        dependant_ids.add(str(app["appId"]))
        if tool == "hub_get_app_config" and str(args.get("appId") or "").isdigit():
            scoped_configs.add(str(args["appId"]))
        if item.get("evidence_kind") in {
            "physical_network_reachability", "mqtt_broker_packet_evidence",
            "upstream_telemetry_confirmation",
        }:
            has_discriminator = True
    if dependant_ids.intersection(scoped_configs):
        has_discriminator = True
    # For a question contrasting a device's offline health with its MQTT
    # status, a verified, inconsistent source clock is itself enough to
    # explain the *evidence discrepancy* provisionally. It does NOT
    # establish which driver callback, broker or hardware fault caused it.
    # Require both named statuses, a source-scoped read and actual history.
    attrs = state.get("reportedAttributes")
    clock = assess_telemetry_clock_consistency(evidence)
    bounded_status_clock_discriminator = bool(
        isinstance(attrs, dict)
        and str(attrs.get("healthStatus") or "").casefold() == "offline"
        and str(attrs.get("mqttStatus") or "").casefold() == "connected"
        and re.search(r"(?i)\\bmqtt\\b", request)
        and re.search(r"(?i)\\boffline\\b", request)
        and isinstance(clock, dict)
        and str(clock.get("deviceId") or "") == target_id
        and clock.get("sourcesAgree") is False
        and clock.get("physicalTelemetryProven") is False
    )
    return has_scoped_log and (
        has_discriminator or high_information_checkpoint_offered
        or bounded_status_clock_discriminator
    )


def ready_after_bounded_telemetry_read(
    request: str,
    evidence: list[dict[str, Any]],
    *,
    domain: str | None,
    receipt_count_before_round: int,
    had_tool_actions: bool,
    round_has_mutation: bool,
    round_tool_failure: bool,
    high_information_checkpoint_offered: bool = False,
) -> bool:
    """Reuse source sufficiency immediately after a *new* safe read result.

    Tool rounds need not end in a model no-tool response. Require at least
    one genuinely new successful read; an optional failed companion tool
    does not invalidate previously checked scoped state/history/logs. This
    is a bounded answer opportunity, not verified physical reachability or
    a completed causal investigation.
    """
    if (
        domain != "device_telemetry"
        or not had_tool_actions
        or round_has_mutation
        # An optional failed source does not erase a complete, independently
        # corroborated read set within the same round.
        or type(receipt_count_before_round) is not int
        or receipt_count_before_round < 0
        or receipt_count_before_round >= len(evidence)
    ):
        return False
    new_reads = evidence[receipt_count_before_round:]
    if not any(
        isinstance(row, dict)
        and row.get("success") is True
        and row.get("mutates") is not True
        and row.get("effect") == "read"
        for row in new_reads
    ):
        return False
    return ready_for_bounded_telemetry_answer(
        request, evidence, domain=domain,
        high_information_checkpoint_offered=high_information_checkpoint_offered,
    )


__all__ = [
    "ready_for_bounded_telemetry_answer",
    "ready_after_bounded_telemetry_read",
    "single_target_telemetry_scope",
]
