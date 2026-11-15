"""V2 source-backed device approval identity and native timing summary.

Original in-request MCP receipts only. Never routes an operation, approves,
changes arguments, performs an MCP read, or infers future physical outcomes.
"""
from __future__ import annotations

import json
import re
from typing import Any

from time_evidence import native_document


def _original(record: dict) -> dict | None:
    if (not isinstance(record, dict)
            or record.get("success") is not True
            or record.get("result_kind") != "tool_result"):
        return None
    raw = record.get("response")
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(value, dict) or value.get("isError") is True:
        return None
    document = native_document(value)
    return document if isinstance(document, dict) else None


def _id(value: Any) -> str | None:
    if type(value) in (int, str) and str(value).strip():
        return str(value).strip()
    return None


def _safe_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    # The display is plain text. Do not let a device label become an
    # instruction or multi-line "approval"; do not silently use its name
    # to authorize any command.
    label = "".join(ch for ch in value.strip() if ch.isprintable())
    return label[:110] if label else None


def verified_device_details(receipts: list[dict]) -> dict[str, dict]:
    """Successful current-request hub_get_device; exact returned/requested ID."""
    result: dict[str, dict] = {}
    for row in receipts:
        if not isinstance(row, dict) or row.get("name") != "hub_get_device":
            continue
        args = row.get("arguments")
        if not isinstance(args, dict):
            continue
        identifier = _id(args.get("deviceId"))
        doc = _original(row)
        if not identifier or not doc or _id(doc.get("id")) != identifier:
            continue
        label = _safe_label(doc.get("label")) or _safe_label(doc.get("name"))
        commands = doc.get("commands")
        advertised = {
            item["name"] for item in commands
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,99}", item["name"])
        } if isinstance(commands, list) else set()
        if label:
            result[identifier] = {"label": label, "commands": advertised}
    return result


_MINUTES_COMMAND = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*?(In|After|For)Minutes$", re.IGNORECASE
)
_MINUTE_VALUE = re.compile(r"-?(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,5})?")
_RELATIVE_PHRASE = re.compile(
    r"\b(after|in|for)\s+(\d{1,4})\s*(?:min|mins|minute|minutes)\b",
    re.IGNORECASE,
)
_DEADLINE_NAME = re.compile(
    r"(?:timed|scheduled|pending)[A-Za-z0-9_]*(?:At|Until|For)$",
    re.IGNORECASE,
)


def numeric_minutes(value: Any) -> str | None:
    """Preview and comparison only; never coerces an outgoing tool argument."""
    if type(value) in (int, float):
        value = str(value)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _MINUTE_VALUE.fullmatch(value) else None


def timing_kind(command: Any) -> str | None:
    if not isinstance(command, str):
        return None
    match = _MINUTES_COMMAND.fullmatch(command)
    if not match:
        return None
    return "delay" if match.group(1).lower() in ("in", "after") else "duration"


def requested_timing(text: str) -> tuple[str, str] | None:
    """Only unambiguous numeric-minute phrases in the original request."""
    matches = list(_RELATIVE_PHRASE.finditer(text)) if isinstance(text, str) else []
    if len(matches) != 1:
        return None
    m = matches[0]
    kind = "duration" if m.group(1).lower() == "for" else "delay"
    return kind, str(int(m.group(2)))


def _deadline(doc: dict) -> tuple[str, str] | None:
    state = doc.get("state")
    if not isinstance(state, dict):
        return None
    for name, entry in state.items():
        if not isinstance(name, str) or not _DEADLINE_NAME.fullmatch(name):
            continue
        value = entry.get("value") if isinstance(entry, dict) else entry
        if isinstance(value, str) and value.strip() and value.lower() != "none":
            # Original native text; not a locally calculated or independent
            # readback. Never infer duration or automatic resumption.
            return name, value[:80]
    return None


def source_derived_timing_answer(
    question: str, draft_answer: str, receipts: list[dict],
) -> dict:
    """Override ONLY an unequivocal, native-accepted minute action summary.

    This output-only projection is narrower than generic agent evaluation:
    source detail must advertise the exact command for this exact target,
    actual native tool result must match, and user timing/number must agree.
    Returns explicit status when a known mismatch prevents projection.
    """
    wanted = requested_timing(question)
    if not wanted:
        return {"status": "not_applicable", "answer": draft_answer}
    devices = verified_device_details(receipts)
    accepted: list[tuple[str, str, str, dict]] = []
    mismatches: list[dict] = []
    for row in receipts:
        if not isinstance(row, dict) or row.get("name") != "hub_call_device_command":
            continue
        args = row.get("arguments")
        if (not isinstance(args, dict) or row.get("possible_native_action") is not True
                or row.get("success") is not True):
            continue
        identifier, command = _id(args.get("deviceId")), args.get("command")
        params = args.get("parameters")
        detail = devices.get(identifier) if identifier else None
        if (not detail or not isinstance(command, str)
                or command not in detail["commands"]
                or not isinstance(params, list) or len(params) != 1):
            continue
        minutes = numeric_minutes(params[0])
        kind = timing_kind(command)
        if not minutes or not kind:
            continue
        if (kind, str(int(float(minutes)))) != wanted:
            mismatches.append({
                "device_id": identifier, "command": command,
                "requested": wanted[0], "selected": kind,
            })
            continue
        doc = _original(row)
        if (not doc or doc.get("success") is not True
                or doc.get("command") != command
                or doc.get("accepted") is False):
            continue
        original_params = doc.get("parameters")
        if (not isinstance(original_params, list) or len(original_params) != 1
                or numeric_minutes(original_params[0]) is None
                or float(original_params[0]) != float(minutes)):
            continue
        # A write receipt may include returned state, not independent readback.
        accepted.append((identifier, command, minutes, doc))
    if mismatches:
        return {
            "status": "native_timing_mismatch",
            "answer": (
                "The native command in this request used different timing "
                "semantics from your instruction. The original user request "
                f"specified {wanted[0]}, but a selected native command was "
                "classified differently. Check the original Technical JSON "
                "before assuming the requested timing was scheduled. "
                "This output warning does not undo or repeat any command."
            ),
            "matches": 0, "independent_readback": False,
        }
    if len(accepted) != 1:
        return {"status": "not_projected", "answer": draft_answer}
    device_id, command, minutes, doc = accepted[0]
    label = devices[device_id]["label"]
    kind = wanted[0]
    requested_text = (f"after {minutes} minutes" if kind == "delay"
                      else f"for {minutes} minutes")
    due = _deadline(doc)
    lines = [
        f"**Native command accepted:** **{label}** (device ID {device_id}).",
        f"\u2022 Command: `{command}` with parameter `{minutes}`.",
        f"\u2022 Requested timing: **{requested_text}** "
        + ("(delayed onset, **not** a blocking duration)."
           if kind == "delay"
           else "(duration, **not** a delayed start)."),
        "\u2022 The original native MCP response reported `success: true`.",
    ]
    if due is not None:
        lines.append(
            f"\u2022 Its native write response reported `{due[0]} = {due[1]}`."
        )
    lines.extend([
        "",
        "**Evidence limit:** The returned timer/state fields are part of the "
        "write response, **not an independent post-write readback**. "
        "A future physical or network change has not been observed in this "
        "request. The original source does not establish an automatic "
        "reversal or a fixed blocking duration.",
    ])
    return {
        "status": "source_derived_native_acceptance",
        "answer": "\n".join(lines),
        "verified_device_id": device_id,
        "matched_command": command,
        "timing_kind": kind,
        "independent_readback": False,
        "reported_deadline_field": due[0] if due else None,
        "original_successful_write_receipts": 1,
    }
