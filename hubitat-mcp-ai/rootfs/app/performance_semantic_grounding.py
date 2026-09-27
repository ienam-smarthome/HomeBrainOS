"""Semantic grounding helpers for measured performance synthesis.

Keep measured facts intact while preventing unverified implementation mechanisms,
performance-outcome causality, and configuration prescriptions from being promoted
beyond the current-turn evidence.
"""

from __future__ import annotations

import re

_ACTION_SECTION_HEADING = re.compile(
    r"(?i)^\s*(#{1,6})\s*(?:[^\w\n]*\s*)?(?:recommended\s+(?:optimizations?|optimisations?)|"
    r"recommendations?|grounded\s+next\s+actions?|next\s+actions?|what\s+to\s+do\s+next)\b"
)
_ANY_HEADING = re.compile(r"^\s*(#{1,6})\s+")
_TABLE_SEPARATOR = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$")
_BULLET_PREFIX = re.compile(r"^(\s*[*+-]\s+(?:\*\*[^*]+\*\*:\s*)?)(.*)$")

_DIRECTIVE = re.compile(
    r"(?i)\b(?:edit|modify|change|add|include|set|adjust|increase|decrease|raise|lower|"
    r"reduce|reduced|reducing|lengthen|shorten|ensure|use|switch|configure|review|"
    r"inspect|investigate|check|verify|audit|consider)\b"
)
_CONFIG_TOPIC = re.compile(
    r"(?i)\b(?:trigger(?:ing)?|thresholds?|debounce|duration|hysteresis|blind time|"
    r"occupancy timeout|polling intervals?|reporting intervals?|polling frequency|"
    r"reporting frequency|reporting thresholds?|config(?:uration)?\s+push(?:es)?|"
    r"gap between trigger actions|larger gap|cadence|async(?:hronous(?:ly)?)?|"
    r"synchronous(?:ly)?|timeouts?|retries?|reconnect(?:ion|ions|s|ing)?)\b"
)
_RULE_EVENT_PRESCRIPTION = re.compile(
    r"(?i)\b(?:ensure|change|reduce|adjust|avoid|audit|review|inspect|check|verify)\b"
    r"[^.!?\n]{0,220}\brules?\b[^.!?\n]{0,220}"
    r"(?:every\s+time|each\s+time|on\s+every|whenever)\b[^.!?\n]{0,180}"
    r"(?:power|sensor|event|value|reading)"
)
_NUMERIC_TUNING = re.compile(
    r"(?i)\b(?:threshold|interval|frequency|timeout|blind time|occupancy timeout|"
    r"debounce|duration|cadence)\b[^.!?\n]{0,160}"
    r"\b\d+(?:\.\d+)?\s*(?:w|%|ms|s|sec(?:ond)?s?|m|min(?:ute)?s?|h|hours?)\b"
)

_MECHANISM = re.compile(
    r"(?i)\b(?:network timeouts?|slow api responses?|api latency|cloud polling|"
    r"frequent polling|polling|config(?:uration)?\s+push(?:es)?|pushing configurations?|"
    r"retries?|reconnect(?:ion|ions|s|ing)?|blocking network calls?|"
    r"block(?:ing)? hub execution threads?|execution threads?|frequent reporting)\b"
)
_ASSERTIVE_MECHANISM_LINK = re.compile(
    r"(?i)\b(?:often|typically|commonly|generally)?\s*indicat(?:e|es|ed|ing)\b|"
    r"\b(?:strongly\s+)?suggest(?:s|ed|ing)?\b|"
    r"\b(?:likely|probably)\s+due\s+to\b|"
    r"\b(?:is|are|was|were)\s+(?:a\s+)?(?:common|primary|main|major|direct)\s+cause\b|"
    r"\bwhich\s+can\s+(?:block|cause|lead|result)\b|"
    r"\bcan\s+(?:block|cause|lead\s+to|result\s+in)\b"
)
_CONDITIONAL_MARKER = re.compile(
    r"(?i)\b(?:if|may|might|could|possible|possibly|plausible|hypothesis|worth investigating)\b"
)

