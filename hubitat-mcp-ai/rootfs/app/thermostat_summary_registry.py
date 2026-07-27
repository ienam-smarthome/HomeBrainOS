from __future__ import annotations

from typing import Any, Awaitable, Callable

from thermostat_summary_guard import (
    _DIRECT_THERMOSTAT_QUERY,
    _HOME_SUMMARY_TERMS,
    _SET_TO_PATTERN,
    _direct_answer,
    _live_thermostat_reading,
    correct_thermostat_summary,
)


TerminalRoute = Callable[[Any], Awaitable[dict[str, Any] | None]]
AnswerGuard = Callable[[Any, dict[str, Any]], Awaitable[dict[str, Any]]]


def build_thermostat_terminal_route(application: Any) -> TerminalRoute:
    """Return the registry terminal route for direct thermostat reads."""

    async def thermostat_terminal_route(request: Any) -> dict[str, Any] | None:
        query = str(getattr(request, "query", "") or "")
        if not _DIRECT_THERMOSTAT_QUERY.search(query):
            return None
        reading, diagnostic = await _live_thermostat_reading(application)
        if reading is None:
            return None
        return _direct_answer(reading, diagnostic)

    return thermostat_terminal_route


def build_thermostat_summary_guard(application: Any) -> AnswerGuard:
    """Return the registry guard that corrects thermostat summary semantics."""

    async def thermostat_summary_guard(
        request: Any,
        answer: dict[str, Any],
    ) -> dict[str, Any]:
        answer = dict(answer)
        query = str(getattr(request, "query", "") or "")
        lowered = query.lower()
        message = str(answer.get("message") or "")
        if (
            not any(term in lowered for term in _HOME_SUMMARY_TERMS)
            or not _SET_TO_PATTERN.search(message)
        ):
            return answer

        reading, diagnostic = await _live_thermostat_reading(application)
        if reading is None:
            answer["thermostat_summary_guard_read"] = diagnostic
            return answer

        corrected, evidence = correct_thermostat_summary(message, [reading])
        if evidence is None:
            return answer
        answer["message"] = corrected
        display = answer.get("display")
        if isinstance(display, dict):
            display = dict(display)
            if display.get("summary") == message:
                display["summary"] = corrected
            answer["display"] = display
        answer["thermostat_semantics_corrected"] = True
        answer["thermostat_semantics"] = evidence
        answer["thermostat_summary_guard_read"] = diagnostic
        return answer

    return thermostat_summary_guard


__all__ = [
    "build_thermostat_summary_guard",
    "build_thermostat_terminal_route",
]
