from __future__ import annotations

from typing import Any


_COUNTER_LABELS = (
    ("model_rounds", "Model rounds"),
    ("tool_calls", "Tool calls"),
    ("tool_discovery_calls", "Tool discovery calls"),
    ("mcp_retries", "MCP retries"),
    ("evidence_retries", "Evidence retries"),
    ("grounding_refusals", "Grounding refusals"),
    ("confirmation_queued", "Confirmations queued"),
    ("confirmation_expired", "Confirmations expired"),
    ("mutation_verification_failures", "Verification failures"),
    ("request_cancellations", "Cancellations"),
    ("device_resolution_ambiguous", "Ambiguous resolutions"),
    ("device_resolution_missing", "Missing-device resolutions"),
)

_DURATION_LABELS = (
    ("provider", "Provider"),
    ("mcp", "MCP"),
    ("tool_discovery", "Discovery"),
    ("verification", "Verification"),
    ("total", "Total"),
)

_OUTCOME_PRESENTATION = {
    "success": {"label": "Success", "tone": "positive"},
    "unresolved": {"label": "Unresolved", "tone": "warning"},
    "refused": {"label": "Refused", "tone": "warning"},
    "cancelled": {"label": "Cancelled", "tone": "neutral"},
    "failed": {"label": "Failed", "tone": "critical"},
}


def _non_negative_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _duration_text(milliseconds: float) -> str:
    if milliseconds < 1000:
        return f"{round(milliseconds):d} ms"
    seconds = milliseconds / 1000
    return f"{seconds:.1f} s"


def present_request_outcome(value: Any) -> dict[str, str] | None:
    """Return stable, UI-safe presentation metadata for a fixed outcome value."""

    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    presentation = _OUTCOME_PRESENTATION.get(normalized)
    if presentation is None:
        return None
    return {"value": normalized, **presentation}


def present_request_metrics(metrics: Any) -> list[dict[str, str]]:
    """Return stable, human-readable rows for a RequestMetrics snapshot."""

    if not isinstance(metrics, dict):
        return []
    counters = metrics.get("counters")
    timings = metrics.get("timings_ms")
    if not isinstance(counters, dict):
        counters = {}
    if not isinstance(timings, dict):
        timings = {}

    rows: list[dict[str, str]] = []
    for key, label in _COUNTER_LABELS:
        number = _non_negative_number(counters.get(key))
        if number is None or number == 0:
            continue
        rows.append({"label": label, "value": str(int(number))})
    for key, label in _DURATION_LABELS:
        number = _non_negative_number(timings.get(key))
        if number is None:
            continue
        rows.append({"label": label, "value": _duration_text(number)})

    outcome = present_request_outcome(metrics.get("outcome"))
    if outcome is not None:
        rows.append({"label": "Outcome", "value": outcome["value"]})
    return rows


__all__ = ["present_request_metrics", "present_request_outcome"]
