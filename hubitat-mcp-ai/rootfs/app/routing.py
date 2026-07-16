from __future__ import annotations

import re
from typing import Any

from routing_policy import classify_query, is_mcp_fast


def normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def is_control_query(query: str) -> bool:
    """Return True only for basic, explicit on/off requests.

    Complex controls, contextual pronouns and multi-device conditions are sent to
    the natural Ollama MCP planner. The deterministic path is intentionally narrow
    because it prioritises speed and verified execution over interpretation.
    """
    return is_mcp_fast(query)


def is_fast_path_query(query: str) -> bool:
    return is_mcp_fast(query)


def routing_debug(query: str) -> dict[str, str]:
    decision = classify_query(query)
    return {"route": decision.route, "reason": decision.reason}


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
