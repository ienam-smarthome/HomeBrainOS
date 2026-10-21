"""Fail-closed final claims for named Hubitat Rule Machine investigations.

A tool's 'success' means an MCP read returned data, not that an entire
requested lookback, command actor, action reference or execution was verified.
Only corrective edits backed by the returned typed receipts are made.
"""
from __future__ import annotations

import re
from typing import Any

from targeted_rule_scope_policy import is_targeted_rule_investigation


def _verified_global_names(receipts: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for row in receipts:
        if (not isinstance(row, dict) or row.get("success") is not True
                or row.get("sub_tool") != "hub_get_variable"):
            continue
        details = row.get("details") or {}
        if not isinstance(details, dict):
            continue
        source = str(details.get("variableScope") or "").casefold()
        name = details.get("variableName")
        if source == "hub" and isinstance(name, str) and name:
            names.add(name)
    return names


def _has_verified_cross_app_refs(receipts: list[dict[str, Any]]) -> bool:
    # This marker can only be written by an explicit future typed action
    # reference extractor. App page identity or a same-name variable is NOT
    # sufficient proof for this claim.
    return any(
        isinstance(row, dict) and row.get("success") is True
        and row.get("evidence_kind") == "typed_cross_rule_variable_reference"
        and isinstance(row.get("details"), dict)
        and row["details"].get("bothRuleReferencesVerified") is True
        for row in receipts
    )


def _history_is_limited(
    receipts: list[dict[str, Any]],
    coverage: dict[str, Any] | None,
) -> bool:
    if isinstance(coverage, dict):
        sources = coverage.get("sourceCoverage")
        if isinstance(sources, dict) and "command_history" in (
            sources.get("missingSourceKinds") or []
        ):
            return True
        if coverage.get("sourceIntegrityWarnings"):
            return True
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("sub_tool") != "hub_list_device_events":
            continue
        details = row.get("details") or {}
        if isinstance(details, dict) and (
            details.get("observedEventsTruncated") is True
            or details.get("eventsTruncated") is True
            or details.get("historySourceIntegrityVerified") is False
        ):
            return True
    return False


def calibrate_native_rule_claims(
    message: str,
    receipts: list[dict[str, Any]],
    coverage: dict[str, Any] | None,
    request: str,
) -> tuple[str, tuple[str, ...]]:
    """Preserve confirmed readings while correcting specifically unsafe claims.

    Never infer an absence of OFF commands from a bounded device-event list,
    or that two apps reference the same variable because a Hub Variable
    with the stated name exists. A *real* typed cross-app action reference
    receipt can relax the second guard in future.
    """
    draft = str(message or "")
    if not is_targeted_rule_investigation(request):
        return draft, ()
    issues: list[str] = []
    partial = bool(isinstance(coverage, dict) and
                   coverage.get("evidenceComplete") is False)

    if partial:
        # V0.18.53 only matched "... investigation of ... is complete.".
        # V0.18.54 used "The verification of the logic and synchronization
        # between apps ... is complete based on current-turn evidence."
        first, sep, rest = draft.partition("\n")
        if re.search(
            r"(?i)\b(?:investigation|verification|review)\b.{0,260}"
            r"\bis complete\b", first,
        ):
            first, changed = re.subn(
                r"(?i)\bis complete(?:\s+based\s+on\s+current-turn\s+evidence)?\.",
                "remains partial on the returned evidence.",
                first, count=1,
            )
            if changed:
                draft = first + sep + rest
                issues.append("native_rule_incomplete_headline")

    if _history_is_limited(receipts, coverage):
        changed_any = False
        # A requested hoursBack=24 is a QUERY parameter. The returned source
        # had only 16 selected rows / five minutes, mostly driver usage
        # telemetry, with observedEventsTruncated=true.
        draft, n = re.subn(
            r"(?i)\bI analyzed the 24-hour event history for\b",
            "I queried events with a requested 24-hour lookback for",
            draft,
        )
        changed_any |= bool(n)
        # An absence claim is not justified without authoritative, complete
        # command history regardless of the query's hoursBack.
        lines = draft.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if re.search(
                r"(?i)^\s*[-*]\s+\*{0,2}Threshold Execution:\*{0,2}",
                line,
            ) and re.search(r"(?i)\b(?:no evidence|only .{0,45}off.+commands)\b", line):
                lines[i] = (
                    "* **Threshold Execution:** No attributable threshold "
                    "block has been verified. The returned device events "
                    "are bounded/truncated and do not establish a complete "
                    "24-hour command history or which app issued an OFF."
                    + ("\n" if line.endswith("\n") else "")
                )
                changed_any = True
            elif line.lstrip().startswith("|") and re.search(
                r"(?i)\|\s*\*{0,2}Execution\*{0,2}\s*\|", line,
            ) and re.search(r"(?i)\b(?:not observed|no.*off commands)\b", line):
                lines[i] = (
                    "| **Execution** | Unverified | No complete app-attributed "
                    "command history was established from the returned "
                    "bounded events. |\n"
                )
                changed_any = True
        draft = "".join(lines)
        if changed_any:
            issues.append("native_rule_truncated_command_history")

    global_names = _verified_global_names(receipts)
    if global_names:
        # The source-qualified global variable definition refutes a
        # same-name variable being *only* local. It does not establish
        # action-level cross-app synchronization.
        lines = draft.splitlines(keepends=True)
        corrected = False
        for i, line in enumerate(lines):
            if ("Possible explanation" in line
                    and re.search(r"(?i)\bis defined as a local variable\b", line)
                    and any(name.casefold() in line.casefold() for name in global_names)):
                variable = next(
                    name for name in sorted(global_names)
                    if name.casefold() in line.casefold()
                )
                lines[i] = (
                    "- **Variable definition checked:** " + variable +
                    " is reported by the Hub Variable reader with source=hub; "
                    "the local-only interpretation is not supported. "
                    "The two apps' exact action references still need "
                    "separate verification.\n"
                )
                # The next 'distinguishing evidence' question was resolved
                # for variable definition (not for action references).
                if i + 1 < len(lines) and "Distinguishing evidence:" in lines[i + 1]:
                    lines[i + 1] = ""
                corrected = True
        if corrected:
            draft = "".join(lines)
            issues.append("native_rule_global_scope_hypothesis_resolved")
    if global_names and not _has_verified_cross_app_refs(receipts):
        # A hub_get_variable(source=hub) read proves global availability,
        # not that the compiled actions of two distinct apps address it.
        lines = draft.splitlines(keepends=True)
        modified = False
        for i, line in enumerate(lines):
            if re.search(r"(?i)^\s*[*-]\s+\*{0,2}Synchronization:\*{0,2}", line):
                lines[i] = (
                    "* **Synchronization:** The counter exists as a global "
                    "Hub Variable, but the returned receipts do not "
                    "independently establish both apps' *exact action "
                    "references* or prove that a reset executed.\n"
                )
                modified = True
            elif re.search(r"(?i)^\s*\|\s*\*{0,2}Variable Sync\*{0,2}\s*\|", line):
                lines[i] = (
                    "| **Variable Sync** | Not independently verified | "
                    "Global variable existence is verified; typed references "
                    "from both rule action trees are still needed. |\n"
                )
                modified = True
            elif re.search(r"(?i)^\s*\|\s*\*{0,2}Logic Match\*{0,2}\s*\|", line):
                lines[i] = (
                    "| **Logic Match** | Configuration reported | "
                    "The app-config reads do not independently verify "
                    "runtime increments, blocking or reset execution. |\n"
                )
                modified = True
        draft = "".join(lines)
        if modified:
            issues.append("native_rule_cross_app_reference_unverified")

    return draft, tuple(dict.fromkeys(issues))


__all__ = ["calibrate_native_rule_claims"]
