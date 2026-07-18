from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


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


def install_control_language(application: Any) -> AskHandler:
    """Canonicalise only explicit on/off commands before routing."""
    original_ask: AskHandler = application.ask

    async def ask_with_control_language(request: Any) -> dict[str, Any]:
        original_query = str(getattr(request, "query", "") or "").strip()
        control = canonicalise_basic_control(original_query)
        if control is None:
            return await original_ask(request)

        request.query = control.canonical_query
        answer = await original_ask(request)
        if control.correction:
            answer["control_language_correction"] = control.correction
            answer["original_query"] = original_query
            answer["resolved_query"] = control.canonical_query
        return answer

    application.ask = ask_with_control_language
    return ask_with_control_language


__all__ = [
    "AskHandler",
    "BasicControl",
    "canonicalise_basic_control",
    "install_control_language",
]
