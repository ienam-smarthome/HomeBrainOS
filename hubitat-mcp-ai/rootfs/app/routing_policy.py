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
    "one",
    "ones",
    "there",
}

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

# Canonical UI shortcuts and equally explicit variants. These return a verified,
# structured answer directly from MCP and do not benefit from a language-model pass.
_FAST_READ_PATTERNS = (
    r"^(?:which|what|list|show)?\s*(?:lights?)\s+(?:are\s+)?on\??$",
    r"^(?:which|what|list|show)?\s*(?:switches?)\s+(?:are\s+)?on\??$",
    r"^(?:which|what|list|show)?\s*(?:batter(?:y|ies))\s+(?:are\s+)?low\??$",
    r"^(?:show|check)\s+(?:the\s+)?hub\s+(?:cpu|memory|free memory|resources|temperature|uptime)(?:\s+and\s+(?:cpu|memory|free memory|temperature|uptime))?\??$",
    r"^how much\s+free memory\s+(?:does\s+)?(?:the\s+)?hub\s+have\??$",
    r"^(?:list|show)\s+devices\s+that\s+are\s+(?:offline|stale)(?:\s+(?:or|and)\s+(?:offline|stale))?\??$",
    r"^(?:device|devices)\s+health(?:\s+status)?\??$",
    r"^(?:find|show|list)\s+devices\s+that\s+(?:need|needs)\s+attention\??$",
    r"^(?:check\s+)?(?:the\s+)?hub\s+(?:health(?: status)?|status)\??$",
    r"^(?:list|show|what are)\s+(?:my\s+)?(?:hubitat\s+)?rooms\??$",
    r"^(?:list|show)\s+(?:my\s+)?(?:active\s+)?(?:automation\s+)?rules\??$",
)


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def classify_query(query: str) -> RouteDecision:
    """Choose the narrow deterministic path or one of the natural AI paths.

    ``mcp-fast``
        Basic explicit on/off commands and canonical live-state or inventory
        shortcuts. These are deterministic, state-verified and normally fast.

    ``ollama-verified``
        Routine natural questions. MCP gathers authoritative evidence first, then
        one Ollama pass turns it into a concise natural answer.

    ``ollama-planner``
        Ambiguous/contextual controls, comparisons, explanations, recommendations,
        automation work and multi-source reasoning.
    """
    q = normalise(query)
    if not q:
        return RouteDecision("ollama-verified", "empty-or-routine")

    control = _SIMPLE_CONTROL.match(q)
    if control:
        target = normalise(control.group(2)).strip(" .!?")
        words = set(re.findall(r"[a-z0-9]+", target))
        contextual = bool(words & _CONTEXTUAL_TARGET_WORDS)
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
            "canonical live-state, inventory or diagnostic shortcut",
        )

    if any(q.startswith(verb) for verb in _CONTROL_VERBS):
        return RouteDecision(
            "ollama-planner",
            "non-basic control needs natural interpretation and MCP planning",
        )

    if any(term in q for term in _PLANNER_TERMS):
        return RouteDecision(
            "ollama-planner",
            "reasoning, comparison, recommendation or automation request",
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
