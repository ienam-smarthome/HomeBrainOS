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
READ-ONLY CONNECTIVITY INCIDENT: Treat the reported statuses as
independent, possibly differently produced signals, not as a contradiction
resolved by repeating their values. Read available live MCP tool schemas and
choose the most discriminating checks: (1) identify the code path that sets
each reported status and the driver's telemetry/watchdog timestamps;
(2) when a suitable same-integration control group is identified, compare
the failing device with responding peers and the common broker/bridge;
(3) use genuinely READ-ONLY diagnostics to distinguish device and broker
reachability, where a matching gateway and current address are verified;
(4) inspect real device-dependent apps, their stored settings and dated
execution, and correlate event time with control time. Do not assume any
particular gateway, address, app ID or tool is available. Prioritise the
highest-information read next. Start with the identified device and bounded
events/logs; do not scan the whole hub.
When those show missing data or a watchdog counter, prioritise the installed
driver's timestamp/parse/connection/watchdog method logic and the actual
device-dependent automation links/settings. The authoritative DRIVER code ID
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



def evidence_progress_checkpoint(
    request: str,
    evidence: list[dict[str, Any]],
) -> str | None:
    """One model-facing causal gap check after substantive target evidence.

    This does not pick a route, tool, address, model, cause or followup count.
    Eligibility comes from the single interpreted objective when available.
    Work only from read receipts and an exactly one-device event-history
    anchor; broad unfiltered diagnostics do not establish device coverage.
    """
    if not is_connectivity_root_cause_request(request):
        return None
    target_ids: set[str] = set()
    source_ids: set[str] = set()
    scoped_logs = False
    dependents = False
    scoped_configuration = False
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("mutates") is True or receipt.get("effect") == "write":
            continue
        operation, args = _leaf(receipt)
        if operation == "hub_list_device_events":
            candidate = str(args.get("deviceId") or "")
            if candidate.isdigit():
                target_ids.add(candidate)
        if operation == "hub_get_source" and str(args.get("type") or "").lower() == "driver":
            candidate = str(args.get("id") or "")
            if candidate.isdigit():
                source_ids.add(candidate)
    if len(target_ids) != 1:
        return None
    target = next(iter(target_ids))
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("mutates") is True or receipt.get("effect") == "write":
            continue
        operation, args = _leaf(receipt)
        if operation == "hub_get_logs" and str(args.get("deviceId") or "") == target:
            scoped_logs = True
        if (operation == "hub_list_device_dependents"
                and str(args.get("deviceId") or "") == target):
            dependents = True
        if (operation == "hub_get_app_config" and
                str(args.get("appId") or "").isdigit()):
            scoped_configuration = True
    # Require a concrete lead. A generic inventory or broad log search
    # cannot keep an investigation looping, even if it returned 100 rows.
    if not source_ids and not dependents and not scoped_logs:
        return None
    gaps: list[str] = []
    if source_ids:
        gaps.append(
            "Driver source code was fetched (code ID(s) "
            + ", ".join(sorted(source_ids))[:80]
            + "), but fetching code is not reading its status, last-packet, "
              "LWT and watchdog update paths. Interpret relevant METHOD "
              "BODIES from the returned content; validate the installed "
              "driver mapping, not just the code ID."
        )
    if not dependents:
        gaps.append(
            "No exact-device dependent-app read was recorded. Consider the "
            "registered read-only dependency/configuration tools to inspect "
            "scheduled power-saving actions and identify a controller, "
            "before inferring an initiating automation from timing alone."
        )
    elif not scoped_configuration:
        gaps.append(
            "A dependent-app list is not its stored configuration. Verify "
            "the relevant app's actual settings/actions and dated execution."
        )
    if not scoped_logs:
        gaps.append(
            "Unfiltered hub/app logs are not target-device watchdog logs. "
            "Seek a device-ID-scoped read if the live catalog supports it; "
            "never use the absence of this read as proof of no watchdog."
        )
    return (
        "HOST EVIDENCE-DRIVEN DIAGNOSTIC CHECKPOINT (READ ONLY)\\n"
        "Device " + target + " has observed target-history evidence, but "
        "important causal discriminators remain. " + " ".join(gaps)
        + " Choose only the *single most useful available* next read from "
          "the live advertised catalog. A good read should distinguish an "
          "upstream outage from a single silent device or establish whether "
          "the last action aligns with telemetry loss. Compare same-driver "
          "peer devices or broker reachability only if a documented read-only "
          "capability exists and the live values are available. Do NOT "
          "requery generic history or logs. If sufficient causal evidence "
          "cannot be obtained, answer concisely with observations, likely "
          "cause only if supported, and explicit unresolved limitations. "
          "Never send commands, edit rules, invent tools or silently "
          "assume an old stored IP still applies."
    )


