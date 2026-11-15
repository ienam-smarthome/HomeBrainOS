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
    return direction, " ".join(target.split()).casefold()


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


def routine_candidate(question: str, calls: list[dict], receipts: list[dict],
                      *, approval_available: bool) -> dict | None:
    """Prove exact user target + model selection + current native commands.

    A successful *hub_get_device* source is necessary: a label-only inventory,
    prior chat, driver metadata, model reasoning or a write result cannot
    independently establish exact identity and command support.
    """
    wanted = _requested(question)
    if not approval_available or not wanted or len(calls) != 1:
        return None
    selected = _arguments(calls[0])
    if selected is None:
        return None
    name, args = selected
    if name != "hub_call_device_command":
        return None
    if set(args) - {"deviceId", "command", "parameters"}:
        return None
    if args.get("parameters") not in (None, []):
        return None
    identifier = args.get("deviceId")
    command = args.get("command")
    if type(identifier) not in (int, str) or not str(identifier).strip():
        return None
    if command != wanted[0]:
        return None
    identifier = str(identifier).strip()
    if not isinstance(receipts, list) or not receipts:
        return None

    # Any other attempted write, failed source, or another device detail is a
    # signal to leave the full model-led review intact. No prior receipts.
    details = []
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            return None
        if row.get("possible_native_action") is True:
            return None
        if row.get("name") == "hub_get_device":
            detail = _original(row)
            read_args = row.get("arguments", {})
            if (not isinstance(read_args, dict)
                    or str(read_args.get("deviceId", "")).strip() != identifier
                    or detail is None
                    or str(detail.get("id", "")).strip() != identifier):
                return None
            details.append(detail)
        elif row.get("name") != "hub_list_devices":
            # Additional catalog, rule, timer or other investigation sources
            # indicate a more complex plan, so retain model review.
            return None
    if len(details) != 1:
        return None
    device = details[0]
    label = device.get("label")
    if not isinstance(label, str) or not label.strip() or "\n" in label:
        return None
    if " ".join(label.split()).casefold() != wanted[1]:
        return None
    capabilities = device.get("capabilities")
    if not isinstance(capabilities, list) or "Switch" not in capabilities:
        return None
    commands = device.get("commands")
    if not isinstance(commands, list):
        return None
    supported = [
        cmd for cmd in commands
        if isinstance(cmd, dict) and cmd.get("name") == command
        and cmd.get("arguments") in (None, [])
    ]
    if len(supported) != 1:
        return None
    attributes = device.get("attributes")
    if not isinstance(attributes, list):
        return None
    states = [
        a.get("value") for a in attributes
        if isinstance(a, dict) and a.get("name") == "switch"
    ]
    if len(states) != 1 or states[0] not in ("on", "off"):
        return None
    if states[0] == command:
        # A duplicate write to an already-satisfied target is not routine.
        return None
    return {"device_id": identifier, "command": command, "label": label.strip()}


def accepted_routine_answer(candidate: dict | None,
                            receipts: list[dict]) -> str | None:
    """One accepted ORIGINAL write receipt; no physical-effect inference.

    Must be invoked only *after* the original before_call approval and real
    native MCP transport have completed. It cannot manufacture a tool call.
    """
    if not isinstance(candidate, dict):
        return None
    writes = [
        row for row in receipts
        if isinstance(row, dict) and row.get("possible_native_action") is True
    ]
    if len(writes) != 1:
        return None
    row = writes[0]
    args = row.get("arguments")
    if (row.get("name") != "hub_call_device_command"
            or not isinstance(args, dict)
            or str(args.get("deviceId", "")).strip() != candidate["device_id"]
            or args.get("command") != candidate["command"]
            or args.get("parameters") not in (None, [])
            or original_native_accepted(row) is not True):
        return None
    document = _original(row)
    if (document is None or document.get("success") is not True
            or document.get("accepted") is False
            or document.get("command") != candidate["command"]):
        return None
    if ("deviceId" in document
            and str(document["deviceId"]).strip() != candidate["device_id"]):
        return None
    if ("parameters" in document and document["parameters"] not in (None, [])):
        return None
    # A response may include stale state. It is NOT an independent postwrite
    # read. Plain text device labels are escaped before Markdown rendering.
    safe_label = re.sub(r"([\\`*_{}\[\]()#+!|>])", r"\\\1",
                        candidate["label"])
    direction = candidate["command"].upper()
    return (f"**{safe_label}: {direction} command accepted by Hubitat.** "
            "The physical state has not been independently verified.")
