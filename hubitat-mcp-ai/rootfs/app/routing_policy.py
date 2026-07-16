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


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def classify_query(query: str) -> RouteDecision:
    """Choose the narrow deterministic path or one of the natural AI paths.

    - ``mcp-fast`` is deliberately limited to one explicit on/off target.
    - ``ollama-verified`` uses deterministic MCP evidence plus one natural summary.
    - ``ollama-planner`` lets Ollama select and combine MCP tools.
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
