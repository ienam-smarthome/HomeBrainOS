from __future__ import annotations

import re
from typing import Any


def normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def is_control_query(query: str) -> bool:
    """Only explicit, low-risk on/off commands bypass Ollama.

    Natural read questions, diagnostics, weather, rooms, rules and reasoning now
    go through the Ollama-first MCP agent. The deterministic path is retained for
    basic commands where speed and state verification matter more than language
    synthesis.
    """
    q = normalise(query)
    return bool(
        re.match(
            r"^(?:please\s+)?(?:turn|switch)\s+(?:on|off)\s+(?:the\s+)?[^?]+$",
            q,
        )
    )


def is_fast_path_query(query: str) -> bool:
    return is_control_query(query)


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
