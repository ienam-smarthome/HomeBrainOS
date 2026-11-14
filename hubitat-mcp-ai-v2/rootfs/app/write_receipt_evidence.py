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
                or record.get("read_only") is True):
            # A distinct read request was submitted after a write. A successful
            # read may return a snapshot, but cannot prove downstream effects.
            post_write_reads.append({
                "tool": name,
                **_target(record.get("arguments", {})),
                "separate_post_write_read": True,
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
                         " (separate read; downstream outcome not independently proven)")
    lines.append("The write(s) must not be automatically retried after this model failure.")
    return "\n".join(lines)
