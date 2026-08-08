from __future__ import annotations

import re
from typing import Any


_CONTEXTUAL_ATTRIBUTE = re.compile(
    r"^\s*(?:what(?:'s|\s+is)|show|tell\s+me)\s+(?:me\s+)?(?:the\s+)?"
    r"(?:current\s+)?(?:value\s+of\s+)?(?:its|it'?s|that(?:\s+device)?'?s)\s+"
    r"(?:current\s+)?(?P<attribute>temperature|humidity|battery|power)\s*[?.!]*\s*$",
    re.I,
)
_NAMED_ATTRIBUTE = re.compile(
    r"^\s*(?:what(?:'s|\s+is)|show(?:\s+me)?|tell\s+me)\s+(?:the\s+)?"
    r"(?P<name>.+?)\s+(?:current\s+)?"
    r"(?P<attribute>temperature|humidity|battery|power)\s*[?.!]*\s*$",
    re.I,
)
_BARE_ATTRIBUTE = re.compile(
    r"^\s*(?:(?:what(?:'s|\s+is)|show(?:\s+me)?|tell\s+me)\s+(?:me\s+)?"
    r"(?:the\s+)?)?(?:current\s+)?"
    r"(?P<attribute>temperature|humidity|battery|power)\s*[?.!]*\s*$",
    re.I,
)
_DEVICE_SELECTION = re.compile(
    r"^\s*(?:(?:select|use|choose)\s+|i\s+mean\s+)?(?:the\s+)?"
    r"(?P<name>.+?)\s*[?.!]*\s*$",
    re.I,
)
_MOTION_ACTIVITY = re.compile(
    r"^\s*(?:(?P<count>how\s+many)|which|show(?:\s+me)?)\s+"
    r"motion\s+sensors?\s+(?:are\s+)?(?P<state>active|inactive)\s*[?.!]*\s*$",
    re.I,
)
_HISTORY_TERMS = re.compile(
    r"\b(?:history|historical|when|last|ago|before|after|changed?|over\s+the\s+last|yesterday|today)\b",
    re.I,
)
# parse_named_attribute's own regex backtracks "What's the temperature?"
# into name="the", attribute="temperature" when there is no real device name
# at all -- its optional "(?:the\s+)?" lead-in and the required-nonempty
# name group can't both be satisfied by "the temperature" without giving
# "the" to one or the other, and the engine gives it to name. That used to
# route a bare "what's the X" reading straight into device-name resolution
# for the literal word "the", which only produced a correct answer by
# accident when a device happened to be labelled after the attribute itself.
# Bare articles belong with the pronoun-only exclusions below, not treated
# as a real device name.
_PRONOUN_NAMES = {
    "it", "its", "it's", "that", "that device", "this", "this device",
    "the", "a", "an",
}
_SELECTION_PREFIX = re.compile(r"^\s*(?:select|use|choose|i\s+mean)\b", re.I)


def clean_choice_label(value: str) -> str:
    """Remove presentation-only conjunctions and articles from a choice label."""

    return re.sub(r"^(?:(?:or|and)\s+)?(?:the|a|an)\s+", "", value.strip(), flags=re.I)


def parse_contextual_attribute(prompt: str) -> str | None:
    """Return a current-state attribute for a pronoun-only follow-up."""

    if _HISTORY_TERMS.search(prompt):
        return None
    match = _CONTEXTUAL_ATTRIBUTE.fullmatch(prompt)
    return match.group("attribute").casefold() if match is not None else None


def parse_named_attribute(prompt: str) -> tuple[str, str] | None:
    """Return an explicit current-state target and attribute.

    Room labels such as ``Bedroom 1`` intentionally remain on this deterministic
    path. Capability filtering in the production agent then decides whether one
    source can answer or whether multiple valid sources must be offered as
    clarification choices. Only historical and pronoun-only wording is excluded.
    """

    if _HISTORY_TERMS.search(prompt):
        return None
    match = _NAMED_ATTRIBUTE.fullmatch(prompt)
    if match is None:
        return None
    name = clean_choice_label(match.group("name")).strip()
    if not name or name.casefold() in _PRONOUN_NAMES:
        return None
    return name, match.group("attribute").casefold()


