from __future__ import annotations

import re
from typing import Any, Callable, Iterable, TypeVar


T = TypeVar("T")

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


def spoken_name_key(value: Any) -> str:
    """Return a conservative key for obvious speech/typing variations.

    The key intentionally handles only transformations that are safe when applied to
    both the requested phrase and a real selected-device label:

    - number words become digits (``two`` -> ``2``),
    - punctuation and spacing are ignored (``living room`` -> ``livingroom``),
    - repeated alphabetic letters collapse (``liiving`` -> ``living``).

    It does not use phonetic guesses, substring matching or semantic similarity. A
    device is auto-selected only when exactly one selected label has the same key.
    """

    tokens = re.findall(r"[a-z0-9]+", str(value or "").lower())
    normalised: list[str] = []
    for token in tokens:
        token = _NUMBER_WORDS.get(token, token)
        token = re.sub(r"([a-z])\1+", r"\1", token)
        if token not in {"the", "please"}:
            normalised.append(token)
    return "".join(normalised)


def unique_spoken_match(
    requested_name: str,
    candidates: Iterable[T],
    *,
    label_of: Callable[[T], str] = str,
) -> T | None:
    """Return one exact spoken-key match, otherwise remain safely ambiguous."""

    target = spoken_name_key(requested_name)
    if len(target) < 4:
        return None

    matches: list[T] = []
    for candidate in candidates:
        label = str(label_of(candidate) or "").strip()
        if label and spoken_name_key(label) == target:
            matches.append(candidate)
    return matches[0] if len(matches) == 1 else None


__all__ = ["spoken_name_key", "unique_spoken_match"]
