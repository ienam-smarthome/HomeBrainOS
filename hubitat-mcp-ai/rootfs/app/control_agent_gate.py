from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from control_agent_intent import is_control_candidate
from control_language import canonicalise_basic_control


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_ALIAS_PREFIXES = ("remember ", "call ", "forget alias ", "forget the alias ")
_UNSAFE_MULTI_WORDS = {
    "all",
    "every",
    "both",
    "except",
    "other",
    "same",
    "it",
    "them",
    "those",
    "these",
}
_UNSAFE_MULTI_TERMS = (
    " if ",
    " unless ",
    " when ",
    " before ",
    " after ",
    " but ",
    " then ",
)


def is_explicit_named_multi_control(query: str) -> bool:
    """Keep simple named conjunctions on the existing verified multi-control path."""

    control = canonicalise_basic_control(query)
    if control is None:
        return False
    target = re.sub(r"\s+", " ", control.target.strip(" .!?"))
    if not target or not ("," in target or re.search(r"\band\b", target, re.IGNORECASE)):
        return False
    lowered = f" {target.lower()} "
    if any(term in lowered for term in _UNSAFE_MULTI_TERMS):
        return False
    words = set(re.findall(r"[a-z0-9]+", target.lower()))
    if words & _UNSAFE_MULTI_WORDS:
        return False
    parts = [
        item.strip()
        for item in re.split(r"\s*(?:,|\band\b)\s*", target, flags=re.IGNORECASE)
        if item.strip()
    ]
    return 2 <= len(parts) <= 6 and all(len(item.split()) <= 8 for item in parts)


def install_control_agent_gate(
    application: Any,
    control_agent: Any,
    legacy_ask: AskHandler,
) -> AskHandler:
    """Avoid graph work for non-controls and preserve proven compatibility routes.

    ``install_control_agent`` has already wrapped ``application.ask`` when this is
    called. The gate keeps that wrapped handler only for actual control/alias/pending
    requests. Routine reads call the earlier handler directly, and simple explicit
    named conjunctions use the existing all-or-nothing multi-device controller.
    """

    control_agent_ask: AskHandler = application.ask

    async def ask_with_control_gate(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        session_id = control_agent.contexts.session_id(request)
        if await control_agent.pending.get(session_id) is not None:
            return await control_agent_ask(request)

        lowered = query.lower()
        if any(lowered.startswith(prefix) for prefix in _ALIAS_PREFIXES):
            return await control_agent_ask(request)
        if is_explicit_named_multi_control(query):
            answer = dict(await legacy_ask(request))
            answer["control_agent_bypass"] = "verified-named-multi-control"
            return answer
        if is_control_candidate(query):
            return await control_agent_ask(request)
        return await legacy_ask(request)

    application.ask = ask_with_control_gate
    return ask_with_control_gate


__all__ = [
    "install_control_agent_gate",
    "is_explicit_named_multi_control",
]
