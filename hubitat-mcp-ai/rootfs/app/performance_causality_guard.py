"""Fail-closed performance/log causality checks for final synthesis.

Performance statistics can establish *what* is expensive. A recent log sample can
establish *what happened recently*. Unless a dedicated current-turn evidence source
links those two facts, the latter must not be promoted into the cause of the former.
"""

from __future__ import annotations

import re
from typing import Any

_PERFORMANCE_TOOL = "hub_get_performance_stats"
_LOG_TOOL = "hub_get_logs"

_PERF_TERM = (
    r"(?:busy(?:\s+percentage|\s*%)?|load|latency|execution(?:\s+time)?|"
    r"response\s+time|performance|resource(?:\s+consumption|\s+usage)?)"
)

_ROOT_CAUSE_LOG_HEADING = re.compile(
    r"(?im)^#{1,6}\s*[^\n]*\broot causes?\b[^\n]*\blogs?\b[^\n]*$"
)
_LOG_CAUSE_PREAMBLE = re.compile(
    rf"(?i)\bThe logs\s+(?:reveal|show|identify)\s+[^\n:.]*"
    rf"(?:driv(?:e|es|ing)|caus(?:e|es|ing)|explain(?:s|ing)?)\s+"
    rf"(?:this\s+|the\s+)?{_PERF_TERM}[^\n:.]*[:.]?"
)
_CLAUSAL_PERF_CAUSE = re.compile(
    rf"(?i),\s*which\s+(?:(?:is|are|was|were)\s+)?"
    rf"(?:(?:likely|probably|clearly|directly)\s+)?"
    rf"(?:driv(?:e|es|ing)|caus(?:e|es|ing)|explain(?:s|ing)?)\s+"
    rf"(?:the\s+)?(?:high\s+)?{_PERF_TERM}[^.!?\n]*(?:[.!?]|$)"
)
_SENTENCE_PERF_CAUSE = re.compile(
    rf"(?i)\b(?:this|that|it)\s+(?:(?:is|are|was|were)\s+)?"
    rf"(?:(?:likely|probably|clearly|directly)\s+)?"
    rf"(?:driv(?:e|es|ing)|caus(?:e|es|ing)|explain(?:s|ing)?|"
    rf"responsible\s+for)\s+(?:the\s+)?(?:high\s+)?"
    rf"{_PERF_TERM}[^.!?\n]*(?:[.!?]|$)"
)
_HYPOTHESIS_PERF_LINK = re.compile(
    rf"(?i)\b(?:this|that|it)\s+(?:is|was)\s+(?:a\s+)?"
    rf"(?:(?:very|strongly)\s+)?(?:likely|plausible|probable)\s+"
    rf"hypothesis\s+(?:for|behind)\s+(?:the\s+)?(?:high\s+)?"
    rf"{_PERF_TERM}[^.!?\n]*(?:[.!?]|$)"
)
_OVERLOAD_SOURCE_SUGGESTION = re.compile(
    r"(?i)\b(?:this|that|it)\s+(?:strongly\s+)?suggests\b"
    r"[^.!?\n]{0,260}\b(?:hidden\s+)?(?:overload|load)\s+source\b"
    r"[^.!?\n]*(?:[.!?]|$)"
)
_THRESHOLD_OSCILLATION = re.compile(
    r"(?i)\b(?:fluctuat(?:e|es|ing|ed)|oscillat(?:e|es|ing|ed))\b"
    r"[^,.;\n]{0,120}\b(?:around|across)\b[^,.;\n]{0,80}"
    r"\b(?:threshold|mark)\b"
)
_ONE_SIDED_FLUCTUATION_CLAUSE = re.compile(
    r"(?i)\b(?:because|as)\s+"
    r"(?=[^\n]{0,160}\b(?:power|value|reading)s?\b)"
    r"(?=[^\n]{0,220}\b(?:fluctuat(?:e|es|ing|ed)|oscillat(?:e|es|ing|ed))\b)"
    r"[^\n]{0,320}?\),(?=\s+(?:the|this|that)\b)"
)
_RULE_EDIT_LINE = re.compile(
    r"(?i)^(?=.*\b(?:modify|change|add|set)\b)"
    r"(?=.*\b(?:trigger|triggering|threshold|debounce|duration|stays that way)\b)"
    r".*$"
)
_RULE_PRESCRIPTION_LINE = re.compile(
    r"(?i)^(?=.*\b(?:need(?:s|ed)?|should|must|require(?:s|d)?|increase|decrease|"
    r"add|set|change|modify)\b)"
    r"(?=.*\b(?:debounce|threshold|trigger(?:ing)?|duration|stays that way|"
    r"gap between trigger actions|larger gap)\b).*$"
)


def _sub_tool(row: dict[str, Any]) -> str:
    value = row.get("sub_tool")
    if value:
        return str(value)
    arguments = row.get("arguments")
    if isinstance(arguments, dict):
        value = arguments.get("tool")
        if value:
            return str(value)
    return ""


def _successful(row: dict[str, Any]) -> bool:
    return row.get("success") is not False


def performance_validation_needed(evidence: list[dict[str, Any]]) -> bool:
    """True when the turn combines performance totals with recent logs."""

    has_performance = any(
        isinstance(row, dict)
        and _successful(row)
        and _sub_tool(row) == _PERFORMANCE_TOOL
        for row in evidence
    )
    has_logs = any(
        isinstance(row, dict)
        and _successful(row)
        and _sub_tool(row) == _LOG_TOOL
        for row in evidence
    )
    return has_performance and has_logs


