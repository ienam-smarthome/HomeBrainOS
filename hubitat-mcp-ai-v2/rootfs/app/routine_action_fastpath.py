"""Narrow source-verified shortcut around redundant model rounds for routine switches.

The MODEL still selects the actual native tool and arguments. This module
never routes, executes, approves or retries a command. Only one ordinary
direct on/off request, one model-selected matching native proposal and
successful ORIGINAL same-request device details can qualify. After normal
native approval/dispatch, a matching accepted original MCP write receipt
can justify a short *acceptance-only* final answer (not physical readback).

Timers, rules, network-effect interpretations, ambiguous targets, multiple
selected operations and missing/contradictory sources retain the ordinary
model-led review. This module contains no household- or device-ID shortcuts.
"""
from __future__ import annotations

import json
import re
from typing import Any

from time_evidence import native_document
from write_receipt_evidence import original_native_accepted


# Deliberately grammar- and scope-limited: no schedule, compound action,
# broad implicit effect, or read-only instruction is matched.
_SIMPLE = re.compile(
    r"^\s*(?:please\s+)?(?:turn|switch)\s+(on|off)\s+"
    r"(?:the\s+)?([^\n\r;:,?!]{1,110}?)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_UNSAFE_TARGET_CLAUSE = re.compile(
    r"\b(?:and|then|after|before|when|while|until|unless|if|every|"
    r"because|instead|without|except|again|for\s+\d+|in\s+\d+)\b",
    re.IGNORECASE,
)


def _original(record: dict) -> dict | None:
    """Successful ORIGINAL MCP tool result, never a client-local summary."""
    if (not isinstance(record, dict)
            or record.get("success") is not True
            or record.get("result_kind") != "tool_result"):
        return None
    try:
        envelope = json.loads(record.get("response", ""))
    except (TypeError, ValueError):
        return None
    if not isinstance(envelope, dict) or envelope.get("isError") is True:
        return None
    document = native_document(envelope)
    return document if isinstance(document, dict) else None


def _requested(question: str) -> tuple[str, str] | None:
    if not isinstance(question, str):
        return None
    match = _SIMPLE.fullmatch(question)
    if not match:
        return None
    direction, target = match.group(1).lower(), match.group(2).strip()
    if not target or _UNSAFE_TARGET_CLAUSE.search(target):
        return None
    return direction, _normal(target)


def _arguments(call: dict) -> tuple[str, dict] | None:
    if not isinstance(call, dict):
        return None
    function = call.get("function")
    if not isinstance(function, dict):
        return None
    name = function.get("name")
    args = function.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return None
    if not isinstance(name, str) or not isinstance(args, dict):
        return None
    return name, args



# An optional client-side read is *verification* of a model-selected target,
# never a client-selected writer or an authority to skip approval.
_CONTEXT_ENTRY = re.compile(
    r"^- (?P<label>.+) \((?P<id>[A-Za-z0-9_-]{1,40}), [^\r\n()]*\) - "
    r"(?P<capabilities>[^;\r\n]+)(?:; (?P<states>[^\r\n]*))?$"
)


def _normal(text: str) -> str:
    # Normalize conventional word separators for device labels without
    # guessing a synonym, device class, alias or target identifier.
    return re.sub(r"[\s_-]+", "", text).casefold()


def _selected(question: str, calls: list[dict], *, approval_available: bool):
    wanted = _requested(question)
    if not approval_available or not wanted or len(calls) != 1:
        return None
    selected = _arguments(calls[0])
    if selected is None:
        return None
    name, args = selected
    if name != "hub_call_device_command":
        return None
    if set(args) - {"deviceId", "command", "parameters", "waitFor"}:
        return None
    if args.get("parameters") not in (None, []):
        return None
    identifier, command = args.get("deviceId"), args.get("command")
    if (type(identifier) not in (int, str)
            or not str(identifier).strip()
            or command != wanted[0]):
        return None
    wait_for = args.get("waitFor")
    if wait_for is not None:
        if (not isinstance(wait_for, dict)
                or set(wait_for) != {"attribute", "expectedValue", "timeoutMs"}
                or wait_for.get("attribute") != "switch"
                or wait_for.get("expectedValue") != command
                or type(wait_for.get("timeoutMs")) is not int
                or not 0 < wait_for["timeoutMs"] <= 5000):
            return None
    return {
        "device_id": str(identifier).strip(),
        "native_device_id": identifier,
        "command": command,
        "target": wanted[1],
        "wait_for": wait_for,
    }