_PERFORMANCE_OUTCOME = re.compile(
    r"(?i)\b(?:hub\s+lag|lag|stutter|sluggish(?:ness)?|instability|"
    r"event[- ]bus\s+congestion|congestion|overload|crash(?:es|ing)?)\b"
)
_STRONG_OUTCOME_LINK = re.compile(
    r"(?i)\b(?:primary|main|major|direct)\s+(?:source|cause|driver)\s+(?:of|for)\b|"
    r"\b(?:is|are|was|were)\s+(?:the\s+)?(?:primary|main|major|direct)\s+"
    r"(?:source|cause|driver)\b|"
    r"\b(?:cause|causes|caused|causing|lead\s+to|leads\s+to|result\s+in|results\s+in)\b"
)
_LIKELY_CANDIDATE_OUTCOME = re.compile(
    r"(?i)\b(?:most\s+likely|likely)\s+candidates?\s+to\s+cause\b"
)


def _configuration_guidance(text: str) -> str:
    folded = text.casefold()
    if "blind time" in folded or "occupancy timeout" in folded:
        return (
            "Inspect the cited sensor configuration first. Recent activity can justify a tuning review, "
            "but this turn did not read the device settings needed to prescribe an exact blind-time or "
            "occupancy-timeout change."
        )
    if any(
        token in folded
        for token in (
            "polling interval",
            "reporting interval",
            "polling frequency",
            "reporting frequency",
            "reporting threshold",
            "config push",
            "configuration push",
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
            "async",
            "synchronous",
            "timeout",
            "retry",
            "reconnect",
            "blocking network",
        )
    ):
        return (
            "Inspect the cited integration implementation/configuration first. The measured latency can justify "
            "investigation, but this turn did not read the relevant driver/app code or settings needed to prescribe "
            "async/sync, timeout, retry, or reconnect changes."
        )
    if any(token in folded for token in ("rule", "automation", "trigger", "hysteresis", "cadence")):
        return (
            "Inspect the cited automation configuration first. Recent activity can justify an execution review, "
            "but this turn did not read the rule/app configuration needed to prescribe an exact trigger, "
            "threshold, debounce, hysteresis, gap, cadence, or duration edit."
        )
    return (
        "Inspect the cited component configuration first. Recent activity can justify a tuning review, "
        "but this turn did not read the relevant settings needed to prescribe an exact configuration change."
    )


def _unsafe_recommendation(text: str) -> bool:
    comparable = re.sub(r"[*_`]", "", str(text or ""))
    if _RULE_EVENT_PRESCRIPTION.search(comparable):
        return True
    if _NUMERIC_TUNING.search(comparable) and _DIRECTIVE.search(comparable):
        return True
    return bool(_DIRECTIVE.search(comparable) and _CONFIG_TOPIC.search(comparable))


def _split_sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])(\s+)", text)


def _localize_mechanism_sentence(sentence: str) -> str:
    comparable = re.sub(r"[*_`]", "", sentence)
    if not _MECHANISM.search(comparable):
        return sentence
    if _CONDITIONAL_MARKER.search(comparable) and not re.search(
        r"(?i)\b(?:typically|often|commonly|generally)\s+indicat", comparable
    ):
        return sentence
    link = _ASSERTIVE_MECHANISM_LINK.search(comparable)
    if not link:
        return sentence

    raw_link = _ASSERTIVE_MECHANISM_LINK.search(sentence)
    if raw_link and raw_link.start() > 0:
        prefix = sentence[: raw_link.start()].rstrip(" ,;:-")
        if re.search(
            r"(?i)(?:\d[\d,.]*(?:-\d[\d,.]*)?\s*(?:%|ms|s|sec(?:ond)?s?|mb)|"
            r"\b(?:busy|calls?|call count|execution time|latency|free memory)\b)",
            re.sub(r"[*_`]", "", prefix),
        ):
            return (
                prefix
                + "; the implementation cause of that measured result is not established by the current "
                + "performance statistics."
            )

    return (
        "This is an implementation hypothesis worth investigating; the current performance statistics "
        "do not establish whether timeouts, API latency, polling/config pushes, retries, reconnects, "
        "reporting cadence, or another implementation mechanism is responsible."
    )


