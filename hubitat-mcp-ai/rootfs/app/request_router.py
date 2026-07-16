from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


async def run_fast_path(
    query: str,
    fallback: Any,
    timeout_seconds: float,
    retries: int = 1,
) -> dict[str, Any]:
    """Run a recognised deterministic request without involving Ollama.

    A transient MCP failure is retried once. The final fallback response is
    returned directly, even when unsuccessful, so callers do not repeat the
    same MCP request or wait for an unavailable Ollama service.
    """
    attempts = max(1, int(retries) + 1)
    errors: list[str] = []

    for attempt in range(attempts):
        try:
            answer = await asyncio.wait_for(
                fallback.answer(query),
                timeout=max(1.0, float(timeout_seconds)),
            )
            if not isinstance(answer, dict):
                answer = {
                    "success": False,
                    "message": "The MCP fast path returned an invalid response.",
                }
            answer.setdefault("fast_path_attempts", attempt + 1)
            if errors:
                answer.setdefault("fast_path_errors", errors)
            if answer.get("success") or attempt == attempts - 1:
                return answer
            errors.append(str(answer.get("message") or "Fast path did not answer"))
        except Exception as exc:
            errors.append(str(exc))
            if attempt == attempts - 1:
                return {
                    "success": False,
                    "message": f"The MCP fast path failed: {exc}",
                    "fast_path_attempts": attempt + 1,
                    "fast_path_errors": errors,
                }

        await asyncio.sleep(0.08)

    return {
        "success": False,
        "message": "The MCP fast path did not produce a response.",
        "fast_path_attempts": attempts,
        "fast_path_errors": errors,
    }


async def schedule_background_health_check(
    health_call: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    """Refresh Ollama health without delaying the user's response."""
    try:
        await health_call(force=True)
    except Exception:
        pass
