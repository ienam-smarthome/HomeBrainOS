from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from request_metrics import increment_active_metric


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
_GENERIC_NAME_TOKENS = {
    "bulb",
    "device",
    "lamp",
    "light",
    "meter",
    "outlet",
    "plug",
    "sensor",
    "socket",
    "switch",
    "thermostat",
}


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    target: dict[str, Any] | None
    matched_name: str | None
    confidence: float
    alternatives: tuple[str, ...]
    reason: str


def _plain_text(value: Any) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", text)
    for word, digit in _NUMBER_WORDS.items():
        text = re.sub(rf"\b{word}\b", digit, text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def normalized_name(value: Any) -> str:
    return _plain_text(value).replace(" ", "")


def targeted_name_variants(value: Any, *, limit: int = 4) -> list[str]:
    """Build bounded legacy lookup variants using shared name normalization."""

    tokens = _plain_text(value).split()
    if not tokens:
        return []
    compact_tokens: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if (
            len(token) == 1
            and token.isalpha()
            and index + 1 < len(tokens)
            and tokens[index + 1].isdigit()
        ):
            compact_tokens.append(token + tokens[index + 1])
            index += 2
            continue
        compact_tokens.append(token)
        index += 1
    candidates = (
        " ".join(tokens),
        "-".join(compact_tokens),
        "-".join(tokens),
        next(
            (
                token
                for token in compact_tokens
                if any(character.isdigit() for character in token)
            ),
            "",
        ),
    )
    variants: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants[: max(1, int(limit))]


def _semantic_name(value: Any) -> str:
    """Normalize speech variants that omit an already-known device kind."""

    generic_kind_tokens = {
        "bulb", "device", "lamp", "light", "outlet", "plug", "socket", "switch",
    }
    return "".join(
        token
        for token in _plain_text(value).split()
        if token not in generic_kind_tokens
    )


def _tokens(value: Any) -> set[str]:
    return set(_plain_text(value).split())


def _device_names(device: dict[str, Any]) -> list[str]:
    values = []
    for field in _NAME_FIELDS:
        value = str(device.get(field) or "").strip()
        if value and value not in values:
            values.append(value)
    return values


def _specific_tokens(value: Any) -> set[str]:
    return _tokens(value) - _GENERIC_NAME_TOKENS


def _specific_tokens_compatible(requested: str, candidate: str) -> bool:
    """Reject matches that agree only on a generic device-kind suffix."""

    wanted = _specific_tokens(requested)
    actual = _specific_tokens(candidate)
    if not wanted:
        return True
    return wanted.issubset(actual)


def _score(requested: str, candidate: str) -> float:
    wanted = normalized_name(requested)
    actual = normalized_name(candidate)
    if not wanted or not actual:
        return 0.0
    if wanted == actual:
        return 1.0
    length_ratio = min(len(wanted), len(actual)) / max(len(wanted), len(actual))
    if (
        length_ratio >= 0.65
        and (actual.startswith(wanted) or wanted.startswith(actual))
    ):
        score = 0.94
    else:
        sequence = SequenceMatcher(None, wanted, actual).ratio()
        wanted_tokens = _tokens(requested)
        actual_tokens = _tokens(candidate)
        if not wanted_tokens or not actual_tokens:
            score = sequence
        else:
            intersection = len(wanted_tokens & actual_tokens)
            union = len(wanted_tokens | actual_tokens)
            jaccard = intersection / union
            containment = intersection / len(wanted_tokens)
            score = max(sequence, (sequence + jaccard) / 2, containment * 0.9)
    wanted_numbers = set(re.findall(r"\d+", wanted))
    actual_numbers = set(re.findall(r"\d+", actual))
    if wanted_numbers and actual_numbers and wanted_numbers != actual_numbers:
        score = max(0.0, score - 0.30)
    if not _specific_tokens_compatible(requested, candidate):
        score = min(score, 0.69)
    return score


def _ambiguous_resolution(
    *,
    confidence: float,
    alternatives: tuple[str, ...],
    reason: str,
) -> CandidateResolution:
    increment_active_metric("device_resolution_ambiguous")
    return CandidateResolution(None, None, confidence, alternatives, reason)


def resolve_device_candidate(
    requested: str,
    candidates: list[dict[str, Any]],
    *,
    unique_threshold: float = 0.72,
    ranked_threshold: float = 0.86,
    margin: float = 0.12,
) -> CandidateResolution:
    """Resolve a speech-derived name without blindly choosing the closest."""

    wanted = normalized_name(requested)
    exact_matches: list[tuple[str, dict[str, Any]]] = []
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for device in candidates:
        names = _device_names(device)
        if not names:
            continue
        exact_name = next(
            (name for name in names if normalized_name(name) == wanted),
            None,
        )
        if exact_name is not None:
            exact_matches.append((exact_name, device))
        best_name = max(names, key=lambda name: _score(requested, name))
        ranked.append((_score(requested, best_name), best_name, device))
    if len(exact_matches) == 1:
        exact_name, exact_device = exact_matches[0]
        return CandidateResolution(
            exact_device,
            exact_name,
            1.0,
            (exact_name,),
            "exact normalized name",
        )
    if len(exact_matches) > 1:
        exact_alternatives = tuple(name for name, _device in exact_matches[:3])
        return _ambiguous_resolution(
            confidence=1.0,
            alternatives=exact_alternatives,
            reason=(
                f"{requested!r} matches multiple devices exactly; the candidates are "
                f"{', '.join(exact_alternatives)}."
            ),
        )
    semantic_wanted = _semantic_name(requested)
    contextual_matches: list[tuple[str, dict[str, Any]]] = []
    for _score_value, name, device in ranked:
        room = str(device.get("roomName") or device.get("room") or "").strip()
        if (
            room
            and semantic_wanted
            and _semantic_name(f"{room} {name}") == semantic_wanted
        ):
            contextual_matches.append((name, device))
    if len(contextual_matches) == 1:
        contextual_name, contextual_device = contextual_matches[0]
        return CandidateResolution(
            contextual_device,
            contextual_name,
            0.99,
            (contextual_name,),
            "exact semantic room and device name",
        )
    semantic_matches = [
        (name, device)
        for _score_value, name, device in ranked
        if semantic_wanted and _semantic_name(name) == semantic_wanted
    ]
    if len(semantic_matches) == 1:
        semantic_name, semantic_device = semantic_matches[0]
        return CandidateResolution(
            semantic_device,
            semantic_name,
            0.98,
            (semantic_name,),
            "exact semantic name with device-kind token omitted",
        )
    ranked.sort(key=lambda item: (-item[0], item[1].casefold()))
    alternatives = tuple(item[1] for item in ranked[:3])
    if not ranked:
        return CandidateResolution(
            None, None, 0.0, (), f"No candidate matched {requested!r}."
        )
    top_score, top_name, top_device = ranked[0]
    if len(ranked) == 1:
        if top_score >= unique_threshold:
            return CandidateResolution(
                top_device,
                top_name,
                top_score,
                alternatives,
                "unique inventory candidate",
            )
        return CandidateResolution(
            None,
            None,
            top_score,
            alternatives,
            f"The only candidate was not similar enough to {requested!r}.",
        )
    second_score = ranked[1][0]
    if top_score >= ranked_threshold and top_score - second_score >= margin:
        return CandidateResolution(
            top_device,
            top_name,
            top_score,
            alternatives,
            "high-confidence ranked candidate",
        )
    return _ambiguous_resolution(
        confidence=top_score,
        alternatives=alternatives,
        reason=(
            f"{requested!r} is ambiguous; the closest candidates are "
            f"{', '.join(alternatives)}."
        ),
    )


__all__ = [
    "CandidateResolution",
    "normalized_name",
    "resolve_device_candidate",
    "targeted_name_variants",
]
