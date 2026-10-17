"""Bounded completion for read-only, source-led device investigations.

Whole-file receipts certify contiguous retrieval only. They cannot certify
method behaviour or root cause. Stop duplicate read expansion once scoped
implementation, device configuration, event history and logs were queried.
"""
from __future__ import annotations

import re
from typing import Any

from adaptive_investigation_policy import source_evidence_request
from source_evidence_metadata import contiguous_source_coverage


_GENERIC_SOURCE_FAILURE = re.compile(
    r"(?:could not produce a valid structured action|"
    r"cannot produce a valid structured action|"
    r"couldn't produce a valid structured action|"
    r"no (?:valid|structured) action (?:was )?(?:provided|produced)|"
    r"found hubitat tools relevant.*no command was sent)",
    re.I | re.S,
)


def source_analysis_failed(message: str) -> bool:
    """Recognise an action-parser failure, never a proof of source analysis."""
    text = str(message or "").strip()
    if not text:
        return True
    # Only allowlisted generic failures: do not discard legitimate responses
    # which discuss why a separate historical action was never executed.
    return bool(_GENERIC_SOURCE_FAILURE.search(text) and len(text) < 1200)


_METHOD_GAP = re.compile(
    r"(?is)(?:methods?|implementations?|code\s+paths?).{0,900}?"
    r"(?:not\s+(?:present|visible|shown)|outside\s+the\s+(?:visible\s+)?"
    r"(?:excerpt|source\s+span)|cannot\s+be\s+traced|"
    r"could\s+not\s+be\s+(?:traced|reviewed))"
)


def source_method_claim_gap(message: str) -> bool:
    """The answer itself admits material method/code paths were not examined."""
    return bool(_METHOD_GAP.search(str(message or "")))


def _leaf(row: dict[str, Any]) -> str:
    arguments = row.get("arguments") or {}
    return str(row.get("sub_tool") or (
        arguments.get("tool") if isinstance(arguments, dict) else ""
    ) or "")


def _args(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("arguments")
    if not isinstance(data, dict):
        return {}
    leaf_args = data.get("args")
    return leaf_args if isinstance(leaf_args, dict) else data


def source_trace_ready_for_synthesis(
    request: str, receipts: list[dict[str, Any]],
) -> bool:
    """Source, configuration, event history, logs for one named device.

    This is a stop for *new exploratory tool calls*, never a claim that
    any Groovy method, broker state or physical device is verified.
    """
    text = str(request or "")
    if not source_evidence_request(text):
        return False
    if not re.search(r"\b(?:driver|device)\b", text, re.I):
        return False
    if not re.search(r"\b(?:events?|logs?|correlat\w*|timeline)\b", text, re.I):
        return False
    if not contiguous_source_coverage(receipts).get("fullImplementationVerified"):
        return False
    device_configs: set[str] = set()
    scoped_events: set[str] = set()
    scoped_logs: set[str] = set()
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is True or row.get("effect") != "read":
            continue
        operation, arguments = _leaf(row), _args(row)
        device = str(arguments.get("deviceId") or "")
        if not re.fullmatch(r"\d{1,9}", device):
            continue
        if operation == "hub_get_device" and arguments.get("mode") == "configuration":
            device_configs.add(device)
        if operation == "hub_list_device_events":
            scoped_events.add(device)
        if operation == "hub_get_logs":
            scoped_logs.add(device)
    return bool(device_configs & scoped_events & scoped_logs)


def source_failure_summary(receipts: list[dict[str, Any]]) -> str:
    """Truthful final read-out when code interpretation never completed."""
    coverage = contiguous_source_coverage(receipts)
    total = coverage.get("totalLength")
    ids = {
        str((row.get("details") or {}).get("sourceCodeId"))
        for row in receipts
        if isinstance(row, dict) and row.get("success") is True
        and isinstance(row.get("details"), dict)
        and row["details"].get("sourceRetrieved") is True
        and str(row["details"].get("sourceCodeId") or "").isdigit()
    }
    source_note = (
        "The entire Groovy source was retrieved by verified contiguous "
        + str(total) + "-offset-unit coverage"
        if coverage.get("fullImplementationVerified") and isinstance(total, int)
        else "Only partial or unverified Groovy source coverage was obtained"
    )
    code_note = " (source code ID " + next(iter(ids)) + ")" if len(ids) == 1 else ""
    had_events = any(
        isinstance(row, dict) and row.get("success") is True
        and _leaf(row) == "hub_list_device_events" for row in receipts
    )
    had_logs = any(
        isinstance(row, dict) and row.get("success") is True
        and _leaf(row) == "hub_get_logs" for row in receipts
    )
    return (
        "**Source investigation incomplete — analysis was not produced.** "
        + source_note + code_note + ". "
        + ("Device event history was queried. " if had_events else
           "Device event history was not verified as checked. ")
        + ("Hubitat logs were queried. " if had_logs else
           "Hubitat logs were not verified as checked. ")
        + "However, the model did not provide a valid explanation of the "
        "relevant Groovy methods, their callers or the runtime observations. "
        "Full source retrieval is not proof of method execution, MQTT broker "
        "traffic, physical power or root cause. No device command was sent "
        "as part of this read-only investigation."
    )


__all__ = [
    "source_analysis_failed", "source_trace_ready_for_synthesis",
    "source_failure_summary", "source_method_claim_gap",
]