def _has_rule_configuration_evidence(evidence: list[dict[str, Any]]) -> bool:
    """Recognize only explicit configuration/detail reads, never list/log reads."""

    for row in evidence:
        if not isinstance(row, dict) or not _successful(row):
            continue
        kind = str(row.get("evidence_kind") or "").casefold()
        if "rule_configuration" in kind or "app_configuration" in kind:
            return True
        sub_tool = _sub_tool(row).casefold()
        if not sub_tool or "list" in sub_tool or sub_tool == _LOG_TOOL:
            continue
        if any(token in sub_tool for token in ("rule_detail", "get_rule", "app_code", "get_app")):
            return True
    return False


def _log_messages(evidence: list[dict[str, Any]]) -> list[str]:
    messages: list[str] = []
    for row in evidence:
        if not isinstance(row, dict) or _sub_tool(row) != _LOG_TOOL:
            continue
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        logs = details.get("logs")
        if not isinstance(logs, list):
            continue
        for item in logs:
            if isinstance(item, dict) and item.get("message"):
                messages.append(str(item["message"]))
    return messages


def _structured_one_sided_trigger_sample(
    evidence: list[dict[str, Any]],
) -> tuple[bool, bool]:
    """Return (structured_samples_seen, any_sample_all_on_qualifying_side)."""

    seen = False
    for row in evidence:
        if not isinstance(row, dict) or _sub_tool(row) != _LOG_TOOL:
            continue
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        samples = details.get("thresholdSamples")
        if not isinstance(samples, list):
            continue
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            values = sample.get("values")
            if not isinstance(values, list) or len(values) < 2:
                continue
            seen = True
            if sample.get("allQualifying") is True:
                return True, True
    return seen, False


def _one_sided_trigger_sample(evidence: list[dict[str, Any]]) -> bool:
    """Detect repeated qualifying reports without evidence of threshold crossings.

    Prefer the compact full-result `thresholdSamples` proof carried by the log
    evidence receipt. Fall back to the retained log excerpt for older receipts and
    unit fixtures that predate the structured sample.
    """

    structured_seen, structured_one_sided = _structured_one_sided_trigger_sample(
        evidence
    )
    if structured_seen:
        return structured_one_sided

    thresholds: dict[str, tuple[str, float]] = {}
    values: dict[str, list[float]] = {}
    for message in _log_messages(evidence):
        parts = message.split("|", 3)
        if len(parts) < 4:
            continue
        prefix = "|".join(parts[:3])
        body = parts[3]
        triggered = re.search(
            r"Triggered:.*?reported\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)",
            body,
            re.IGNORECASE,
        )
        if triggered:
            thresholds[prefix] = (triggered.group(1), float(triggered.group(2)))
        event_value = re.search(
            r"^(?:Wait\s+)?Event:.*?(-?\d+(?:\.\d+)?)\s*$",
            body,
            re.IGNORECASE,
        )
        if event_value:
            values.setdefault(prefix, []).append(float(event_value.group(1)))

    for prefix, (operator, threshold) in thresholds.items():
        observed = values.get(prefix, [])
        if len(observed) < 2:
            continue
        if operator == ">=" and all(value >= threshold for value in observed):
            return True
        if operator == ">" and all(value > threshold for value in observed):
            return True
        if operator == "<=" and all(value <= threshold for value in observed):
            return True
        if operator == "<" and all(value < threshold for value in observed):
            return True
    return False


def guard_performance_log_causality(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Localize unsupported log->performance claims and exact ungrounded edits."""

    original = str(message or "")
    if not original or not performance_validation_needed(evidence):
        return original, False

    corrected = _ROOT_CAUSE_LOG_HEADING.sub(
        "### Recent log observations (not proven performance causes)",
        original,
    )
    corrected = _LOG_CAUSE_PREAMBLE.sub(
        "The recent logs show activity patterns; they are observations, not proven causes of the measured performance totals:",
        corrected,
    )
    corrected = _CLAUSAL_PERF_CAUSE.sub(
        "; the recent logs show repeated activity, but they do not establish that it causes the measured performance result.",
        corrected,
    )
    corrected = _SENTENCE_PERF_CAUSE.sub(
        "The recent logs show this activity, but they do not establish that it causes the measured performance result.",
        corrected,
    )
    corrected = _HYPOTHESIS_PERF_LINK.sub(
        "This is a hypothesis worth investigating, but the recent logs do not establish it as the cause of the measured performance result.",
        corrected,
    )
    corrected = _OVERLOAD_SOURCE_SUGGESTION.sub(
        "This is a plausible hypothesis to verify, not a proven source of the measured performance load.",
        corrected,
    )

    if _one_sided_trigger_sample(evidence):
        corrected = _THRESHOLD_OSCILLATION.sub(
            "reporting qualifying values without evidence of threshold crossing",
            corrected,
        )
        corrected = _ONE_SIDED_FLUCTUATION_CLAUSE.sub(
            "The sampled trigger values in the recent logs stayed on one qualifying side of the threshold;",
            corrected,
        )

    if not _has_rule_configuration_evidence(evidence):
        lines: list[str] = []
        for line in corrected.splitlines():
            if (
                _RULE_EDIT_LINE.search(line) or _RULE_PRESCRIPTION_LINE.search(line)
            ) and any(
                token in line.casefold()
                for token in (
                    "rule",
                    "trigger",
                    "stays that way",
                    "debounce",
                    "threshold",
                    "larger gap",
                    "gap between",
                )
            ):
                prefix = "* " if line.lstrip().startswith("*") else ""
                line = (
                    prefix
                    + "**Inspect the cited automation configuration:** Recent logs can prove repeated execution, but this turn did not read the rule/app configuration needed to prescribe an exact trigger, threshold, debounce, gap, or duration edit."
                )
            lines.append(line)
        corrected = "\n".join(lines)

    return corrected, corrected != original


__all__ = [
    "guard_performance_log_causality",
    "performance_validation_needed",
]
