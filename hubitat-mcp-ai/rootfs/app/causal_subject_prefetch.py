"""Deterministic causal-subject prefetch for explicit state-transition questions.

This module does not answer a causal question. It only decides whether the
prompt safely names exactly one known device and explicitly asks why that device
changed one supported binary state. When that narrow structural contract is
met, HomeBrain can gather subject history before the first provider round.

The final causal explanation still comes from the normal evidence pipeline and
FinalAnswerCoordinator.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Any


_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}
_NAME_FIELDS = ("label", "name", "displayName", "deviceLabel")
_GENERIC_SINGLE_TOKENS = {
    "device",
    "light",
    "lamp",
    "sensor",
    "socket",
    "switch",
    "plug",
    "outlet",
    "thermostat",
}
_SWITCH_TRANSITIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:turn|turned|switch|switched|power|powered)"
            r"(?:\s+itself)?\s+on\b",
            re.I,
        ),
        "on",
    ),
    (
        re.compile(
            r"\b(?:turn|turned|switch|switched|power|powered)"
            r"(?:\s+itself)?\s+off\b",
            re.I,
        ),
        "off",
    ),
    (
        re.compile(r"\b(?:came|come)(?:\s+back)?\s+on\b", re.I),
        "on",
    ),
    (
        re.compile(r"\b(?:went|go)(?:\s+back)?\s+off\b", re.I),
        "off",
    ),
    (
        re.compile(r"\bshut(?:\s+itself)?(?:\s+down|\s+off)\b", re.I),
        "off",
    ),
    (
        re.compile(r"\bstart(?:ed)?\s+running\b", re.I),
        "on",
    ),
    (
        re.compile(r"\bstop(?:ped)?\s+running\b", re.I),
        "off",
    ),
)


def _switch_transition(prompt: str) -> str | None:
    text = str(prompt or "")
    for pattern, transition in _SWITCH_TRANSITIONS:
        if pattern.search(text) is not None:
            return transition
    return None


@dataclass(frozen=True, slots=True)
class CausalSubjectSeed:
    name: str
    attribute: str
    transition: str
    confidence: float
    matched_text: str
    target: dict[str, Any]


def _tokens(value: Any) -> list[str]:
    text = str(value or "").casefold()
    for word, digit in _NUMBER_WORDS.items():
        text = re.sub(rf"\b{word}\b", digit, text)
    return re.findall(r"[a-z0-9]+", text)


def _names(device: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for field in _NAME_FIELDS:
        value = str(device.get(field) or "").strip()
        if value and value not in result:
            result.append(value)
    return result


def _identity_key(device: dict[str, Any]) -> str:
    stable = str(device.get("id") or device.get("deviceId") or "").strip()
    if stable:
        return f"id:{stable}"
    names = _names(device)
    return f"name:{names[0].casefold()}" if names else ""


def _normalized_capabilities(device: dict[str, Any]) -> set[str]:
    raw = device.get("capabilities")
    values = raw if isinstance(raw, list) else []
    result: set[str] = set()
    for item in values:
        if isinstance(item, dict):
            value = item.get("name") or item.get("capability")
        else:
            value = item
        normalized = re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
        if normalized:
            result.add(normalized)
    return result


def _normalized_attributes(device: dict[str, Any]) -> set[str]:
    raw = device.get("attributes")
    result: set[str] = set()
    if isinstance(raw, dict):
        values = raw.keys()
    elif isinstance(raw, list):
        values = raw
    else:
        values = ()
    for item in values:
        if isinstance(item, dict):
            value = item.get("name") or item.get("attribute")
        else:
            value = item
        normalized = re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
        if normalized:
            result.add(normalized)
    return result


def _commands(device: dict[str, Any]) -> set[str]:
    raw = device.get("commands")
    values = raw if isinstance(raw, list) else []
    result: set[str] = set()
    for item in values:
        if isinstance(item, dict):
            value = item.get("name") or item.get("command")
        else:
            value = item
        normalized = str(value or "").strip().casefold()
        if normalized:
            result.add(normalized)
    return result


def _supports_switch(device: dict[str, Any]) -> bool:
    return bool(
        "switch" in _normalized_attributes(device)
        or "switch" in _normalized_capabilities(device)
        or {"on", "off"}.issubset(_commands(device))
    )


def _window_similarity(name_tokens: list[str], window: list[str]) -> float:
    if not name_tokens or len(name_tokens) != len(window):
        return 0.0
    left = "".join(name_tokens)
    right = "".join(window)
    if left == right:
        return 1.0
    sequence = SequenceMatcher(None, left, right).ratio()
    token_scores = [
        SequenceMatcher(None, wanted, actual).ratio()
        for wanted, actual in zip(name_tokens, window)
    ]
    token_floor = min(token_scores) if token_scores else 0.0
    # A digit mismatch is almost always a different numbered device, not a typo.
    wanted_numbers = {token for token in name_tokens if token.isdigit()}
    actual_numbers = {token for token in window if token.isdigit()}
    if wanted_numbers != actual_numbers:
        return 0.0
    return min(sequence, token_floor + 0.08)


def _best_prompt_match(
    prompt: str,
    identities: list[dict[str, Any]],
) -> tuple[dict[str, Any], str, float] | None:
    prompt_tokens = _tokens(prompt)
    if not prompt_tokens:
        return None

    by_identity: dict[str, tuple[float, str, dict[str, Any]]] = {}
    for device in identities:
        if not isinstance(device, dict):
            continue
        identity = _identity_key(device)
        if not identity:
            continue
        for name in _names(device):
            name_tokens = _tokens(name)
            if not name_tokens or len(name_tokens) > len(prompt_tokens):
                continue
            width = len(name_tokens)
            single = width == 1
            normalized_single = name_tokens[0] if single else ""
            for start in range(len(prompt_tokens) - width + 1):
                window = prompt_tokens[start:start + width]
                score = _window_similarity(name_tokens, window)
                if single:
                    # Exact short labels are safe; fuzzy single-token names need
                    # enough identifying information to avoid matching ordinary
                    # question words to generic device kinds.
                    if score < 1.0 and (
                        len(normalized_single) < 6
                        or normalized_single in _GENERIC_SINGLE_TOKENS
                        or score < 0.92
                    ):
                        continue
                    if score == 1.0 and normalized_single in _GENERIC_SINGLE_TOKENS:
                        continue
                if score < 0.86:
                    continue
                matched = " ".join(window)
                prior = by_identity.get(identity)
                if prior is None or score > prior[0]:
                    by_identity[identity] = (score, matched, device)

    if not by_identity:
        return None

    ranked = sorted(
        by_identity.values(),
        key=lambda item: (-item[0], str(_names(item[2])[:1]).casefold()),
    )
    best_score, matched, best_device = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    if best_score < 0.90:
        return None
    if len(ranked) > 1 and best_score - second_score < 0.12:
        return None
    return best_device, matched, best_score


def causal_subject_seed(
    prompt: str,
    identities: list[dict[str, Any]],
) -> CausalSubjectSeed | None:
    """Return one safe model-free causal history seed, otherwise None.

    This fast path intentionally covers only explicit switch-state transition
    questions. Broader causal questions ("why is the room cold?", "what caused
    this automation?") remain in the normal model tool-selection path.
    """

    transition = _switch_transition(prompt)
    if transition is None:
        return None

    match = _best_prompt_match(prompt, identities)
    if match is None:
        return None
    device, matched_text, confidence = match
    if not _supports_switch(device):
        return None

    canonical = next(iter(_names(device)), "")
    if not canonical:
        return None
    return CausalSubjectSeed(
        name=canonical,
        attribute="switch",
        transition=transition,
        confidence=confidence,
        matched_text=matched_text,
        target=dict(device),
    )


__all__ = ["CausalSubjectSeed", "causal_subject_seed"]