def substantive_incident_progress_since(
    evidence: list[dict[str, Any]], checkpoint_receipt_count: int,
) -> bool:
    """Did the previous retry produce a NEW source-linked discriminator?

    A cloud model round, a generic hub list, a repeated history/log page,
    an unlinked driver-source lookup or a failed tool call cannot justify
    another provider retry. Actual target-scoped dependency/configuration,
    source-linked driver evidence or independently observed upstream status
    can make a second investigation step useful. This gate is independent
    of any particular device label or room and never declares root cause.
    """
    if (
        type(checkpoint_receipt_count) is not int
        or checkpoint_receipt_count < 0
        or checkpoint_receipt_count > len(evidence)
    ):
        return False

    history_targets = set()
    linked_driver_ids = set()
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is True or row.get("effect") == "write":
            continue
        op, args = _leaf(row)
        if op == "hub_list_device_events":
            target = str(args.get("deviceId") or "")
            if target.isdigit():
                history_targets.add(target)
        if op == "hub_get_device":
            detail = row.get("details") or {}
            if isinstance(detail, dict):
                code = str(detail.get("verifiedInstalledDriverCodeId") or "")
                if code.isdigit():
                    linked_driver_ids.add((str(args.get("deviceId") or ""), code))
    if len(history_targets) != 1:
        return False
    target = next(iter(history_targets))

    for row in evidence[checkpoint_receipt_count:]:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is True or row.get("effect") == "write":
            continue
        op, args = _leaf(row)
        detail = row.get("details") or {}
        detail = detail if isinstance(detail, dict) else {}
        if op == "hub_get_device" and str(args.get("deviceId") or "") == target:
            code = str(detail.get("verifiedInstalledDriverCodeId") or "")
            if code.isdigit():
                return True
        if op == "hub_get_source" and str(args.get("type") or "").lower() == "driver":
            code = str(detail.get("sourceCodeId") or args.get("id") or "")
            if detail.get("sourceRetrieved") is True and (target, code) in linked_driver_ids:
                return True
        if op == "hub_list_device_dependents" and str(args.get("deviceId") or "") == target:
            # A verified dependency relationship is a real potential path to
            # inspect; an empty/name-matched app inventory is not.
            if detail.get("verifiedDeviceTargetLinks") is True:
                return True
            for key in ("dependentApps", "dependents"):
                if isinstance(detail.get(key), list) and detail[key]:
                    return True
        if op == "hub_get_app_config" and str(args.get("appId") or "").isdigit():
            if str(detail.get("verifiedControlsDeviceId") or "") == target:
                return True
        if str(detail.get("verifiedForDeviceId") or "") == target and (
            detail.get("independentObservationVerified") is True
            or (op == "hub_get_device_health"
                and isinstance(detail.get("pingResults"), list)
                and bool(detail["pingResults"]))
        ):
            return True
    return False


__all__ = [
    "is_connectivity_root_cause_request", "device_incident_followup",
    "incident_progress_followup", "evidence_progress_checkpoint",
    "substantive_incident_progress_since",
    "CONNECTIVITY_EVIDENCE_PLAN",
]
