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

_UNSAFE_MULTI_CONTROL_TERMS = tuple(
    term for term in _COMPLEX_CONTROL_TERMS if term != " and "
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
    "backup",
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

_DEVICE_TYPE_PHRASE = (
    r"(?:motion\s+(?:sensors?|detectors?)|contact\s+sensors?|door\s+sensors?|window\s+sensors?|"
    r"temperature\s+(?:sensors?|devices?)|humidity\s+(?:sensors?|devices?)|presence\s+sensors?|"
    r"occupancy\s+sensors?|illuminance\s+sensors?|light\s+sensors?|lux\s+sensors?|"
    r"battery\s+(?:devices?|sensors?)|thermostats?|trvs?|radiator\s+valves?|locks?|"
    r"smoke\s+(?:detectors?|alarms?)|carbon\s+monoxide\s+(?:detectors?|sensors?)|co\s+detectors?|"
    r"water\s+sensors?|leak\s+sensors?|moisture\s+sensors?|soil\s+sensors?|"
    r"power\s+(?:meters?|monitors?|devices?)|energy\s+(?:meters?|monitors?|devices?)|"
    r"lights?|lamps?|bulbs?|dimmers?|switches?|sockets?|outlets?|smart\s+plugs?|plugs?|"
    r"cameras?|cams?|fans?|valves?|buttons?|scene\s+buttons?|sirens?|alarms?|"
    r"acceleration\s+sensors?|vibration\s+sensors?|sensors?)"
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
    r"^(?:what\s+time\s+(?:is|does)|when\s+(?:is|does)|tell\s+me\s+(?:the\s+)?)\s*(?:fajr|fajar|sunrise|shuruq|ishraq|dhuhr|dhur|zuhr|zohar|asr|maghrib|magrib|isha|ishaa)(?:\s+(?:start|begin|starts|begins))?(?:\s+(?:today|tonight))?\??$",
    r"^(?:fajr|fajar|sunrise|shuruq|ishraq|dhuhr|dhur|zuhr|zohar|asr|maghrib|magrib|isha|ishaa)(?:\s+prayer)?\s+time(?:\s+(?:today|tonight))?\??$",
    r"^(?:show|list|display|give\s+me|what\s+are|what(?:'s|\s+is))\s+(?:today(?:'s)?\s+)?(?:pray|prayer)\s+times(?:\s+today)?\??$",
    rf"^(?:show|list|find|get|display)\s+(?:me\s+)?(?:(?:all|every|the)\s+)?{_DEVICE_TYPE_PHRASE}\??$",
    rf"^(?:what|which)\s+{_DEVICE_TYPE_PHRASE}\s+(?:devices?\s+)?(?:do\s+i\s+have|are\s+(?:there|available|selected|configured))\??$",
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
    r"^(?:show|get|list|find)?\s*(?:recent\s+)?hub\s+(?:logs?|errors?|warnings?)(?:\s+and\s+(?:logs?|errors?|warnings?))?\??$",
    r"^(?:show|list|get|find)\s+(?:the\s+)?(?:slow|busy)\s+(?:apps?|devices?)\??$",
    r"^(?:show|list|get)\s+(?:the\s+)?(?:hub\s+)?performance(?:\s+stats?)?\??$",
    r"^(?:show|list|get)\s+(?:the\s+)?(?:scheduled|running|hub)\s+(?:jobs?|tasks?)\??$",
    r"^(?:list|show|find|get)\s+(?:all\s+)?(?:installed\s+)?(?:hubitat\s+)?apps?\??$",
    r"^(?:list|show|get)\s+(?:the\s+)?(?:hpm|installed|package manager)\s+packages?\??$",
    r"^(?:list|show|get)\s+(?:the\s+)?(?:hub|global)\s+variables?\??$",
    r"^(?:list|show|get)\s+(?:the\s+)?(?:easy|hub)?\s*dashboards?\??$",
    r"^(?:show|get)\s+(?:the\s+)?(?:hub\s+)?(?:memory|cpu)\s+(?:history|trend)\??$",
    r"^(?:show|get)\s+(?:the\s+)?(?:z-wave|zwave|zigbee|matter|radio)\s+details?\??$",
    r"^(?:show|list|get|find)\s+(?:the\s+)?(?:recent\s+)?events\s+(?:for|from|of)\s+.+?\??$",
    r"^(?:show|list|get)\s+.+?\s+events\??$",
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
    return bool(_CONTEXTUAL_ONE.match(target))


def _explicit_multi_control_targets(target: str) -> list[str] | None:
    """Recognise only safe explicit named conjunctions for deterministic control."""

    padded = f" {normalise(target)} "
    if not ("," in target or " and " in padded):
        return None
    if any(term in padded for term in _UNSAFE_MULTI_CONTROL_TERMS):
        return None

    parts = [
        re.sub(r"^(?:the\s+)", "", item.strip(), flags=re.IGNORECASE)
        for item in re.split(r"\s*(?:,|\band\b)\s*", target, flags=re.IGNORECASE)
    ]
    if not 2 <= len(parts) <= 6 or any(not part for part in parts):
        return None
    for part in parts:
        words = set(re.findall(r"[a-z0-9]+", normalise(part)))
        if not words or len(words) > 8 or words & _CONTEXTUAL_TARGET_WORDS:
            return None
        if _CONTEXTUAL_ONE.match(normalise(part)):
            return None
    return parts


def classify_query(query: str) -> RouteDecision:
    """Choose deterministic MCP, verified natural AI, or full AI planning."""

    q = normalise(query)
    if not q:
        return RouteDecision("ollama-verified", "empty-or-routine")

    control = _SIMPLE_CONTROL.match(q)
    if control:
        target = normalise(control.group(2)).strip(" .!?")
        words = set(re.findall(r"[a-z0-9]+", target))
        contextual = _contextual_control_target(target)
        explicit_targets = _explicit_multi_control_targets(target)
        if explicit_targets is not None:
            return RouteDecision(
                "mcp-fast",
                "multiple explicit on/off targets; exact-match all and verify states deterministically",
            )
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
            "authoritative live-state, device-type inventory, gateway read, room inventory, comparison or diagnostic query",
        )

    if any(q.startswith(verb) for verb in _CONTROL_VERBS):
        return RouteDecision(
            "ollama-planner",
            "non-basic control needs natural interpretation and MCP planning",
        )

    if any(term in q for term in _PLANNER_TERMS):
        return RouteDecision(
            "ollama-planner",
            "reasoning, recommendation, automation, backup or multi-source request",
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