def _localize_outcome_sentence(sentence: str) -> str:
    comparable = re.sub(r"[*_`]", "", sentence)
    if not _PERFORMANCE_OUTCOME.search(comparable):
        return sentence
    if _LIKELY_CANDIDATE_OUTCOME.search(comparable):
        return (
            "These are the highest measured consumers to investigate if hub lag or instability occurs; "
            "the current performance statistics do not establish that they will cause those outcomes."
        )
    if not _STRONG_OUTCOME_LINK.search(comparable):
        return sentence
    if _CONDITIONAL_MARKER.search(comparable) and not re.search(
        r"(?i)\b(?:primary|main|major|direct)\s+(?:source|cause|driver)\b", comparable
    ):
        return sentence

    relation = re.search(
        r"(?i)\b(?:is|are|was|were)\s+(?:the\s+)?(?:primary|main|major|direct)\s+"
        r"(?:source|cause|driver)\b|\b(?:primary|main|major|direct)\s+"
        r"(?:source|cause|driver)\s+(?:of|for)\b|\b(?:cause|causes|caused|causing|"
        r"lead\s+to|leads\s+to|result\s+in|results\s+in)\b",
        comparable,
    )
    if relation:
        # Preserve the measured subject before the unsupported causal predicate.
        raw_relation = re.search(
            r"(?i)\b(?:is|are|was|were)\s+(?:the\s+)?(?:primary|main|major|direct)\s+"
            r"(?:source|cause|driver)\b|\b(?:primary|main|major|direct)\s+"
            r"(?:source|cause|driver)\s+(?:of|for)\b|\b(?:cause|causes|caused|causing|"
            r"lead\s+to|leads\s+to|result\s+in|results\s+in)\b",
            sentence,
        )
        if raw_relation and raw_relation.start() > 0:
            prefix = sentence[: raw_relation.start()].rstrip(" ,;:-")
            if prefix:
                return (
                    prefix
                    + "; this is a measured performance concern, but the current statistics do not establish "
                    + "that it causes hub lag, stutter, congestion, or instability."
                )
    return (
        "This is a measured performance concern, but the current statistics do not establish that it causes "
        "hub lag, stutter, congestion, or instability."
    )


def _localize_analysis_text(text: str) -> str:
    pieces = _split_sentences(text)
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not sentence:
            continue
        localized = _localize_mechanism_sentence(sentence)
        localized = _localize_outcome_sentence(localized)
        if _unsafe_recommendation(localized):
            localized = _configuration_guidance(localized)
        pieces[index] = localized
    return "".join(pieces)


def _rewrite_action_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return line
    if _TABLE_SEPARATOR.match(line):
        return line
    if stripped.startswith("|") and stripped.endswith("|"):
        cells = [cell.strip() for cell in stripped[1:-1].split("|")]
        if len(cells) >= 2 and cells[0].casefold() not in {"component", ":---", "---"}:
            if _unsafe_recommendation(cells[1]):
                cells[1] = _configuration_guidance(cells[1])
                return "| " + " | ".join(cells) + " |"
        return line

    bullet = _BULLET_PREFIX.match(line)
    if bullet:
        prefix, body = bullet.groups()
        if _unsafe_recommendation(body):
            return prefix + _configuration_guidance(body)
        return line

    pieces = _split_sentences(line)
    changed = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if sentence and _unsafe_recommendation(sentence):
            pieces[index] = _configuration_guidance(sentence)
            changed = True
    return "".join(pieces) if changed else line


def ground_performance_semantics(message: str) -> str:
    """Ground analysis clauses and action recommendations without erasing measured facts."""

    original = str(message or "")
    if not original:
        return original

    lines: list[str] = []
    in_action_section = False
    action_level: int | None = None
    trailing_newline = original.endswith("\n")

    for line in original.splitlines():
        action_heading = _ACTION_SECTION_HEADING.match(line)
        any_heading = _ANY_HEADING.match(line)
        if action_heading:
            in_action_section = True
            action_level = len(action_heading.group(1))
            lines.append(line)
            continue
        if in_action_section and any_heading and action_level is not None:
            if len(any_heading.group(1)) <= action_level:
                in_action_section = False
                action_level = None

        if in_action_section:
            line = _rewrite_action_line(line)
        else:
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [cell.strip() for cell in stripped[1:-1].split("|")]
                if len(cells) >= 2:
                    cells[1] = _localize_analysis_text(cells[1])
                    line = "| " + " | ".join(cells) + " |"
            else:
                line = _localize_analysis_text(line)
        lines.append(line)

    corrected = "\n".join(lines)
    if trailing_newline:
        corrected += "\n"
    return corrected


__all__ = ["ground_performance_semantics"]
