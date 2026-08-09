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
    # English articles/determiners. A user saying "the fridge" or "turn off
    # a socket" contributes "the"/"a"/"an" as an ordinary token, and unlike
    # a real identifying word, that token can never appear in a device's
    # own label -- so before this fix it was scored as a "specific" token
    # that had to match something, capping an otherwise exact match (e.g.
    # "the fridge" against a device literally labelled "Fridge") down into
    # ambiguous/missing territory. These carry no identifying information
    # about which device is meant, so they belong here alongside the
    # generic device-kind words.
    "the",
    "a",
    "an",
}
_STANDARD_ATTRIBUTE_UNITS = {
    "battery": "%",
    "batterylevel": "%",
    "humidity": "%",
    "power": "W",
    "activepower": "W",
    "powermeter": "W",
    "temperature": "°C",
    "temperaturec": "°C",
}


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    target: dict[str, Any] | None
    matched_name: str | None
    confidence: float
    alternatives: tuple[str, ...]
    reason: str


_LEADING_ARTICLES = ("the", "a", "an")


def _plain_text(value: Any) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", text)
    for word, digit in _NUMBER_WORDS.items():
        text = re.sub(rf"\b{word}\b", digit, text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    # Strip a leading English article ("the fridge" -> "fridge"). This has
    # to happen before scoring, not just before the specific-token
    # compatibility check -- a leading "the"/"a"/"an" still dilutes the
    # underlying SequenceMatcher ratio used for ordinary fuzzy scoring,
    # which is fatal for short labels ("the tv" vs "TV" scores only 0.57,
    # well below the confidence floor, even though it's an exact match
    # once the article is removed). Only strips a genuinely leading
    # article with at least one more word after it, so this never touches
    # a label that is itself just "The" or similar.
    words = text.split(" ")
    if len(words) > 1 and words[0] in _LEADING_ARTICLES:
        text = " ".join(words[1:])
    return text


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


def _normalized_attribute_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _state_items(device: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in (
        device.get("attributes"),
        device.get("states"),
        device.get("currentStates"),
    ):
        if isinstance(raw, list):
            items.extend(item for item in raw if isinstance(item, dict))
    return items


def _attribute_names(device: dict[str, Any]) -> set[str]:
    names = {
        _normalized_attribute_name(key)
        for key, value in device.items()
        if value is not None
    }
    for raw in (
        device.get("attributes"),
        device.get("states"),
        device.get("currentStates"),
    ):
        if isinstance(raw, dict):
            names.update(
                _normalized_attribute_name(key)
                for key, value in raw.items()
                if value is not None
            )
    for item in _state_items(device):
        name = item.get("name") or item.get("attribute")
        value = item.get("currentValue", item.get("value"))
        if name and value is not None:
            names.add(_normalized_attribute_name(name))
    return names


def _measurement_units(device: dict[str, Any]) -> dict[str, str]:
    units: dict[str, str] = {}
    existing = device.get("attributeUnits") or device.get("attribute_units")
    if isinstance(existing, dict):
        units.update(
            {
                str(name): str(unit)
                for name, unit in existing.items()
                if str(name).strip() and str(unit).strip()
            }
        )
    for item in _state_items(device):
        name = item.get("name") or item.get("attribute")
        unit = item.get("unit")
        if name and unit not in {None, ""}:
            units[str(name)] = str(unit)
    present = _attribute_names(device)
    for attribute, unit in _STANDARD_ATTRIBUTE_UNITS.items():
        if attribute in present and not any(
            _normalized_attribute_name(name) == attribute
            for name in units
        ):
            units[attribute] = unit
    return units


def _with_measurement_units(device: dict[str, Any]) -> dict[str, Any]:
    units = _measurement_units(device)
    if not units:
        return device
    enriched = dict(device)
    enriched["attributeUnits"] = units
    return enriched


def _specific_tokens(value: Any) -> set[str]:
    return _tokens(value) - _GENERIC_NAME_TOKENS


def _specific_tokens_ordered(value: Any) -> list[str]:
    return [
        token for token in _plain_text(value).split()
        if token not in _GENERIC_NAME_TOKENS
    ]


def _specific_tokens_compatible(requested: str, candidate: str) -> bool:
    """Allow minor typos but reject matches based only on generic suffixes.

    A device's own label often hyphenates a compound alphanumeric code
    ("Tab-S9-FE") into separate tokens once punctuation is normalised to
    spaces ("tab", "s9", "fe"), but a person typing or speaking the same
    code naturally runs it together as one token ("s9fe") since they never
    think to reproduce the internal hyphen. Neither "s9" nor "fe" alone is
    similar enough to "s9fe" for the ordinary per-token typo tolerance
    below, which wrongly treated an exact code match as barely-compatible
    and capped its score into "ambiguous" territory instead of resolving
    it outright. Also accept a wanted token that appears as a contiguous
    run inside the candidate's concatenated specific tokens (in their
    original order) -- this only fires for the exact code-splitting shape
    above, not for generic fuzzy substring matching, and the length-3
    floor keeps short/coincidental substrings from qualifying.
    """

    wanted = _specific_tokens(requested)
    actual = _specific_tokens(candidate)
    if not wanted:
        return True
    if not actual:
        return False
    actual_joined = "".join(_specific_tokens_ordered(candidate))

    def _token_ok(wanted_token: str) -> bool:
        if any(
            wanted_token == actual_token
            or SequenceMatcher(None, wanted_token, actual_token).ratio() >= 0.80
            for actual_token in actual
        ):
            return True
        return len(wanted_token) >= 3 and wanted_token in actual_joined

    return all(_token_ok(wanted_token) for wanted_token in wanted)


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


def _missing_resolution(
    *,
    confidence: float,
    alternatives: tuple[str, ...],
    reason: str,
) -> CandidateResolution:
    """Record a deterministic no-acceptable-candidate outcome."""

    increment_active_metric("device_resolution_missing")
    return CandidateResolution(None, None, confidence, alternatives, reason)


def _resolved(
    device: dict[str, Any],
    matched_name: str,
    confidence: float,
    alternatives: tuple[str, ...],
    reason: str,
) -> CandidateResolution:
    return CandidateResolution(
        _with_measurement_units(device),
        matched_name,
        confidence,
        alternatives,
        reason,
    )


def resolve_device_candidate(
    requested: str,
    candidates: list[dict[str, Any]],
    *,
    unique_threshold: float = 0.72,
    ranked_threshold: float = 0.86,
    margin: float = 0.12,
    missing_floor: float = 0.70,
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
        return _resolved(
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
        return _resolved(
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
        return _resolved(
            semantic_device,
            semantic_name,
            0.98,
            (semantic_name,),
            "exact semantic name with device-kind token omitted",
        )
    ranked.sort(key=lambda item: (-item[0], item[1].casefold()))
    alternatives = tuple(item[1] for item in ranked[:3])
    if not ranked:
        return _missing_resolution(
            confidence=0.0,
            alternatives=(),
            reason=f"No candidate matched {requested!r}.",
        )
    top_score, top_name, top_device = ranked[0]
    if len(ranked) == 1:
        if top_score >= unique_threshold:
            return _resolved(
                top_device,
                top_name,
                top_score,
                alternatives,
                "unique inventory candidate",
            )
        return _missing_resolution(
            confidence=top_score,
            alternatives=alternatives,
            reason=f"The only candidate was not similar enough to {requested!r}.",
        )
    second_score = ranked[1][0]
    if top_score >= ranked_threshold and top_score - second_score >= margin:
        return _resolved(
            top_device,
            top_name,
            top_score,
            alternatives,
            "high-confidence ranked candidate",
        )
    # A moderate absolute score (below ranked_threshold but still above the
    # missing floor) can still be the unambiguous right answer if nothing
    # else is remotely close -- e.g. a hyphenated device code typed without
    # its hyphens scores lower on raw sequence similarity than an ordinary
    # typo would, even though no other candidate is a plausible match at
    # all. Require a much wider margin than the high-confidence tier above
    # (dominant_margin) to compensate for the lower absolute score before
    # trusting it, so this only fires when the runner-up is clearly not a
    # real contender rather than merely somewhat behind.
    dominant_margin = 0.25
    if top_score >= missing_floor and top_score - second_score >= dominant_margin:
        return _resolved(
            top_device,
            top_name,
            top_score,
            alternatives,
            "dominant ranked candidate despite moderate absolute score",
        )
    if top_score < missing_floor:
        return _missing_resolution(
            confidence=top_score,
            alternatives=alternatives,
            reason=(
                f"No candidate was similar enough to {requested!r}; the "
                f"closest inventory names ({', '.join(alternatives)}) fell "
                "below the confidence floor."
            ),
        )
    # ranked[:3] (built above) can pad this disambiguation list with a
    # candidate far below any real similarity threshold, just because it
    # happened to score third highest across the whole inventory --
    # live-reproduced: "turn off the lamp" against a house with two real
    # lamps ("Big lamp", "My Floor Lamp", both scoring 0.9) surfaced
    # "HallwayCAM (MQTT)" (scoring 0.43, well below missing_floor) as a
    # third choice button, offering the user a device with nothing to do
    # with lamps. Every candidate reaching this point already has
    # top_score >= missing_floor (the branch above returns early
    # otherwise), so filtering ranked[:3] down to only entries that clear
    # the same floor always keeps at least the top candidate while
    # dropping implausible padding.
    plausible_alternatives = tuple(
        name for score, name, _device in ranked[:3] if score >= missing_floor
    )
    return _ambiguous_resolution(
        confidence=top_score,
        alternatives=plausible_alternatives,
        reason=(
            f"{requested!r} is ambiguous; the closest candidates are "
            f"{', '.join(plausible_alternatives)}."
        ),
    )


def device_commands(device: dict[str, Any]) -> set[str]:
    """Every command name a device advertises, casefolded.

    Mirrors the command-name extraction `RuleAuthoringService._commands()`
    already does privately for its own post-resolution capability check --
    exposed here as a public, reusable helper so other capability-aware
    resolution paths don't have to duplicate the list-vs-dict and
    command-vs-name shape handling.
    """

    values = device.get("commands") or device.get("supportedCommands") or []
    if isinstance(values, dict):
        values = list(values)
    commands: set[str] = set()
    for item in values if isinstance(values, (list, tuple, set)) else []:
        if isinstance(item, dict):
            item = item.get("name") or item.get("command")
        if item:
            commands.add(str(item).casefold())
    return commands


def resolve_capable_device_candidate(
    requested: str,
    candidates: list[dict[str, Any]],
    *,
    required_command: str,
    **kwargs: Any,
) -> CandidateResolution:
    """`resolve_device_candidate`, scoped to devices that actually advertise
    `required_command`.

    Plain name resolution alone can pick an exact-label match that lacks
    the capability entirely over a less exact match that has it. Live
    evidence: a real hub has two devices both plausibly named "tv" -- a
    plain power-switch labelled exactly "TV", and a network-integration
    device labelled "Block Google-TV-Streamer" that is the only one of the
    two that actually advertises `blockInternet`/`allowInternet`. Ordinary
    name resolution picks the exact-label switch every time (confidence
    1.0, no contest), even though it can't do what was asked at all.
    Filtering to capable devices FIRST, then resolving by name only among
    those, finds the streamer instead. If literally no device advertises
    the required command, that's reported as a normal "no match" outcome
    so callers get the standard alternatives/error handling rather than a
    device being silently substituted or the command running elsewhere.
    """

    capable = [
        device for device in candidates
        if required_command.casefold() in device_commands(device)
    ]
    if not capable:
        return _missing_resolution(
            confidence=0.0,
            alternatives=(),
            reason=f"no device advertises {required_command!r}",
        )
    return resolve_device_candidate(requested, capable, **kwargs)


__all__ = [
    "CandidateResolution",
    "device_commands",
    "normalized_name",
    "resolve_capable_device_candidate",
    "resolve_device_candidate",
    "targeted_name_variants",
]
