"""Evidence-only guard against invented historical automation executions.

Source retrieval and a broad hoursBack query are not proof that a named app
actually issued a command at a model-asserted historical boundary. This guard
does not claim the action never happened: it checks only current-turn returned
event rows and errs toward an unresolved investigation if an otherwise confident
named-app execution is unsupported.

Never let model-proposed facts enter this evidence store.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any


_APP_ACTOR = re.compile(r"(?i)\b(?:app\s*id|appId|app)\s*[:=#]?\s*(\d{3,9})\b")
_ACT = re.compile(
    r"(?i)\b(?:issued|sent|triggered|caused|switched|turned|executed|"
    r"commanded|activated|initiated|fired)\b|(?:\bon\(\)|\boff\(\))"
)
_DATE = re.compile(
    r"(?i)\b(?:on\s+)?(?:Oct(?:ober)?|Nov(?:ember)?|Sep(?:tember)?|"
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Dec(?:ember)?)\s+\d{1,2}\b"
)
_CLEARLY_UNVERIFIED = re.compile(
    r"(?i)\b(?:unknown whether|cannot determine whether|not established "
    r"whether|unverified whether|no evidence whether)\b"
)
_SOURCE_FALSE_ABSENCE = re.compile(
    r"(?i)\b(?:driver|Groovy|implementation)\s+source(?:\s+code)?\s+"
    r"(?:was|were|has)\s+not\s+(?:been\s+)?(?:retrieved|read|provided|checked)\b"
)
_DEVICE_SOURCE_OPS = {"hub_get_source", "homebrain_read_groovy_source"}


def _observed_events(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        for key in ("observedEvents", "events", "commandEvents", "boundaryEvents"):
            rows = details.get(key)
            if isinstance(rows, list):
                events.extend(item for item in rows if isinstance(item, dict))
    return events


def _source_received(evidence: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(row, dict) and row.get("success") is True
        and str(row.get("sub_tool") or row.get("tool") or "") in _DEVICE_SOURCE_OPS
        and isinstance(row.get("details"), dict)
        and row["details"].get("sourceRetrieved") is True
        for row in evidence
    )


def _actor(event: dict[str, Any]) -> str:
    producer = event.get("producedBy") or event.get("producer") or {}
    if not isinstance(producer, dict):
        return ""
    if (str(producer.get("type") or "").casefold() not in ("app", "application")
            and "appId" not in producer):
        return ""
    return str(producer.get("appId") or producer.get("id") or "")


def _event_command(event: dict[str, Any]) -> bool:
    operation = str(event.get("name") or event.get("command") or "")
    description = str(event.get("description") or "")
    return bool(
        str(event.get("type") or "").casefold() == "command"
        or operation.casefold().startswith("command-")
        or re.search(r"(?i)\bcommand (?:called|issued|sent)\b", description)
    )


def _claim_context(message: str, match: re.Match[str]) -> str:
    # A table row, clause or adjacent appId-in-parentheses belongs to the
    # same assertion. Keep it bounded so unrelated methods aren't conflated.
    start, end = match.span()
    left = max(message.rfind("\n", 0, start), message.rfind(". ", 0, start))
    return message[max(0, left + 1, start - 270): min(len(message), end + 155)]


def _claimed_date(context: str) -> tuple[int, int] | None:
    m = _DATE.search(context)
    if m is None:
        return None
    name, number = re.search(r"([A-Za-z]+)\s+(\d{1,2})", m.group(0)).groups()
    for month in range(1, 13):
        if datetime(2026, month, 1).strftime("%B").casefold().startswith(name[:3].casefold()):
            return month, int(number)
    return None


def _matching_record(
    app_id: str, message_context: str, events: list[dict[str, Any]],
) -> bool:
    # Require a concrete command event, not mere app configuration or source
    # code mentioning the installed rule. When date is specified, the event
    # date must match. Source rows without a date cannot prove a dated claim.
    boundary = _claimed_date(message_context)
    for event in events:
        if _actor(event) != app_id or not _event_command(event):
            continue
        if boundary is None:
            return True
        raw = str(event.get("date") or event.get("timestamp") or "")
        try:
            at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if (at.month, at.day) == boundary:
            return True
    return False


def assess_historical_claims(
    message: str, evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Identify unsupported named-app command provenance with high precision.

    An absent event in truncated history is never proof that the action didn't
    occur. Here it only prevents *a claimed verification* and requires a
    qualified answer or further evidence.
    """
    message = str(message or "")
    events = _observed_events(evidence)
    unverified: set[str] = set()
    for match in _APP_ACTOR.finditer(message):
        context = _claim_context(message, match)
        if not _ACT.search(context) or _CLEARLY_UNVERIFIED.search(context):
            continue
        app_id = match.group(1)
        if not _matching_record(app_id, context, events):
            unverified.add(app_id)
    truncated = any(
        isinstance(r, dict) and r.get("success") is True
        and isinstance(r.get("details"), dict)
        and any(r["details"].get(k) is True for k in
                ("observedEventsTruncated", "boundaryEventsTruncated"))
        for r in evidence
    )
    return {
        "unverifiedCommandActors": sorted(unverified),
        "historicalActionVerified": not bool(unverified),
        "historyTruncated": truncated,
        "sourceReadContradicted": bool(
            _source_received(evidence) and _SOURCE_FALSE_ABSENCE.search(message)
        ),
    }


