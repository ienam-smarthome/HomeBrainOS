from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BasicControl:
    action: str
    target: str
    canonical_query: str
    correction: str | None = None


_PREFIX = re.compile(
    r"^(?:please\s+)?(?:turn|switch)\s+(on|off|of)\s+(?:the\s+)?(.+?)[.!?]*$",
    re.IGNORECASE,
)
_SUFFIX = re.compile(
    r"^(?:please\s+)?(?:turn|switch)\s+(?:the\s+)?(.+?)\s+(on|off|of)[.!?]*$",
    re.IGNORECASE,
)


def canonicalise_basic_control(query: str) -> BasicControl | None:
    """Return a safe canonical form for a simple switch on/off command.

    The narrowly-scoped ``of`` correction handles the common speech/typing form
    ``turn of Bedroom 3 Light`` without changing ordinary occurrences of "of".
    Both action-first and action-last wording are accepted.
    """
    text = re.sub(r"\s+", " ", str(query or "").strip())
    if not text:
        return None

    match = _PREFIX.match(text)
    if match:
        raw_action = match.group(1).lower()
        target = match.group(2).strip(" .!?")
    else:
        match = _SUFFIX.match(text)
        if not match:
            return None
        target = match.group(1).strip(" .!?")
        raw_action = match.group(2).lower()

    if not target:
        return None
    action = "off" if raw_action == "of" else raw_action
    correction = "of→off" if raw_action == "of" else None
    return BasicControl(
        action=action,
        target=target,
        canonical_query=f"turn {action} {target}",
        correction=correction,
    )


__all__ = ["BasicControl", "canonicalise_basic_control"]
