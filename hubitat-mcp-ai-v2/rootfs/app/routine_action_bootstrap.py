"""Source-only preparation for exact ordinary ON/OFF requests.

No device action is chosen, authorized, submitted, replayed or inferred here.
Read-only native searches and a native device-detail read may provide verified
source evidence BEFORE a single model round. The model still selects the
actual writer from the live MCP tool schema; real UI approval remains mandatory.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from mcp import MCPError, redact
from time_evidence import native_document
from routine_action_fastpath import _requested, _normal, routine_candidate


def search_variants(question: str) -> list[str]:
    """Literal target first, then bounded adjacent-word joins.

    This accommodates routine whitespace differences in native labels without
    knowing device IDs, adding hardcoded room/device aliases, or guessing a
    synonym or related physical control surface.
    """
    wanted = _requested(question)
    if wanted is None:
        return []
    # Reconstruct original label words; never use the canonical no-space key
    # as a search term because upstream labelFilter is a literal substring.
    raw = question.strip().rstrip(".!")
    import re
    match = re.fullmatch(
        r"(?:please\s+)?(?:turn|switch)\s+(?:on|off)\s+(?:the\s+)?(.+)",
        raw, flags=re.IGNORECASE
    )
    if match is None:
        return []
    words = match.group(1).split()
    if not words:
        return []
    options = [" ".join(words)]
    for i in range(len(words) - 1):
        if len(options) >= 4:
            break
        variant = words[:i] + [words[i] + words[i+1]] + words[i+2:]
        term = " ".join(variant)
        if term not in options:
            options.append(term)
    return options


def _parsed_native(raw: dict) -> dict | None:
    if not isinstance(raw, dict) or raw.get("isError"):
        return None
    parsed = native_document(raw)
    return parsed if isinstance(parsed, dict) else None


def _exact_identity(document: dict, filter_value: str,
                    question: str) -> tuple[str, str, str] | None:
    """Require an entire source-returned, uniquely matching filtered set."""
    devices = document.get("devices")
    if not isinstance(devices, list):
        return None
    if (document.get("labelFilter") != filter_value
            or type(document.get("count")) is not int
            or type(document.get("total")) is not int
            or document["count"] != len(devices)
            or document["count"] != document["total"]
            or document.get("hasMore") is True
            or document.get("nextCursor") not in (None, "")
            or len(devices) > 50):
        return None
    wanted = _requested(question)
    if wanted is None:
        return None
    matches = []
    for row in devices:
        if not isinstance(row, dict):
            return None
        label, identifier = row.get("label"), row.get("id")
        if not isinstance(label, str) or type(identifier) not in (str, int):
            continue
        if _normal(label) == wanted[1] and row.get("disabled") is not True:
            matches.append((str(identifier).strip(), label, wanted[0]))
    if len(matches) != 1 or not matches[0][0]:
        return None
    return matches[0]


def _tool_receipt(name: str, args: dict, original: dict | None,
                  elapsed_ms: int, error: str | None = None) -> dict:
    record = {
        "name": name, "arguments": args, "success": original is not None
        and not bool(original.get("isError")),
        "elapsed_ms": elapsed_ms, "result_kind": "tool_result",
        "read_only": True, "operation_executed": original is not None,
        "client_routine_source_bootstrap": True,
    }
    if original is not None:
        content = json.dumps(redact(original), ensure_ascii=False, default=str)
        record["response"] = content
        record["response_characters"] = len(content)
    if error:
        record["error"] = str(redact(error))[:220]
    return record


async def prepare_routine_source(question: str, mcp: Any,
                                 catalog_names: set[str],
                                 *, max_seconds: float = 7.0) -> dict:
    """Bounded read-only native preflight, not a command-routing engine.

    Return a VERIFIED source candidate or a fallthrough reason. All original
    returned receipts remain accessible for the general agent if not verified.
    """
    output = {"status": "not_applicable", "candidate": None,
              "receipts": [], "lookup_reads": 0}
    wanted = _requested(question)
    variants = search_variants(question)
    required = {"hub_list_devices", "hub_get_device", "hub_call_device_command"}
    if not wanted or not variants or not required.issubset(catalog_names):
        return output
    started = time.monotonic()
    output["status"] = "no_exact_source_match"
    chosen = None
    for filter_value in variants:
        remaining = max_seconds - (time.monotonic() - started)
        if remaining <= 1.25:
            output["status"] = "read_budget_exhausted"
            break
        args = {"labelFilter": filter_value, "format": "summary"}
        begun = time.monotonic()
        try:
            raw = await asyncio.wait_for(
                mcp.call("hub_list_devices", args),
                timeout=min(2.5, remaining),
            )
        except (MCPError, asyncio.TimeoutError, ValueError) as exc:
            output["receipts"].append(_tool_receipt(
                "hub_list_devices", args, None,
                round((time.monotonic()-begun)*1000), str(exc)))
            output["status"] = "read_error"
            return output
        output["receipts"].append(_tool_receipt(
            "hub_list_devices", args, raw,
            round((time.monotonic()-begun)*1000)))
        output["lookup_reads"] += 1
        doc = _parsed_native(raw)
        if doc is None:
            output["status"] = "read_error"
            return output
        chosen = _exact_identity(doc, filter_value, question)
        if chosen:
            break
        if doc.get("count") and (
                doc.get("count") != doc.get("total")
                or doc.get("hasMore") is True):
            output["status"] = "ambiguous_or_incomplete"
            return output
    if chosen is None:
        return output
    identifier, original_label, command = chosen
    remaining = max_seconds - (time.monotonic() - started)
    if remaining <= 0.75:
        output["status"] = "read_budget_exhausted"
        return output
    args = {"deviceId": identifier}
    begun = time.monotonic()
    try:
        detail_raw = await asyncio.wait_for(
            mcp.call("hub_get_device", args),
            timeout=min(3.0, remaining),
        )
    except (MCPError, asyncio.TimeoutError, ValueError) as exc:
        output["receipts"].append(_tool_receipt(
            "hub_get_device", args, None,
            round((time.monotonic()-begun)*1000), str(exc)))
        output["status"] = "read_error"
        return output
    output["receipts"].append(_tool_receipt(
        "hub_get_device", args, detail_raw,
        round((time.monotonic()-begun)*1000)))
    details = _parsed_native(detail_raw)
    if details is None:
        output["status"] = "read_error"
        return output
    # Checking source identity/capability against a virtual PROPOSAL is
    # verification only: no native writer is called, offered, or approved.
    proposed = {"function": {
        "name": "hub_call_device_command",
        "arguments": {"deviceId": identifier, "command": command},
    }}
    qualified = routine_candidate(
        question, [proposed], output["receipts"],
        approval_available=True,
    )
    if qualified is None or _normal(qualified["label"]) != _normal(original_label):
        output["status"] = "source_not_verified"
        return output
    output["candidate"] = qualified
    output["status"] = "verified"
    return output
