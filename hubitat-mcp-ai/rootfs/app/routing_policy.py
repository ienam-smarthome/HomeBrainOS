from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str


_SIMPLE_CONTROL = re.compile(
    r"^(?:please\s+)?(?:turn|switch)\s+(on|off)\s+(?:the\s+)?(.+?)[.!?]*$",
    re.IGNORECASE,
)

_CONTEXTUAL_TARGET_WORDS = {
    "it",
    "them",
    "that",
    "those",
    "these",
    "same",
    "other",
    "there",
}

_CONTEXTUAL_ONE = re.compile(
    r"^(?:(?:the|that|this|same|other)\s+)?ones?(?:\s+(?:in|from|there))?(?:\s|$)",
    re.IGNORECASE,
)

_COMPLEX_CONTROL_TERMS = (
    " and ",
    " then ",
    " except ",
    " unless ",
    " if ",
    " when ",
    " where ",
    " whichever ",
    " which ",
    " that are ",
    " with ",
    " but ",
    " after ",
    " before ",
)

_PLANNER_TERMS = (
    "why ",
    "explain",
    "analyse",
    "analyze",
    "compare",
    "correlate",
    "recommend",
    "suggest",
    "diagnose",
    "troubleshoot",
    "create rule",
    "create automation",
    "modify rule",
    "change rule",
    "delete rule",
    "optimise",
    "optimize",
    "pattern",
    "trend",
    "based on",
    "depending on",
    "work out",
)

_CONTROL_VERBS = (
    "turn ",
    "switch ",
    "set ",
    "dim ",
    "brighten ",
    "lock ",
    "unlock ",
    "open ",
    "close ",
    "start ",
    "stop ",
)

_FAST_READ_PATTERNS = (
    r"^(?:which|what|list|show)?\s*(?:lights?)\s+(?:are\s+)?on\??$",
    r"^(?:which|what|list|show)?\s*(?:switches?)\s+(?:are\s+)?on\??$",
    r"^(?:which|what|list|show)?\s*(?:batter(?:y|ies))\s+(?:are\s+)?low\??$",
    r"^(?:which|what|list|show)?\s*(?:motion\s+)?sensors?\s+(?:are\s+)?active\??$",
    r"^(?:where\s+is\s+)?motion\s+active\??$",
    r"^(?:what(?:'s| is)\s+)?(?:the\s+)?weather(?:\s+(?:now|today|tomorrow))?\??$",
    r"^(?:what(?:'s| is)\s+)?(?:the\s+)?forecast(?:\s+(?:today|tomorrow))?\??$",
    r"^(?:will\s+it\s+rain|is\s+it\s+raining)(?:\s+(?:now|today|tomorrow))?\??$",
    r"^(?:list|show)\s+(?:all\s+)?devices\??$",
    r"^(?:list|show)\s+(?:all\s+)?lights\??$",
    r"^compare\s+(?:humidity|temperature)\s+(?:in|between)\s+(?:the\s+)?.+?\s+and\s+(?:the\s+)?.+?\??$",
    r"^(?:show|check)\s+(?:the\s+)?hub\s+(?:cpu|memory|free memory|resources|temperature|uptime)(?:\s+and\s+(?:cpu|memory|free memory|temperature|uptime))?\??$",
    r"^how much\s+free memory\s+(?:does\s+)?(?:the\s+)?hub\s+have\??$",
    r"^(?:list|show)\s+devices\s+that\s+are\s+(?:offline|stale)(?:\s+(?:or|and)\s+(?:offline|stale))?\??$",
    r"^(?:device|devices)\s+health(?:\s+status)?\??$",
    r"^(?:find|show|list)\s+devices\s+that\s+(?:need|needs)\s+attention\??$",
    r"^(?:check\s+)?(?:the\s+)?hub\s+(?:health(?: status)?|status)\??$",
    r"^(?:list|show|what are)\s+(?:my\s+)?(?:hubitat\s+)?rooms\??$",
    r"^(?:list|show)\s+(?:my\s+)?(?:active\s+)?(?:automation\s+)?rules\??$",
    # Exact room inventories. The fallback verifies the requested name against
    # Hubitat rooms before returning devices, so ordinary phrases are not treated
    # as room names. "Find devices listed under Apps" is accepted as well.
    r"^(?:list|show|display|find)\s+(?:all\s+)?devices\s+(?:listed\s+)?(?:in|under|inside|from|assigned\s+to)\s+(?:the\s+)?.+?(?:\s+room)?\??$",
    r"^(?:what|which)\s+devices\s+(?:are\s+)?(?:listed\s+)?(?:in|under|inside|from|assigned\s+to)\s+(?:the\s+)?.+?(?:\s+room)?\??$",
    r"^(?:list|show|display)\s+(?:the\s+)?[a-z0-9][a-z0-9 &'_\-]{0,50}(?:\s+room(?:\s+devices)?)?\??$",
)


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _contextual_control_target(target: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", target))
    if words & _CONTEXTUAL_TARGET_WORDS:
        return True
    # "one" is often a spoken number in a real device label (Bedroom One Light).
    # Treat it as contextual only when it is being used as a pronoun, such as
    # "turn off the one in the bedroom".
    return bool(_CONTEXTUAL_ONE.match(target))


def classify_query(query: str) -> RouteDecision:
    """Choose deterministic MCP, verified natural AI, or full AI planning.

    Exact state reads, inventories, simple room comparisons, weather and basic
    on/off controls are deterministic because MCP already has the authoritative
    answer. Natural summaries use MCP evidence plus one short model pass. Only
    requests that genuinely require interpretation or multi-step reasoning use the
    planner.
    """
    q = normalise(query)
    if not q:
        return RouteDecision("ollama-verified", "empty-or-routine")

    control = _SIMPLE_CONTROL.match(q)
    if control:
        target = normalise(control.group(2)).strip(" .!?")
        words = set(re.findall(r"[a-z0-9]+", target))
        contextual = _contextual_control_target(target)
        complex_target = any(term in f" {target} " for term in _COMPLEX_CONTROL_TERMS)
        too_long = len(words) > 8
        if target and not contextual and not complex_target and not too_long:
            return RouteDecision(
                "mcp-fast",
                "single explicit on/off target; verify state deterministically",
            )
        return RouteDecision(
            "ollama-planner",
            "on/off command requires context or multi-device interpretation",
        )

    if any(re.match(pattern, q) for pattern in _FAST_READ_PATTERNS):
        return RouteDecision(
            "mcp-fast",
            "authoritative live-state, weather, room inventory, comparison or diagnostic query",
        )

    if any(q.startswith(verb) for verb in _CONTROL_VERBS):
        return RouteDecision(
            "ollama-planner",
            "non-basic control needs natural interpretation and MCP planning",
        )

    if any(term in q for term in _PLANNER_TERMS):
        return RouteDecision(
            "ollama-planner",
            "reasoning, recommendation, automation or multi-source request",
        )

    return RouteDecision(
        "ollama-verified",
        "routine read-only question; use authoritative MCP evidence then natural wording",
    )


def is_mcp_fast(query: str) -> bool:
    return classify_query(query).route == "mcp-fast"


def requires_planner(query: str) -> bool:
    return classify_query(query).route == "ollama-planner"


__all__ = [
    "RouteDecision",
    "classify_query",
    "is_mcp_fast",
    "normalise",
    "requires_planner",
]
