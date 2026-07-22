from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from control_agent_intent import ControlIntentInterpreter, is_control_candidate
from control_language import canonicalise_basic_control
from contextual_control import is_contextual_device_control, is_other_device_control
from mutation_result_policy import enforce_device_mutation_result


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
_FAST_PATH_COMPLEX_TERMS = (
    " whichever ",
    " which ",
    " that ",
    " near ",
    " beside ",
    " next to ",
    " except ",
    " unless ",
    " if ",
    " when ",
    " and ",
    ",",
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


def is_exact_fast_control(query: str) -> bool:
    """Return True when the canonical parser proves one explicit safe target."""

    text = re.sub(r"\s+", " ", str(query or "").strip())
    padded = f" {text.lower()} "
    if any(term in padded for term in _FAST_PATH_COMPLEX_TERMS):
        return False
    intent = ControlIntentInterpreter._deterministic_intent(text)
    if intent is None or intent.model is not None or len(intent.actions) != 1:
        return False
    action = intent.actions[0]
    target = action.target
    if (
        not target.name_hint
        or target.quantifier != "one"
        or target.reference != "none"
        or target.exclusions
    ):
        return False
    if action.command == "set_level":
        return action.value is not None and 0 <= action.value <= 100
    return action.command in {"on", "off"}


def install_control_agent_gate(
    application: Any,
    control_agent: Any,
    legacy_ask: AskHandler,
) -> AskHandler:
    """Give the deterministic Control Agent terminal ownership of controls.

    AI may interpret natural language inside the Control Agent's typed intent boundary,
    but it never receives mutation tools. Python resolves selected-device IDs, validates
    capabilities, executes MCP commands and verifies state before reporting an outcome.
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
            if is_other_device_control(query):
                return await control_agent_ask(request)
            # Resolve pronouns against verified per-session device IDs. Browser
            # history supplied to an LLM is not an authoritative device reference.
            if is_contextual_device_control(query):
                return await control_agent_ask(request)
            if is_exact_fast_control(query):
                answer = dict(await control_agent_ask(request))
                answer.setdefault("route_reason", "exact control fast path")
                return answer
            answer = dict(await control_agent_ask(request))
            answer.setdefault(
                "route_reason",
                "terminal deterministic Control Agent resolution, execution and verification",
            )
            return enforce_device_mutation_result(query, answer)
        return await legacy_ask(request)

    application.ask = ask_with_control_gate
    return ask_with_control_gate


__all__ = [
    "install_control_agent_gate",
    "is_exact_fast_control",
    "is_explicit_named_multi_control",
    "is_contextual_device_control",
]
