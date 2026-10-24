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
    from ai_investigation_routing import active_request_interpretation
    interpreted = active_request_interpretation(request)
    if interpreted is not None and interpreted.objective is not None:
        return interpreted.objective == "device_connectivity"
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
        "First compare *different clocks and temporal anchors* rather than "
        "taking a reported age as a physical packet timestamp. When logs say "
        "'after N seconds without data', calculate log time minus N and compare "
        "the result across warnings and same-device event times. Coincidence "
        "is a timer reference clue, NOT proof of a physical last packet. "
        "Then choose the highest-information registered MCP READ sources to "
        "test competing explanations. Verify the installed driver code ID and "
        "trace the relevant timestamp writes/reads, watchdog transitions and "
        "connection callbacks in source before asserting their behaviour; "
        "app-source workbenches take installed app IDs, not driver code IDs. "
        "A driver source read alone does not demonstrate method behaviour. "
        "Inspect actual controlling automation/device-dependent references "
        "and dated execution when relevant, not a generic list of all apps. "
        "For upstream network or broker claims, use only genuinely independent "
        "tools and retain actual return values. Never invent transport "
        "evidence or perform a write to test connectivity.\n"
        "Do not repeat the current 24-hour events or log read solely to restate "
        "the status. If no relevant registered source is available, explain "
        "that precise gap rather than asserting a root cause. Only one "
        "additional tool-selection opportunity is granted here."
    )



CONNECTIVITY_EVIDENCE_PLAN = """
READ-ONLY CONNECTIVITY INCIDENT: The user's objective is to distinguish the
reported MQTT session flag from physical or device-originated telemetry. Start
with the identified device and bounded events/logs; do not scan whole hub.
When those show missing data or a watchdog counter, prioritise the installed
driver's timestamp/parse/connection/watchdog method logic and the actual
device-dependent automation links/settings. The authoritative driver CODE ID
is not necessarily an installed APP ID. Use a read-only driver source reader
with a live verified code-ID mapping, not the installed-app source workbench.
Checking app names or app logs is not equivalent to checking the installed
controller's stored configuration or dated execution; a zero-row log window
does not exclude execution. Cross-check temporal anchors and distinguish
driver-generated health changes from genuine physical packets. Decide which
registered tool has the highest information value; never guess a schema,
read unrelated devices, use write commands, or assert source/method/physical
behaviour without evidence. Explain any specific unavailable source.
"""


def incident_progress_followup(
    request: str,
    evidence: list[dict[str, Any]],
) -> str | None:
    """One bounded evidence-progress checkpoint after the initial AI follow-up.

    Only an actual same-device dependent-app read can trigger another
    source-selection opportunity. This is not a keyword-driven route or
    deterministic MCP plan, and it does not claim a missing source exists.
    An app log alone is not a verified link or current configuration.
    """
    if not is_connectivity_root_cause_request(request):
        return None
    from incident_reasoning_depth import assess_incident_reasoning_depth

    target_ids = set()
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("mutates") is True or receipt.get("effect") == "write":
            continue
        op, args = _leaf(receipt)
        if op == "hub_list_device_events":
            target = str(args.get("deviceId") or "")
            if target.isdigit():
                target_ids.add(target)
    if len(target_ids) != 1:
        return None
    target = next(iter(target_ids))
    depth = assess_incident_reasoning_depth(evidence, target)
    # Only recover from a meaningful new lead, not a generic search, log
    # retry or name-matched inventory. Avoid consuming more model rounds
    # when no specific target-dependent candidate has been investigated.
    if not depth["deviceDependentAppsChecked"]:
        return None
    missing = []
    if not depth["scopedAppConfigRead"]:
        missing.append(
            "the actual installed dependent/controlling app settings and "
            "device targeting (dependency list or empty logs alone do not "
            "verify the rule behaviour)"
        )
    if not depth["driverSourceRetrieved"] and not depth["driverSourceAttempted"]:
        missing.append(
            "the matched device's installed DRIVER code identity and "
            "read-only source (not an app-instance source reader)"
        )
    if not missing:
        return None
    return (
        "HOST INVESTIGATION FOLLOW-THROUGH (READ ONLY, ONE CHANCE)\\n"
        "Device " + target + " has a successful targeted dependency lookup, "
        "but the original root-cause question remains unanswered. "
        "Incomplete discriminators: " + "; ".join(missing) + ". "
        "Choose the most decisive available LIVE MCP read operation, using "
        "the identity and actual returned dependency metadata, rather than "
        "listing all apps or repeating device history. If a dependent app ID "
        "has been established by the returned results, inspect its actual "
        "configuration and dated relevant execution; if the mapped driver "
        "source is available, inspect watchdog/connection timestamp branches. "
        "Treat any earlier app log with zero entries only as checked-empty, "
        "never as evidence that a control rule did not run. If no specific "
        "read tool can establish the missing observation, finalise with that "
        "precise gap. Never issue a write or assume evidence exists."
    )


__all__ = [
    "is_connectivity_root_cause_request", "device_incident_followup",
    "incident_progress_followup", "CONNECTIVITY_EVIDENCE_PLAN",
]