def _context_devices(doc: dict) -> list[dict] | None:
    summary = doc.get("summary")
    if not isinstance(summary, str) or len(summary) > 18000:
        return None
    entries = [line for line in summary.splitlines() if line.startswith("- ")]
    count = doc.get("count")
    if type(count) is not int or count != len(entries) or not 0 < count <= 50:
        return None
    parsed = []
    for line in entries:
        match = _CONTEXT_ENTRY.fullmatch(line)
        if not match:
            return None
        capabilities = {v.strip() for v in match["capabilities"].split(",")}
        states = {}
        for item in (match["states"] or "").split(","):
            key, sep, value = item.strip().partition("=")
            if sep:
                states[key.strip()] = value.strip()
        parsed.append({
            "id": match["id"], "label": match["label"],
            "capabilities": capabilities, "switch": states.get("switch"),
        })
    return parsed


def verification_target(question: str, calls: list[dict],
                        receipts: list[dict], *,
                        approval_available: bool) -> dict | None:
    """A bounded source check for an already model-selected direct writer.

    Requires exact and unique identity from a COMPLETE current filtered
    native inventory, opposite reported switch state, and concrete ordinary
    Light/Outlet capabilities; never from partial unfiltered inventories.
    """
    selected = _selected(question, calls, approval_available=approval_available)
    if not selected or not isinstance(receipts, list) or not receipts:
        return None
    if any(isinstance(x, dict) and x.get("name") == "hub_get_device"
           for x in receipts):
        return None  # The model has already selected the detailed read.
    filtered_sources = []
    for receipt in receipts:
        if (not isinstance(receipt, dict)
                or receipt.get("name") != "hub_list_devices"
                or receipt.get("success") is not True):
            return None
        args = receipt.get("arguments")
        if not isinstance(args, dict):
            return None
        filter_value = args.get("labelFilter")
        if not isinstance(filter_value, str) or not filter_value.strip():
            continue  # An unfiltered first page is insufficient.
        if args.get("format") != "context":
            continue
        doc = _original(receipt)
        if (not doc or doc.get("hasMore") is not False
                or type(doc.get("total")) is not int
                or doc.get("total") != doc.get("count")
                or doc.get("labelFilter") != filter_value
                or _normal(filter_value) not in selected["target"]):
            continue
        devices = _context_devices(doc)
        if devices is None:
            continue
        filtered_sources.append(devices)
    if not filtered_sources:
        return None
    for devices in filtered_sources:
        matches = [item for item in devices
                   if _normal(item["label"]) == selected["target"]]
        if len(matches) != 1:
            return None
        target = matches[0]
        if (target["id"] != selected["device_id"]
                or target["switch"] not in ("on", "off")
                or target["switch"] == selected["command"]
                or "Switch" not in target["capabilities"]
                or not ({"Light", "Outlet"} & target["capabilities"])):
            return None
    return selected


def _source_state(device: dict) -> str | None:
    values = []
    attributes = device.get("attributes")
    if isinstance(attributes, list):
        values += [a.get("value") for a in attributes
                   if isinstance(a, dict) and a.get("name") == "switch"]
    current = device.get("currentStates")
    if isinstance(current, dict) and "switch" in current:
        state = current["switch"]
        values.append(state.get("value") if isinstance(state, dict) else state)
    elif isinstance(current, list):
        values += [a.get("value") for a in current
                   if isinstance(a, dict) and a.get("name") == "switch"]
    return values[0] if values and all(v == values[0] for v in values
              ) and values[0] in ("on", "off") else None


