"""Safe HTTP 429 diagnostics for Ollama Cloud model calls.

Rate limits, usage-credit exhaustion and a full provider queue can all cause
429. The response alone cannot distinguish them; never invent a reset clock,
retry automatically, or reflect provider body/headers with credentials.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

_RETRY_SECONDS = re.compile(r"^[0-9]{1,6}$")


def describe_ollama_rate_limit(error: httpx.HTTPStatusError) -> tuple[str, str | None] | None:
    """Return user-safe explanation and validated Retry-After, only for 429."""
    response = getattr(error, "response", None)
    if response is None or getattr(response, "status_code", None) != 429:
        return None
    raw = str(response.headers.get("Retry-After") or "").strip()
    seconds = int(raw) if _RETRY_SECONDS.fullmatch(raw) else None
    retry = str(seconds) if seconds is not None and 0 < seconds <= 3600 else None
    detail = (
        "Ollama Cloud rejected this model request (HTTP 429). This can mean "
        "a request/concurrency limit, a full provider queue or insufficient "
        "usage credits. Check your Ollama account's usage and billing, "
        "and avoid repeated requests while the limit applies. "
        "The Hubitat/MCP service may still be online; this investigation "
        "did not obtain a completed cloud-model answer."
    )
    if retry:
        detail += f" The provider supplied a Retry-After delay of {retry} seconds."
    detail += (
        " A configured and reachable local Ollama model can be used via "
        "HomeBrain's existing local-first settings."
    )
    return detail, retry


__all__ = ["describe_ollama_rate_limit"]