def parse_bare_attribute(prompt: str) -> str | None:
    """Return a current-state attribute for a bare, unqualified reading word.

    Handles the plain single-word form ("temperature", "humidity") and its
    minimal question forms ("what's the temperature") that carry no device
    name at all -- deliberately narrower than ``parse_named_attribute``,
    which requires a name between the question prefix and the attribute.

    Live-tested regression: this exact bare wording used to fall all the way
    through to the model's tool-selection loop, where the 0.10.370
    weather-routing prompt change only steered it away from
    ``homebrain_weather_snapshot`` probabilistically rather than guaranteeing
    it -- a real live run answered "temperature" from the outdoor forecast
    device while every indoor sensor read something else entirely. Routing
    this deterministically, ahead of the model, removes that risk for the
    bare-word case outright. Prompts mentioning "weather", "outside",
    "outdoor", or "forecast" never reach this parser in practice -- the
    orchestrator's own separate keyword trigger already owns those before
    the model loop runs, and none of that wording matches this pattern
    anyway (only the attribute word itself is permitted before the
    optional trailing punctuation).
    """

    if _HISTORY_TERMS.search(prompt):
        return None
    match = _BARE_ATTRIBUTE.fullmatch(prompt)
    return match.group("attribute").casefold() if match is not None else None


def parse_device_selection(prompt: str) -> str | None:
    """Return an explicit device-selection command without model routing."""

    if _SELECTION_PREFIX.search(prompt) is None:
        return None
    match = _DEVICE_SELECTION.fullmatch(prompt)
    if match is None:
        return None
    name = clean_choice_label(match.group("name")).strip()
    return name or None


def capability_choice_labels(
    requested: str,
    matches: list[dict[str, Any]],
) -> list[str]:
    """Return attribute-capable labels matching every meaningful request token."""

    tokens = re.findall(r"[a-z0-9]+", requested.casefold())
    labels: list[str] = []
    seen: set[str] = set()
    for item in matches:
        label = str(item.get("label") or item.get("name") or "").strip()
        normalized = " ".join(re.findall(r"[a-z0-9]+", label.casefold()))
        if not label or not all(token in normalized.split() for token in tokens):
            continue
        key = label.casefold()
        if key not in seen:
            labels.append(label)
            seen.add(key)
    return labels


def parse_motion_activity(prompt: str) -> tuple[str, bool] | None:
    """Return ``(state, count_only)`` for deterministic motion aggregation."""

    match = _MOTION_ACTIVITY.fullmatch(prompt)
    if match is None:
        return None
    return match.group("state").casefold(), bool(match.group("count"))


def present_attribute(label: str, attribute: str, value: Any, unit: str | None) -> str:
    suffix = unit or ""
    if suffix == "%":
        rendered = f"{value}%"
    elif suffix:
        rendered = f"{value}{suffix}"
    else:
        rendered = str(value)
    return f"{label} {attribute} is {rendered}."


def present_motion_activity(
    matches: list[dict[str, Any]],
    *,
    state: str,
    count_only: bool,
) -> str:
    labels: list[str] = []
    seen: set[str] = set()
    for item in matches:
        label = str(item.get("label") or item.get("name") or "").strip()
        key = label.casefold()
        if label and key not in seen:
            labels.append(label)
            seen.add(key)

    count = len(labels)
    noun = "motion sensor" if count == 1 else "motion sensors"
    verb = "is" if count == 1 else "are"
    if count_only or not labels:
        return f"{count} {noun} {verb} {state}."
    if count == 1:
        joined = labels[0]
    elif count == 2:
        joined = f"{labels[0]} and {labels[1]}"
    else:
        joined = ", ".join(labels[:-1]) + f", and {labels[-1]}"
    return f"{count} {noun} {verb} {state}: {joined}."


__all__ = [
    "capability_choice_labels",
    "clean_choice_label",
    "parse_bare_attribute",
    "parse_contextual_attribute",
    "parse_device_selection",
    "parse_motion_activity",
    "parse_named_attribute",
    "present_attribute",
    "present_motion_activity",
]