def routine_candidate(question: str, calls: list[dict], receipts: list[dict],
                      *, approval_available: bool) -> dict | None:
    """Strict source-backed eligibility after the model selects native tools."""
    selected = _selected(question, calls, approval_available=approval_available)
    if not selected or not isinstance(receipts, list) or not receipts:
        return None
    details = []
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            return None
        if row.get("possible_native_action") is True:
            return None
        if row.get("name") == "hub_get_device":
            detail = _original(row)
            read_args = row.get("arguments")
            if (not isinstance(read_args, dict)
                    or str(read_args.get("deviceId", "")).strip()
                    != selected["device_id"]
                    or detail is None
                    or str(detail.get("id", "")).strip()
                    != selected["device_id"]):
                return None
            details.append(detail)
        elif row.get("name") != "hub_list_devices":
            return None
    if len(details) != 1:
        return None
    device = details[0]
    label = device.get("label")
    if (not isinstance(label, str) or not label.strip()
            or "\n" in label or _normal(label) != selected["target"]):
        return None
    capabilities = device.get("capabilities")
    if not isinstance(capabilities, list):
        return None
    supported_capabilities = {
        c if isinstance(c, str) else c.get("name")
        for c in capabilities if isinstance(c, str)
        or (isinstance(c, dict) and isinstance(c.get("name"), str))
    }
    if ("Switch" not in supported_capabilities
            or not ({"Light", "Outlet"} & supported_capabilities)):
        return None
    commands = device.get("commands")
    if not isinstance(commands, list):
        return None
    supported = [
        cmd for cmd in commands
        if isinstance(cmd, dict) and cmd.get("name") == selected["command"]
        and cmd.get("arguments") in (None, [])
    ]
    if (len(supported) != 1 or
            _source_state(device) != (
                "on" if selected["command"] == "off" else "off")):
        return None
    return {
        "device_id": selected["device_id"],
        "command": selected["command"],
        "label": label.strip(),
        "wait_for": selected["wait_for"],
    }


def accepted_routine_answer(candidate: dict | None,
                            receipts: list[dict]) -> str | None:
    """Receipt-backed completion after genuine approval and native dispatch.

    Native waitFor convergence is in-command state reporting, not a separately
    observed later physical effect or proof that this command caused it.
    """
    if not isinstance(candidate, dict):
        return None
    writes = [row for row in receipts if isinstance(row, dict)
              and row.get("possible_native_action") is True]
    if len(writes) != 1:
        return None
    row = writes[0]
    args = row.get("arguments")
    if (row.get("name") != "hub_call_device_command"
            or not isinstance(args, dict)
            or str(args.get("deviceId", "")).strip() != candidate["device_id"]
            or args.get("command") != candidate["command"]
            or args.get("parameters") not in (None, [])
            or args.get("waitFor") != candidate.get("wait_for")
            or original_native_accepted(row) is not True):
        return None
    document = _original(row)
    if (document is None or document.get("success") is not True
            or document.get("accepted") is False
            or document.get("command") != candidate["command"]):
        return None
    if ("deviceId" in document and
            str(document["deviceId"]).strip() != candidate["device_id"]):
        return None
    if ("device" in document and isinstance(document["device"], str)
            and _normal(document["device"]) != _normal(candidate["label"])):
        return None
    if ("parameters" in document and document["parameters"] not in (None, [])):
        return None
    wait = candidate.get("wait_for")
    reported_convergence = False
    if wait is not None:
        result = document.get("waitFor")
        if (not isinstance(result, dict)
                or result.get("attribute") != wait["attribute"]
                or result.get("expected") != wait["expectedValue"]
                or result.get("converged") is not True
                or result.get("finalValue") != wait["expectedValue"]):
            return None
        reported_convergence = True
    elif "waitFor" in document:
        # Unexpected verification contract: retain full model interpretation.
        return None
    # The label is source data, not a template or authorization. Escape it
    # before including it in Markdown, without altering native arguments.
    safe_label = re.sub(r"([\\\x60*_{}\[\]()#+!|>])", r"\\\1",
                        candidate["label"])
    direction = candidate["command"].upper()
    if reported_convergence:
        return (f"**{safe_label}: {direction} command accepted.** "
                f"Hubitat's in-command check reported switch {direction}. "
                "The physical effect was not independently verified.")
    return (f"**{safe_label}: {direction} command accepted by Hubitat.** "
            "The physical state has not been independently verified.")
