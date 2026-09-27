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
_CONFIRMED_HYPOTHESIS_LABEL = re.compile(r"(?i)\bConfirmed\s+Hypothesis\b")
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
_NOUN_PERF_CAUSE = re.compile(
    rf"(?i)\b(?:this|that|it)\s+(?:is|was)\s+(?:the\s+)?"
    rf"(?:(?:primary|main|major|significant|direct)\s+)?"
    rf"(?:driver|cause|source|contributor)\s+(?:for|of|to|behind)\s+"
    rf"(?:the\s+)?(?:high\s+)?{_PERF_TERM}[^.!?\n]*(?:[.!?]|$)"
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

_CONFIG_EDIT_LINE = re.compile(
    r"(?i)^(?=.*\b(?:edit|modify|change|add|include|set|setting|adjust|increase|decrease|"
    r"raise|lower|reduce|lengthen|shorten)\b)"
    r"(?=.*\b(?:trigger|triggering|threshold|debounce|duration|stays that way|"
    r"hysteresis|blind time|occupancy timeout|polling intervals?|reporting intervals?|"
    r"polling frequency|reporting frequency|reporting thresholds?|config(?:uration)? pushes?|"
    r"gap between trigger actions|larger gap)\b).*$"
)
_CONFIG_PRESCRIPTION_LINE = re.compile(
    r"(?i)^(?=.*\b(?:need(?:s|ed)?|should|must|require(?:s|d)?|increase|decrease|"
    r"add|include|set|setting|change|modify|edit|adjust|raise|lower|reduce|"
    r"lengthen|shorten)\b)"
    r"(?=.*\b(?:debounce|threshold|trigger(?:ing)?|duration|stays that way|hysteresis|"
    r"blind time|occupancy timeout|polling intervals?|reporting intervals?|polling frequency|"
    r"reporting frequency|reporting thresholds?|config(?:uration)? pushes?|"
    r"gap between trigger actions|larger gap)\b).*$"
)
_IMPLEMENTATION_PRESCRIPTION_LINE = re.compile(
    r"(?i)^(?=.*\b(?:ensure|use|switch|configure|set|increase|decrease|raise|lower|"
    r"add|change|modify|edit|adjust)\b)"
    r"(?=.*\b(?:async(?:hronous(?:ly)?)?|synchronous(?:ly)?|timeouts?|retries?|"
    r"reconnect(?:ion|ions|s|ing)?|blocking network calls?)\b).*$"
)
_NUMERIC_TUNING_LINE = re.compile(
    r"(?i)^(?=.*\b(?:threshold|interval|frequency|timeout|blind time|occupancy timeout|"
    r"debounce|duration)\b)(?=.*\b(?:e\.g\.|instead|setting|set|longer|shorter)\b)"
    r"(?=.*\b\d+(?:\.\d+)?\s*(?:w|%|ms|s|sec(?:ond)?s?|m|min(?:ute)?s?|h|hours?)\b).*$"
)
_RULE_CADENCE_PRESCRIPTION_LINE = re.compile(
    r"(?i)^(?=.*\b(?:ensure|change|reduce|adjust|avoid)\b)(?=.*\brules?\b)"
    r"(?=.*\bevery\s+\d+(?:\.\d+)?\s*(?:ms|s|sec(?:ond)?s?|m|min(?:ute)?s?|h|hours?)\b).*$"
)
_RECOMMENDATION_PREFIX = re.compile(r"^(\s*\*\s+\*\*[^*]+\*\*:\s*)")
_ACTION_SECTION_HEADING = re.compile(
    r"(?im)^#{1,6}\s*(?:recommended\s+optimizations?|recommendations?|"
    r"grounded\s+next\s+actions?|next\s+actions?|what\s+to\s+do\s+next)\b"
)
_PERFORMANCE_SECTION_HEADING = re.compile(
    r"(?im)^#{1,6}\s*(?:potential\s+(?:app|device)\s+culprits?|"
    r"(?:top|primary)\s+resource\s+consumers?|performance\s+outliers?|"
    r"observations\s*&\s*hypotheses)\b"
)
_MECHANISM_KEYWORD = re.compile(
    r"(?i)\b(?:network timeouts?|slow api responses?|cloud polling|frequent polling|"
    r"polling|config(?:uration)? pushes?|pushing configurations?|retries?|"
    r"reconnect(?:ion|ions|s|ing)?|blocking network calls?|block hub execution threads?)\b"
)
_MECHANISM_INFERENCE = re.compile(
    r"(?i)\b(?:often indicates?|suggests?|strongly suggests?|likely due to|probably due to)\b"
)
_LIKELY_DUE_MECHANISM_CLAUSE = re.compile(
    r"(?i),\s*(?:likely|probably)\s+due\s+to\s+[^.!?\n]*(?:[.!?]|$)"
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


def _has_performance_evidence(evidence: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(row, dict)
        and _successful(row)
        and _sub_tool(row) == _PERFORMANCE_TOOL
        for row in evidence
    )


def _has_log_evidence(evidence: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(row, dict)
        and _successful(row)
        and _sub_tool(row) == _LOG_TOOL
        for row in evidence
    )


def performance_validation_needed(evidence: list[dict[str, Any]]) -> bool:
    """True for the narrower log-to-performance causality validation path."""

    return _has_performance_evidence(evidence) and _has_log_evidence(evidence)


def _has_configuration_evidence(evidence: list[dict[str, Any]]) -> bool:
    """Recognize explicit rule/app/device settings or implementation reads, never lists/logs."""

    for row in evidence:
        if not isinstance(row, dict) or not _successful(row):
            continue
        kind = str(row.get("evidence_kind") or "").casefold()
        if any(
            token in kind
            for token in ("configuration", "preferences", "settings", "code", "implementation")
        ):
            return True
        sub_tool = _sub_tool(row).casefold()
        if not sub_tool or "list" in sub_tool or sub_tool == _LOG_TOOL:
            continue
        if any(
            token in sub_tool
            for token in (
                "rule_detail",
                "get_rule",
                "app_code",
                "get_app",
                "driver_code",
                "device_code",
                "get_driver",
                "get_device_code",
                "device_config",
                "device_preferences",
                "get_preferences",
                "get_settings",
                "read_settings",
            )
        ):
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
    """Detect repeated qualifying reports without evidence of threshold crossings."""

    structured_seen, structured_one_sided = _structured_one_sided_trigger_sample(evidence)
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


def _configuration_guidance(text: str) -> str:
    folded = text.casefold()
    if any(token in folded for token in ("blind time", "occupancy timeout")):
        return (
            "Inspect the cited sensor configuration first. Recent activity can justify a tuning review, "
            "but this turn did not read the device settings needed to prescribe an exact blind-time or "
            "occupancy-timeout change."
        )
    if any(
        token in folded
        for token in (
            "polling interval",
            "polling intervals",
            "reporting interval",
            "reporting intervals",
            "polling frequency",
            "reporting frequency",
            "reporting threshold",
            "reporting thresholds",
            "config push",
            "config pushes",
            "configuration push",
            "configuration pushes",
        )
    ):
        return (
            "Inspect the cited integration/device configuration first. Recent activity can justify a tuning review, "
            "but this turn did not read the relevant settings needed to prescribe an exact polling/reporting "
            "threshold, interval, or frequency."
        )
    if any(
        token in folded
        for token in (
            "asynchronous",
            "async ",
            "synchronous",
            "timeout",
            "retry",
            "retries",
            "reconnect",
            "blocking network",
        )
    ):
        return (
            "Inspect the cited integration implementation/configuration first. The measured latency can justify "
            "investigation, but this turn did not read the relevant driver/app code or settings needed to prescribe "
            "async/sync, timeout, retry, or reconnect changes."
        )
    if any(token in folded for token in ("rule", "automation", "trigger", "hysteresis")):
        return (
            "Inspect the cited automation configuration first. Recent activity can prove repeated execution, "
            "but this turn did not read the rule/app configuration needed to prescribe an exact trigger, "
            "threshold, debounce, hysteresis, gap, cadence, or duration edit."
        )
    return (
        "Inspect the cited component configuration first. Recent activity can justify a tuning review, "
        "but this turn did not read the relevant settings needed to prescribe an exact numeric configuration change."
    )


def _configuration_replacement(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("|") and stripped.endswith("|"):
        cells = [cell.strip() for cell in stripped[1:-1].split("|")]
        if len(cells) >= 2:
            cells[1] = _configuration_guidance(line)
            return "| " + " | ".join(cells) + " |"

    match = _RECOMMENDATION_PREFIX.match(line)
    if match:
        prefix = match.group(1)
    else:
        prefix = "* " if line.lstrip().startswith("*") else ""
    return prefix + _configuration_guidance(line)


def _needs_configuration_rewrite(line: str) -> bool:
    return bool(
        _CONFIG_EDIT_LINE.search(line)
        or _CONFIG_PRESCRIPTION_LINE.search(line)
        or _IMPLEMENTATION_PRESCRIPTION_LINE.search(line)
        or _NUMERIC_TUNING_LINE.search(line)
        or _RULE_CADENCE_PRESCRIPTION_LINE.search(line)
    )


def _localize_mechanism_text(text: str) -> str:
    """Downgrade implementation mechanisms that performance totals do not prove."""

    pieces = re.split(r"(?<=[.!?])(\s+)", text)
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not sentence:
            continue

        def _clause_replacement(match: re.Match[str]) -> str:
            clause = match.group(0)
            if not _MECHANISM_KEYWORD.search(clause):
                return clause
            return (
                "; the implementation cause of that measured load is not established "
                "by the current performance statistics."
            )

        localized = _LIKELY_DUE_MECHANISM_CLAUSE.sub(_clause_replacement, sentence)
        comparable = re.sub(r"[*_`]", "", localized)
        if (
            localized == sentence
            and _MECHANISM_INFERENCE.search(comparable)
            and _MECHANISM_KEYWORD.search(comparable)
        ):
            localized = (
                "This is an implementation hypothesis worth investigating; the current performance statistics "
                "do not establish whether timeouts, API latency, polling/config pushes, retries, reconnects, "
                "or another implementation mechanism is responsible."
            )
        pieces[index] = localized
    return "".join(pieces)


def _guard_unproven_implementation_mechanisms(message: str) -> str:
    lines: list[str] = []
    trailing_newline = message.endswith("\n")
    for line in message.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped[1:-1].split("|")]
            if len(cells) >= 2:
                cells[1] = _localize_mechanism_text(cells[1])
                line = "| " + " | ".join(cells) + " |"
        else:
            line = _localize_mechanism_text(line)
        lines.append(line)
    corrected = "\n".join(lines)
    if trailing_newline:
        corrected += "\n"
    return corrected


def _ensure_grounded_next_actions(message: str) -> str:
    """Keep diagnostic-style performance answers actionable without inventing tuning."""

    text = str(message or "")
    if not text or _ACTION_SECTION_HEADING.search(text):
        return text
    if not _PERFORMANCE_SECTION_HEADING.search(text):
        return text
    return (
        text.rstrip()
        + "\n\n### Grounded Next Actions\n"
        + "* **High per-call latency:** Inspect the same high-latency app/driver implementation and settings first; "
        + "only prescribe async/sync, timeout, retry, or reconnect changes after that code/configuration has been read.\n"
        + "* **High call volume:** Inspect the same high-volume component's schedules, subscriptions, polling, or event cadence first; "
        + "only prescribe a specific threshold/interval/frequency change after its current configuration has been read."
    )


def guard_performance_log_causality(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Validate performance synthesis, with log-specific causality checks when logs exist."""

    original = str(message or "")
    if not original or not _has_performance_evidence(evidence):
        return original, False

    corrected = original
    has_logs = _has_log_evidence(evidence)
    has_configuration = _has_configuration_evidence(evidence)

    if has_logs:
        corrected = _ROOT_CAUSE_LOG_HEADING.sub(
            "### Recent log observations (not proven performance causes)",
            corrected,
        )
        corrected = _CONFIRMED_HYPOTHESIS_LABEL.sub(
            "Hypothesis (cause unproven)",
            corrected,
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
        corrected = _NOUN_PERF_CAUSE.sub(
            "The recent logs show this activity, but they do not establish that it is a primary cause or driver of the measured performance result.",
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

    if not has_configuration:
        corrected = _guard_unproven_implementation_mechanisms(corrected)
        lines: list[str] = []
        line_changed = False
        trailing_newline = corrected.endswith("\n")
        for line in corrected.splitlines():
            replacement = _configuration_replacement(line) if _needs_configuration_rewrite(line) else line
            if replacement != line:
                line_changed = True
            lines.append(replacement)
        if line_changed:
            corrected = "\n".join(lines)
            if trailing_newline:
                corrected += "\n"

    corrected = _ensure_grounded_next_actions(corrected)
    return corrected, corrected != original


__all__ = [
    "guard_performance_log_causality",
    "performance_validation_needed",
]
