"""Bounded evidence-depth checkpoint for a single-device connectivity incident.

This is NOT an automatic tool plan: the model remains responsible for
selecting relevant registered read tools and interpreting their results.
It prevents state/history/log receipts alone from being treated as a
complete root-cause investigation of an offline/MQTT/telemetry problem.
"""
from __future__ import annotations

import re
from typing import Any

_CONNECTIVITY = re.compile(
    r"(?i)\b(?:offline|stale|unreachable|not\s+responding|"
    r"no\s+(?:data|telemetry)|mqtt|lastseen|last\s+seen|watchdog|"
    r"connectivity|disconnected)\b"
)
_INVESTIGATE = re.compile(
    r"(?i)\b(?:why|investigat\w*|diagnos\w*|root[- ]cause|"
    r"troubleshoot|what\s+caused|explain\s+(?:the\s+)?cause)\b"
)
_SINGLE_DEVICE = re.compile(
    r"(?i)\bdevice\s*(?:id\s*)?[:#]?\s*[1-9]\d{2,8}\b"
    r"|\b(?:bedroom|livingroom|bathroom|hallway|kitchen|"
    r"plug|socket|mesh)\b"
)


def is_connectivity_root_cause_request(request: str) -> bool:
    """Recognise an incident goal, not an explicit ON/OFF event reconstruction."""
    request = str(request or "")
    return bool(
        _INVESTIGATE.search(request)
        and _CONNECTIVITY.search(request)
        and _SINGLE_DEVICE.search(request)
        and not re.search(
            r"(?i)\b(?:all|entire|whole)\s+(?:my\s+)?"
            r"(?:hubitat\s+)?(?:system|hub|devices)\b",
            request,
        )
    )


def _leaf(receipt: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    args = receipt.get("arguments") or {}
    if not isinstance(args, dict):
        return "", {}
    operation = args.get("tool") or receipt.get("sub_tool") or ""
    inner = args.get("args") or args
    return str(operation), inner if isinstance(inner, dict) else {}


def device_incident_followup(
    request: str,
    evidence: list[dict[str, Any]],
) -> str | None:
    """One model-facing read-only follow-up after scoped baseline evidence.

    Never equate 'not checked' to an available or required tool; ask the
    model to discover supported operations and report precise blockers.
    """
    if not is_connectivity_root_cause_request(request):
        return None
    state, history, logs = False, False, False
    driver_read = False
    automation_read = False
    upstream_read = False
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is True or row.get("effect") == "write":
            continue
        operation, args = _leaf(row)
        kind = str(row.get("evidence_kind") or "")
        if operation in {"hub_list_devices", "hub_get_device"} or kind == "targeted_device_lookup":
            state = True
        if operation in {"hub_list_device_events", "hub_get_device_events"} or kind in {
            "deterministic_device_event_history", "authoritative_device_event_history",
        }:
            history = True
        if operation == "hub_get_logs" and args.get("deviceId") is not None:
            logs = True
        if operation == "hub_get_source" and str(args.get("type") or "").casefold() == "driver":
            driver_read = True
        # A whole-hub app/rule identity list is NOT verification that an
        # automation controls this particular device, its configured
        # actions, or actual execution. Only scoped app/rule receipts count.
        if operation in {"hub_get_app_config", "hub_get_rule_health"} and (
            args.get("appId") is not None
        ):
            automation_read = True
        if kind in {"physical_network_reachability", "mqtt_broker_packet_evidence",
                    "upstream_telemetry_confirmation"}:
            upstream_read = True
    if not (state and (history or logs)):
        return None
    missing = []
    if not driver_read:
        missing.append("installed driver implementation/health and MQTT freshness logic")
    if not automation_read:
        missing.append("relevant power-saving/controlling automation configuration and dated execution")
    if not upstream_read:
        missing.append("independent network, broker, or source-side last-packet evidence")
    if not missing:
        return None
    return (
        "HOST DEVICE-INCIDENT EVIDENCE DEPTH CHECK (READ ONLY)\n"
        "The device state, history and/or logs establish reported symptoms, "
        "but do not complete this root-cause investigation. Additional "
        "discriminators have not been verified: "
        + "; ".join(missing) + ".\n"
        "Choose the ONE or TWO highest-information, available MCP READ tools "
        "to distinguish a stale driver clock/health watchdog from an actual "
        "plug, network or controller fault. For driver code, verify its installed "
        "driver code ID before hub_get_source(type=driver); app or device source "
        "is not interchangeable. For an automation claim, verify device targeting "
        "and read the actual app/rule configuration plus dated execution evidence. "
        "For an upstream network or broker claim, check whether a genuinely "
        "independent read tool exists. Never invent a ping/MQTT-broker gateway "
        "or perform a write to test connectivity.\n"
        "Do not repeat the current 24-hour events or log read solely to restate "
        "the status. If no relevant registered source is available, explain "
        "that precise gap rather than asserting a root cause. Only one "
        "additional tool-selection opportunity is granted here."
    )


__all__ = ["is_connectivity_root_cause_request", "device_incident_followup"]
