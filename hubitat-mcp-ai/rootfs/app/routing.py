from __future__ import annotations

import re
from typing import Any


def normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def is_control_query(query: str) -> bool:
    q = normalise(query)
    return bool(
        re.match(
            r"^(?:please\s+)?(?:turn|switch)\s+(?:on|off)\s+(?:the\s+)?[^?]+$",
            q,
        )
    )


def is_fast_path_query(query: str) -> bool:
    """Return True for common requests that do not need LLM reasoning."""
    q = normalise(query)
    if not q:
        return False
    if is_control_query(q):
        return True

    slow_reasoning_terms = (
        "why ",
        "explain",
        "analyse",
        "analyze",
        "compare",
        "correlate",
        "suggest",
        "create rule",
        "create automation",
        "modify rule",
        "troubleshoot",
        "diagnose",
        "what does this mean",
    )
    if any(term in q for term in slow_reasoning_terms):
        return False

    patterns = (
        r"^(?:what(?:'s| is) happening(?: at home)?|home status)\??$",
        r"^(?:which|what|list)?\s*(?:lights?|switches?)\s+(?:are\s+)?on\??$",
        r"^(?:which|what|list)?\s*(?:batter(?:y|ies))\s+(?:are\s+)?low\??$",
        r"^(?:check\s+)?(?:the\s+)?hub\s+(?:health(?: status)?|status)\??$",
        r"^(?:what(?:'s| is)\s+)?(?:the\s+)?hub\s+(?:cpu|memory|free memory)\??$",
        r"^(?:list|show|what are)\s+(?:my\s+)?(?:hubitat\s+)?rooms\??$",
        r"^(?:what(?:'s| is)\s+)?(?:the\s+)?weather(?: today| now)?\??$",
        r"^(?:will it rain|is it raining)(?: today| now)?\??$",
        r"^(?:list|show)\s+(?:my\s+)?(?:active\s+)?(?:automation\s+)?rules\??$",
        r"^(?:find|show|list)\s+devices\s+that\s+(?:need|needs)\s+attention\??$",
        r"^(?:what|which)\s+devices\s+(?:need|needs)\s+attention\??$",
        r"^(?:list|show|find)\s+(?:devices\s+that\s+are\s+)?(?:offline|stale)(?:\s+(?:or|and)\s+(?:offline|stale))?(?:\s+devices)?\??$",
        r"^(?:list|show|find)\s+devices\s+that\s+are\s+offline\s+(?:or|and)\s+stale\??$",
        r"^(?:device|devices)\s+health(?:\s+status)?\??$",
        r"^(?:which|what)\s+devices\s+(?:are\s+)?(?:offline|stale|not responding)\??$",
    )
    return any(re.match(pattern, q) for pattern in patterns)


def dedupe_current_query(
    history: list[dict[str, str]] | None,
    query: str,
) -> list[dict[str, str]]:
    """Remove the UI's duplicated latest user turn before sending to Ollama."""
    cleaned = [
        {
            "role": str(item.get("role") or ""),
            "content": str(item.get("content") or ""),
        }
        for item in (history or [])
        if isinstance(item, dict)
        and item.get("role") in {"user", "assistant"}
        and item.get("content")
    ][-10:]
    if (
        cleaned
        and cleaned[-1]["role"] == "user"
        and normalise(cleaned[-1]["content"]) == normalise(query)
    ):
        cleaned.pop()
    return cleaned