def render_unverified_claim_warning(
    facts: dict[str, Any], evidence: list[dict[str, Any]],
) -> str:
    """Conservative replacement when a claimed named-app execution is unfounded.

    Do not republish an unverified causal timeline alongside the disclaimer:
    that would still mislead readers. Preserve verified source categories and
    actionable next evidence instead of inventing earlier actions.
    """
    code_ids = sorted({
        str(r["details"]["sourceCodeId"])
        for r in evidence
        if isinstance(r, dict) and r.get("success") is True
        and isinstance(r.get("details"), dict)
        and r["details"].get("sourceRetrieved") is True
        and str(r["details"].get("sourceCodeId") or "").isdigit()
    })
    ops = {
        str(r.get("sub_tool") or r.get("tool") or "")
        for r in evidence if isinstance(r, dict) and r.get("success") is True
    }
    labels = []
    if code_ids:
        labels.append("Groovy source code ID " + ", ".join(code_ids))
    if "hub_get_device" in ops:
        labels.append("device attributes/configuration")
    if "hub_list_device_events" in ops or "homebrain_device_history" in ops:
        labels.append("bounded device-event history")
    if "hub_get_logs" in ops:
        labels.append("device-scoped logs")
    listed = ", ".join(labels) or "some read-only sources"
    return (
        "**Historical cause not established.** The investigation retrieved "
        + listed + ", but its answer attributed a historical command or "
        "automation execution to app ID(s) "
        + ", ".join(facts["unverifiedCommandActors"])
        + " without a matching dated command event in the returned evidence. "
        "This does not prove those automations never ran. "
        + (
            "The returned event-history projection was truncated, so an "
            "older event may have been omitted. "
            if facts["historyTruncated"] else
            "The available history does not establish the stated execution. "
        )
        + ("The source-read absence claim also contradicts the successful "
           "Groovy source receipt. " if facts["sourceReadContradicted"] else "")
        + "Do not treat the proposed automation/timestamp sequence as the "
          "root cause. The reported health/watchdog observations and the "
          "driver's MQTT status are not independent physical connectivity "
          "evidence. Inspect a date-bounded command/event page for the "
          "asserted time and the relevant automation's execution logs before "
          "attributing causation. No device commands were issued in this "
          "read-only investigation."
    )


_UNVERIFIED_DISPATCH_ASSERTION = re.compile(
    r"(?i)\b(?:the\s+)?command\s+dispatch\s+"
    r"(?:is|was|has\s+been)\s+(?:established|confirmed|verified)\b"
)


def reconcile_historical_dispatch_claim(
    message: str, request: str, evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Do not mistake a recorded switch state for a dispatched command.

    Only a successful, target-scoped command-history read containing a named
    command event can support an unconditional command-dispatch assertion.
    An empty command page does not prove that no command occurred.
    """
    from rule_machine_analysis import historical_rule_execution_request
    if not historical_rule_execution_request(request):
        return message, False
    ids = re.findall(
        r"(?i)\bdevice\s*(?:id\s*)?[#:]?\s*(\d{2,7})\b", request,
    )
    if len(set(ids)) != 1:
        return message, False
    device_id = ids[0]
    # A verified mixed event page can be just as authoritative about a
    # recorded Hubitat off()/on() invocation as an attribute-filtered query.
    # Source coverage must never claim missing command history merely because
    # the MCP server returned the event inside an unfiltered device page.
    from historical_command_source_contract import (
        focused_command_observation,
    )
    observed_command = focused_command_observation(request, evidence)
    if (
        observed_command is not None
        and observed_command["deviceId"] == device_id
    ):
        return message, False
    observed = False
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("sub_tool") != "hub_list_device_events":
            continue
        outer = receipt.get("arguments")
        args = outer.get("args") if isinstance(outer, dict) else {}
        if not isinstance(args, dict):
            continue
        if (str(args.get("deviceId") or "") != device_id
                or not str(args.get("attribute") or "").startswith("command-")):
            continue
        details = receipt.get("details")
        rows = details.get("events") if isinstance(details, dict) else None
        if isinstance(rows, list) and any(
            isinstance(row, dict)
            and str(row.get("name") or "").casefold()
                == str(args["attribute"]).casefold()
            for row in rows
        ):
            observed = True
            break
    if observed:
        return message, False
    corrected, count = _UNVERIFIED_DISPATCH_ASSERTION.subn(
        "a device state transition is recorded, but command dispatch remains unverified",
        str(message or ""),
    )
    return corrected, bool(count)


__all__ = [
    "assess_historical_claims", "render_unverified_claim_warning",
    "reconcile_historical_dispatch_claim",
]
