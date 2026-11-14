"""Private, source-labelled executed-write evidence after a later model error.

Does not infer physical results, retry any command, or change the model's answer.
"""
from __future__ import annotations

import json
import re
from typing import Any
from mcp import redact
from time_evidence import native_document


def model_error_kind(error: Exception | str) -> str:
    text = str(error)
    if re.search(r"\bHTTP 402\b", text, re.IGNORECASE):
        return "quota_or_billing"
    if re.search(r"\bHTTP 429\b", text, re.IGNORECASE):
        return "rate_limit"
    return "other"


def original_native_accepted(record: dict) -> bool | None:
    try:
        source = json.loads(record.get("response", ""))
    except (ValueError, TypeError):
        return None
    document = native_document(source)
    if isinstance(document, dict):
        if document.get("success") is False or document.get("accepted") is False:
            return False
        if document.get("success") is True or document.get("accepted") is True:
            return True
    return None


def _target(arguments: dict) -> dict:
    arguments = arguments if isinstance(arguments, dict) else {}
    leaf = arguments.get("args") if isinstance(arguments.get("args"), dict) else {}
    value = leaf if isinstance(arguments.get("tool"), str) else arguments
    result = {}
    for key in ("deviceId", "appId", "rule_id", "ruleId", "command", "parameters", "args"):
        if key in value:
            if key == "args" and not isinstance(value[key], list):
                continue
            result[key] = redact(value[key])
    if isinstance(arguments.get("tool"), str):
        result["native_leaf"] = arguments["tool"]
    return result


def _read_values(record: dict) -> dict:
    try:
        raw = json.loads(record.get("response", ""))
    except (ValueError, TypeError):
        return {}
    document = native_document(raw)
    if not isinstance(document, dict):
        return {}
    # Retain only directly reported value fields, never infer or calculate
    # downstream effects. Redaction applies to each source value.
    values = {}
    if isinstance(document.get("attribute"), str) and "value" in document:
        values[str(document["attribute"])[:100]] = redact(document["value"])
    for key in ("switch", "pendingUntil", "deadline", "pendingBlockUntil",
                "internetAccess", "scheduledFor"):
        if key in document and type(document[key]) in (str, int, float, bool):
            values[key] = redact(document[key])
    return dict(list(values.items())[:8])


def _identity(arguments: dict) -> tuple[str, str] | None:
    if not isinstance(arguments, dict):
        return None
    payload = (arguments.get("args") if isinstance(arguments.get("tool"), str)
               and isinstance(arguments.get("args"), dict) else arguments)
    for key in ("deviceId", "appId", "rule_id", "ruleId"):
        if isinstance(payload.get(key), (str, int)):
            return key, str(payload[key])
    return None


def matches_prior_written_target(receipts: list[dict], read_arguments: dict) -> bool:
    """Separate read call is target-specific only if explicit native IDs match."""
    current = _identity(read_arguments)
    if current is None:
        return False
    return any(
        row.get("possible_native_action") is True and row.get("success") is True
        and _identity(row.get("arguments", {})) == current
        for row in receipts
    )


def write_failure_evidence(receipts: list[dict]) -> dict:
    executed_writes = []
    post_write_reads = []
    seen_write = False
    for record in receipts:
        if not isinstance(record, dict):
            continue
        name = str(record.get("name") or "")
        if record.get("success") is not True:
            continue
        if record.get("possible_native_action") is True and record.get("result_kind") == "tool_result":
            seen_write = True
            executed_writes.append({
                "tool": name,
                **_target(record.get("arguments", {})),
                "accepted": original_native_accepted(record),
                "source": "original native MCP write response",
                "outcome_verified": False,
            })
        elif seen_write and record.get("result_kind") == "tool_result" and (
                name.startswith(("hub_get_", "hub_list_", "hub_read_", "hub_search_"))
                or (isinstance(record.get("arguments"), dict)
                    and str(record["arguments"].get("tool") or "").startswith(
                        ("hub_get_", "hub_list_", "hub_read_", "hub_search_")))
                or record.get("read_only") is True):
            # A distinct read request was submitted after a write. A successful
            # read may return a snapshot, but cannot prove downstream effects.
            post_write_reads.append({
                "tool": name,
                **_target(record.get("arguments", {})),
                "separate_post_write_read": True,
                "same_explicit_target_id_as_prior_write": (
                    _identity(record.get("arguments", {})) is not None
                    and any(_identity(w.get("arguments", {}))
                            == _identity(record.get("arguments", {}))
                            for w in receipts if w.get("possible_native_action") is True
                            and w.get("success") is True)
                ),
                "reported_values": _read_values(record),
                "source_response": redact(str(record.get("response", ""))[:6000]),
            })
    return {"executed_writes": executed_writes[:12],
            "post_write_reads": post_write_reads[:12]}


def model_failure_notice(evidence: dict) -> str:
    """Plain source-summary with no scheduling, cause or outcome conclusion."""
    writes = evidence.get("executed_writes") or []
    if not writes:
        return ""
    lines = ["Client-generated receipt summary (NOT written by the model):",
             "The model failed after the following native write response(s) returned. "
             "These receipts do not prove the intended downstream effect."]
    for item in writes:
        action = item.get("command") or item.get("native_leaf") or item.get("tool")
        status = ("accepted=true" if item.get("accepted") is True else
                  "accepted=false" if item.get("accepted") is False else
                  "acceptance not explicitly confirmed")
        lines.append("- " + str(action) + " [" + status + "]; supplied target " +
                     str(item.get("deviceId") or item.get("appId") or item.get("rule_id") or "unspecified"))
    reads = evidence.get("post_write_reads") or []
    if reads:
        lines.append("Separate post-write read result(s) were returned; inspect the "
                     "original Technical JSON for exact reported values:")
        for read in reads:
            lines.append("- " + str(read["tool"]) +
                         ": " + (json.dumps(read.get("reported_values"), ensure_ascii=False)
                                if read.get("reported_values") else
                                "no direct scalar reading extracted") +
                         " (separate native read; no downstream outcome claim)")
    lines.append("The write(s) must not be automatically retried after this model failure.")
    return "\n".join(lines)
