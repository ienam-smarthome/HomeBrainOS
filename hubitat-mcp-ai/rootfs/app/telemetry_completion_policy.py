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
        or summary.get("truncated") is True
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
    return has_scoped_log and (has_discriminator or high_information_checkpoint_offered)


__all__ = ["ready_for_bounded_telemetry_answer", "single_target_telemetry_scope"]
